#!/usr/bin/env python3
"""Superloop: strategy-to-execution multi-pair Codex orchestration.

Implements optional producer/verifier loops using Doc-Loop style control signals:
- <question>...</question>
- verifier-only final line <promise>COMPLETE|INCOMPLETE|BLOCKED</promise>
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set

PROMISE_COMPLETE = "COMPLETE"
PROMISE_INCOMPLETE = "INCOMPLETE"
PROMISE_BLOCKED = "BLOCKED"
PROMISE_LINE_RE = re.compile(
    r"^\s*<promise>(COMPLETE|INCOMPLETE|BLOCKED)</promise>\s*$",
    re.IGNORECASE,
)

PAIR_ORDER = ["plan", "implement", "test"]

PAIR_LABELS = {
    "plan": "Plan ↔ Plan Verifier",
    "implement": "Implement ↔ Code Reviewer",
    "test": "Test Author ↔ Test Auditor",
}

PAIR_ARTIFACTS = {
    "plan": ["plan.md", "milestones.md", "interfaces.md", "risk_register.md"],
    "implement": ["implementation_notes.md", "review_findings.md"],
    "test": ["test_strategy.md", "test_gaps.md"],
}

PAIR_CRITERIA_TEMPLATES = {
    "plan": """# Plan Verification Criteria
Check these boxes (`- [x]`) only when true.

- [ ] **Correctness**: The plan does not contradict repository constraints, known requirements, or prior clarifications.
- [ ] **Completeness**: Scope, milestones, interfaces, dependencies, rollout, and operational constraints are concrete and implementation-ready.
- [ ] **Regression Risk**: Risks, blast radius, and rollback/mitigation strategy are explicit and actionable.
- [ ] **DRY / KISS**: The plan avoids redundant sections and unnecessary complexity.
- [ ] **Feasibility**: Timeline and sequencing are realistic and blockers are surfaced.
""",
    "implement": """# Code Review Criteria
Check these boxes (`- [x]`) only when true.

- [ ] **Correctness**: Changes satisfy the accepted plan/requirements and preserve expected behavior.
- [ ] **Safety**: No obvious security or data-integrity regressions were introduced.
- [ ] **Architecture Conformance**: Changes match repo conventions and avoid needless complexity.
- [ ] **Performance**: No avoidable major regressions or pathological hot paths were introduced.
- [ ] **Maintainability**: Diffs are understandable, cohesive, and adequately documented where needed.
""",
    "test": """# Test Audit Criteria
Check these boxes (`- [x]`) only when true.

- [ ] **Coverage Quality**: New/changed behavior is covered at appropriate levels (unit/integration/e2e as applicable).
- [ ] **Edge Cases**: Failure and boundary cases for changed behavior are covered.
- [ ] **Flaky Risk Control**: Tests avoid nondeterministic timing/network assumptions without stabilization.
- [ ] **Regression Shield**: Critical regressions from changed modules/contracts are guarded.
- [ ] **Signal Quality**: Assertions validate outcomes, not only execution paths.
""",
}

PAIR_PRODUCER_PROMPT = {
    "plan": """# Superloop Planner Instructions
You are the planning agent for this repository.

## Goal
Turn the user intent into an implementation-ready plan with milestones, interfaces, and risk controls.

## Required outputs
Update these artifacts in `.superloop/plan/`:
- `plan.md`
- `milestones.md`
- `interfaces.md`
- `risk_register.md`

Also append a concise entry to `.superloop/plan/feedback.md` with what changed and why.

## Rules
1. Analyze the repository and user request deeply before proposing edits. Understand current behavior, constraints, and interfaces.
2. Check and verify your own plan for consistency, feasibility, DRY/KISS quality, and regression risk before writing files.
3. Keep the plan concrete and implementation-ready.
4. Apply KISS and DRY; avoid speculative complexity.
5. Do not edit `.superloop/plan/criteria.md` (verifier-owned).
6. If the user request is ambiguous, logically flawed, introduces breaking changes, may cause regressions, or may create hidden unintended behavior, warn the user via a clarifying question.
7. Every clarifying question must include your best suggestion/supposition so the user can confirm or correct quickly.
8. When asking a clarifying question, do not edit files and output exactly:
<question>Question text. Best suggestion/supposition: ...</question>
9. Do not output any `<promise>...</promise>` tag.
""",
    "implement": """# Superloop Implementer Instructions
You are the implementation agent for this repository.

## Goal
Implement the approved plan and reviewer feedback with high-quality multi-file code changes.

## Working set
- Entire repository
- `.superloop/context.md`
- `.superloop/implement/feedback.md`
- `.superloop/plan/*` artifacts when present

## Rules
1. Apply minimal, high-signal changes; keep KISS/DRY.
2. Resolve reviewer findings explicitly.
3. Update `.superloop/implement/implementation_notes.md` with a concise changelog.
4. Do not edit `.superloop/implement/criteria.md` (reviewer-owned).
5. If blocked by missing product intent, do not edit files; output:
<question>your question</question>
6. Do not output any `<promise>...</promise>` tag.
""",
    "test": """# Superloop Test Author Instructions
You are the test authoring agent for this repository.

## Goal
Create or refine tests and fixtures to validate changed behavior and prevent regressions.

## Required outputs
- Update relevant test files in the repository.
- Update `.superloop/test/test_strategy.md` with what is covered.
- Append a concise entry to `.superloop/test/feedback.md` summarizing test additions.

## Rules
1. Favor deterministic tests with stable setup/teardown.
2. Cover edge and failure paths for changed behavior.
3. Do not edit `.superloop/test/criteria.md` (auditor-owned).
4. If blocked by missing intent, do not edit files; output:
<question>your question</question>
5. Do not output any `<promise>...</promise>` tag.
""",
}

PAIR_VERIFIER_PROMPT = {
    "plan": """# Superloop Plan Verifier Instructions
You are the plan verifier.

## Goal
Audit planning artifacts for correctness, completeness, regression risk, and KISS/DRY quality.

## Required actions
1. Update `.superloop/plan/criteria.md` checkboxes accurately.
2. Append actionable findings to `.superloop/plan/feedback.md` when incomplete.
3. End the last non-empty line of stdout with exactly one tag:
<promise>COMPLETE</promise> OR <promise>INCOMPLETE</promise> OR <promise>BLOCKED</promise>

## Rules
- You may not edit repository source code.
- Ask `<question>...</question>` only when missing product intent makes safe verification impossible.
- If COMPLETE, every checkbox in criteria must be checked.
""",
    "implement": """# Superloop Code Reviewer Instructions
You are the code reviewer.

## Goal
Audit implementation diffs for correctness, architecture conformance, security, performance, and maintainability.

## Required actions
1. Update `.superloop/implement/criteria.md` checkboxes accurately.
2. Append clear, file-targeted review findings to `.superloop/implement/feedback.md` when incomplete.
3. End the last non-empty line with exactly one promise tag:
<promise>COMPLETE</promise> OR <promise>INCOMPLETE</promise> OR <promise>BLOCKED</promise>

## Rules
- Do not modify non-`.superloop/` code files.
- Ask `<question>...</question>` only for missing product intent.
- If COMPLETE, criteria must have no unchecked boxes.
""",
    "test": """# Superloop Test Auditor Instructions
You are the test auditor.

## Goal
Audit tests for coverage quality, edge-case depth, and flaky-risk control.

## Required actions
1. Update `.superloop/test/criteria.md` checkboxes accurately.
2. Append actionable gaps to `.superloop/test/feedback.md` when incomplete.
3. End the last non-empty line with exactly one promise tag:
<promise>COMPLETE</promise> OR <promise>INCOMPLETE</promise> OR <promise>BLOCKED</promise>

## Rules
- Do not edit repository code except `.superloop/test/*` audit artifacts.
- Ask `<question>...</question>` only for missing product intent.
- If COMPLETE, criteria must have no unchecked boxes.
""",
}


@dataclass(frozen=True)
class PairConfig:
    name: str
    enabled: bool
    max_iterations: int


@dataclass(frozen=True)
class PhaseSnapshot:
    """Git reference and untracked-file baseline for one phase."""

    ref: str
    untracked_paths: frozenset[str]


def fatal(message: str, exit_code: int = 1):
    print(message, file=sys.stderr)
    sys.exit(exit_code)


def warn(message: str):
    print(f"[!] WARNING: {message}", file=sys.stderr)


def run_git(args: List[str], cwd: Path, allow_fail: bool = False) -> subprocess.CompletedProcess[str]:
    res = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if res.returncode != 0 and not allow_fail:
        fatal(f"[!] FATAL GIT ERROR: {' '.join(args)}\n{res.stderr.strip()}")
    return res


def normalize_repo_path(path_text: str) -> str:
    """Normalizes a repo-relative path from git porcelain output."""
    cleaned = path_text.strip()
    if " -> " in cleaned:
        cleaned = cleaned.split(" -> ", 1)[1]
    return cleaned


def parse_status_paths(status_text: str) -> Set[str]:
    """Parses git porcelain status into a set of changed repo-relative paths."""
    changed: Set[str] = set()
    for line in status_text.splitlines():
        if len(line) < 4:
            continue
        changed.add(normalize_repo_path(line[3:]))
    return changed



def list_untracked_paths(cwd: Path, tracked_paths: Optional[Sequence[str]] = None) -> Set[str]:
    """Returns untracked files in the working tree."""
    args = ["ls-files", "--others", "--exclude-standard"]
    if tracked_paths:
        args.extend(["--", *tracked_paths])
    out = run_git(args, cwd=cwd).stdout
    return {line.strip() for line in out.splitlines() if line.strip()}


def phase_snapshot_ref(cwd: Path, tracked_paths: Optional[Sequence[str]] = None) -> PhaseSnapshot:
    """Returns a git snapshot reference plus untracked-file baseline."""
    untracked = frozenset(list_untracked_paths(cwd, tracked_paths=tracked_paths))

    snap = run_git(["stash", "create", "superloop-phase-snapshot"], cwd=cwd, allow_fail=True).stdout.strip()
    if snap:
        return PhaseSnapshot(ref=snap, untracked_paths=untracked)

    head = run_git(["rev-parse", "HEAD"], cwd=cwd, allow_fail=True).stdout.strip()
    if head:
        return PhaseSnapshot(ref=head, untracked_paths=untracked)

    fatal("[!] FATAL GIT ERROR: Unable to create a phase snapshot reference.")


def changed_paths_from_snapshot(cwd: Path, snapshot: PhaseSnapshot, tracked_paths: Optional[Sequence[str]] = None) -> Set[str]:
    """Returns files changed since a snapshot, including newly-created untracked files."""
    args = ["diff", "--name-only", snapshot.ref, "--"]
    if tracked_paths:
        args.extend(tracked_paths)
    tracked_delta = {line.strip() for line in run_git(args, cwd=cwd).stdout.splitlines() if line.strip()}

    current_untracked = list_untracked_paths(cwd, tracked_paths=tracked_paths)
    new_untracked = current_untracked - set(snapshot.untracked_paths)
    return tracked_delta | new_untracked
def changed_paths(cwd: Path, tracked_paths: Optional[Sequence[str]] = None) -> Set[str]:
    """Returns changed paths from git porcelain status, optionally restricted to tracked paths."""
    args = ["status", "--porcelain"]
    if tracked_paths:
        args.extend(["--", *tracked_paths])
    return parse_status_paths(run_git(args, cwd=cwd).stdout)


def allowed_verifier_paths(pair: str) -> List[str]:
    """Returns repo-relative paths a verifier is allowed to edit for a pair."""
    return [f".superloop/{pair}/"]


def verifier_scope_violations(pair: str, verifier_delta: Set[str]) -> List[str]:
    """Returns verifier writes that are outside its allowed scope."""
    allowed = tuple(allowed_verifier_paths(pair))
    return sorted(path for path in verifier_delta if not path.startswith(allowed))


def tracked_superloop_paths(pair: Optional[str] = None) -> List[str]:
    """Returns paths that Superloop may stage/commit."""
    shared_paths = [".superloop/context.md", ".superloop/run_log.md"]
    if pair is None:
        pair_paths = [f".superloop/{name}/" for name in PAIR_ORDER]
    else:
        pair_paths = [f".superloop/{pair}/"]
    return [*shared_paths, *pair_paths]


def has_git_repo(root: Path) -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return probe.returncode == 0


def ensure_git_commit_ready(root: Path):
    author = run_git(["var", "GIT_AUTHOR_IDENT"], cwd=root, allow_fail=True)
    committer = run_git(["var", "GIT_COMMITTER_IDENT"], cwd=root, allow_fail=True)
    if author.returncode != 0 or committer.returncode != 0:
        details = (
            author.stderr.strip()
            or committer.stderr.strip()
            or "Configure user.name and user.email for this repository."
        )
        fatal(f"[!] FATAL GIT ERROR: Unable to determine a valid git author identity.\n{details}")


def repo_relative_path(root: Path, absolute_or_relative: Path) -> str:
    """Returns a git-usable repo-relative path string."""
    try:
        return str(absolute_or_relative.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(absolute_or_relative)


def commit_paths(root: Path, message: str, paths: Iterable[str]) -> bool:
    """Stages and commits only the provided repo-relative paths when changed."""
    unique_paths = sorted({p for p in paths if p})
    if not unique_paths:
        return False

    run_git(["add", "--", *unique_paths], cwd=root)
    if not changed_paths(root, tracked_paths=unique_paths):
        return False

    run_git(["commit", "-m", message], cwd=root)
    return True


def commit_tracked_changes(root: Path, message: str, tracked_paths: Optional[Sequence[str]] = None) -> bool:
    tracked = list(tracked_paths) if tracked_paths else tracked_superloop_paths()
    return commit_paths(root, message, tracked)


def check_dependencies():
    missing = []
    if not shutil.which("git"):
        missing.append("git")
    if not shutil.which("codex"):
        missing.append("codex (install via 'npm i -g @openai/codex')")
    if missing:
        fatal(f"[!] FATAL: Missing required dependencies: {', '.join(missing)}")


def resolve_codex_exec_command(model: str) -> List[str]:
    help_result = subprocess.run(
        ["codex", "exec", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if help_result.returncode != 0:
        details = help_result.stderr.strip() or help_result.stdout.strip() or "Unable to inspect `codex exec --help`."
        fatal(f"[!] FATAL CODEX ERROR: {details}")

    help_text = f"{help_result.stdout}\n{help_result.stderr}"
    if "--full-auto" in help_text:
        return ["codex", "exec", "--ephemeral", "--full-auto", "--model", model, "-"]
    fatal("[!] FATAL CODEX ERROR: This Superloop version requires `codex exec --full-auto` support.")


def parse_pairs(pairs_arg: str, max_iterations: int) -> List[PairConfig]:
    requested = [p.strip().lower() for p in pairs_arg.split(",") if p.strip()]
    if not requested:
        fatal("[!] FATAL: --pairs must include at least one pair.")

    duplicates = sorted({name for name in requested if requested.count(name) > 1})
    if duplicates:
        fatal(
            f"[!] FATAL: Duplicate pair(s) in --pairs: {', '.join(duplicates)}. "
            f"Use each pair at most once from: {', '.join(PAIR_ORDER)}"
        )

    invalid = [p for p in requested if p not in PAIR_ORDER]
    if invalid:
        fatal(f"[!] FATAL: Unsupported pair(s): {', '.join(invalid)}. Valid values: {', '.join(PAIR_ORDER)}")

    requested_set = set(requested)
    return [
        PairConfig(name=pair, enabled=(pair in requested_set), max_iterations=max_iterations)
        for pair in PAIR_ORDER
    ]


def ensure_workspace(root: Path, product_intent: Optional[str]) -> Dict[str, Path]:
    super_dir = root / ".superloop"
    super_dir.mkdir(parents=True, exist_ok=True)

    context_file = super_dir / "context.md"
    if not context_file.exists():
        starter = "# Product Context\n\n"
        if product_intent:
            starter += f"{product_intent.strip()}\n"
        else:
            starter += "Add business goals, constraints, and non-negotiable requirements here.\n"
        context_file.write_text(starter, encoding="utf-8")

    run_log = super_dir / "run_log.md"
    if not run_log.exists():
        run_log.write_text("# Superloop Run Log\n", encoding="utf-8")

    pair_dirs: Dict[str, Path] = {}
    for pair in PAIR_ORDER:
        pair_dir = super_dir / pair
        pair_dir.mkdir(parents=True, exist_ok=True)
        pair_dirs[pair] = pair_dir

        prompt_file = pair_dir / "prompt.md"
        if not prompt_file.exists():
            prompt_file.write_text(PAIR_PRODUCER_PROMPT[pair], encoding="utf-8")

        verifier_prompt_file = pair_dir / "verifier_prompt.md"
        if not verifier_prompt_file.exists():
            verifier_prompt_file.write_text(PAIR_VERIFIER_PROMPT[pair], encoding="utf-8")

        criteria_file = pair_dir / "criteria.md"
        if not criteria_file.exists():
            criteria_file.write_text(PAIR_CRITERIA_TEMPLATES[pair], encoding="utf-8")

        feedback_file = pair_dir / "feedback.md"
        if not feedback_file.exists():
            feedback_file.write_text(f"# {PAIR_LABELS[pair]} Feedback\n", encoding="utf-8")

        for artifact_name in PAIR_ARTIFACTS[pair]:
            artifact = pair_dir / artifact_name
            if not artifact.exists():
                artifact.write_text(f"# {artifact_name}\n", encoding="utf-8")

    return {
        "super_dir": super_dir,
        "context_file": context_file,
        "run_log": run_log,
        **{f"pair_{k}": v for k, v in pair_dirs.items()},
    }


def run_codex_phase(codex_command: List[str], cwd: Path, prompt_file: Path, phase_name: str, pair_name: str) -> str:
    base_instructions = prompt_file.read_text(encoding="utf-8")
    prompt_payload = (
        f"REPOSITORY ROOT: {cwd}\n"
        f"LOOP PAIR: {pair_name}\n"
        "Follow the prompt rules exactly.\n\n"
        f"{base_instructions}"
    )

    print(f"[*] Spawning {pair_name}:{phase_name} agent...")
    process = subprocess.run(
        codex_command,
        cwd=cwd,
        input=prompt_payload,
        text=True,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        encoding="utf-8",
    )

    stdout = process.stdout or ""
    if process.returncode != 0:
        if stdout.strip():
            print(stdout.rstrip(), file=sys.stderr)
        fatal(f"\n[!] Codex CLI failed during {pair_name}:{phase_name} with exit code {process.returncode}.")
    return stdout


def last_non_empty_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        if line.strip():
            return line.strip()
    return ""


def extract_control_tags(stdout: str) -> tuple[Optional[str], Optional[str]]:
    question_match = re.search(r"<question>(.*?)</question>", stdout, re.DOTALL | re.IGNORECASE)
    promise_match = PROMISE_LINE_RE.fullmatch(last_non_empty_line(stdout))
    question_text = question_match.group(1).strip() if question_match else None
    promise = promise_match.group(1).upper() if promise_match else None
    return question_text, promise


def criteria_all_checked(criteria_file: Path) -> bool:
    criteria_text = criteria_file.read_text(encoding="utf-8")
    return re.search(r"^- \[ \]", criteria_text, re.MULTILINE) is None


def ask_human(question_text: str) -> str:
    print(f"\n[AGENT QUESTION]\n{question_text}\n")
    while True:
        try:
            answer = input("Your answer (type 'skip' to provide no answer): ").strip()
        except EOFError:
            print("\n[!] EOF detected. Exiting.")
            sys.exit(130)

        if answer.lower() == "skip":
            return "[User skipped providing an answer]"
        if answer:
            return answer
        print("Please provide an answer, or type 'skip'.")


def auto_answer_question(codex_command: List[str], root: Path, context_file: Path, question: str) -> str:
    context = context_file.read_text(encoding="utf-8")
    prompt = (
        "You are assisting a superloop orchestrator.\n"
        "Answer the question using repository context and existing requirements.\n"
        "If uncertain, provide the safest explicit assumption.\n"
        "Return plain text only.\n\n"
        f"Question:\n{question}\n\n"
        f"Context:\n{context}\n"
    )
    process = subprocess.run(
        codex_command,
        cwd=root,
        input=prompt,
        text=True,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        encoding="utf-8",
    )
    if process.returncode != 0:
        fatal(f"[!] Auto-answer pass failed with exit code {process.returncode}.")
    answer = (process.stdout or "").strip()
    if not answer:
        return "[Auto-answer failed to produce content]"
    return answer


def append_clarification(context_file: Path, pair: str, phase: str, cycle: int, question: str, answer: str):
    with context_file.open("a", encoding="utf-8") as f:
        f.write(f"\n\n### Clarification ({pair}, cycle {cycle}, {phase})\n")
        f.write(f"**Q:** {question}\n")
        f.write(f"**A:** {answer}\n")


def append_run_log(run_log: Path, message: str):
    with run_log.open("a", encoding="utf-8") as f:
        f.write(f"\n- {message}\n")


def main():
    parser = argparse.ArgumentParser(description="Superloop: optional strategy-to-execution Codex loop orchestration")
    parser.add_argument("--pairs", type=str, default="plan,implement,test", help="Comma list from: plan,implement,test")
    parser.add_argument("--max-iterations", type=int, default=8, help="Maximum verifier cycles per enabled pair")
    parser.add_argument("--model", type=str, default="gpt-5.4", help="Codex model")
    parser.add_argument("--workspace", type=str, default=".", help="Repository/workspace root")
    parser.add_argument("--intent", type=str, help="Optional initial product intent text")
    parser.add_argument("--full-auto-answers", action="store_true", help="Auto-answer agent questions using an extra Codex pass")
    args = parser.parse_args()

    if args.max_iterations < 1:
        fatal("[!] FATAL: --max-iterations must be >= 1")

    root = Path(args.workspace).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        fatal(f"[!] FATAL: --workspace must be an existing directory: {root}")

    check_dependencies()
    codex_command = resolve_codex_exec_command(args.model)
    pair_configs = parse_pairs(args.pairs, args.max_iterations)

    repo_exists = has_git_repo(root)
    if not repo_exists:
        print("[*] Initializing local Git repository...")
        run_git(["init"], cwd=root)
        run_git(["config", "user.name", "Superloop Agent"], cwd=root)
        run_git(["config", "user.email", "superloop@localhost"], cwd=root)

    ensure_git_commit_ready(root)
    paths = ensure_workspace(root, args.intent)

    commit_tracked_changes(root, "superloop: baseline")

    print("\n[+] Starting Superloop")
    print(f"[*] Workspace root: {root}")
    print(f"[*] Enabled pairs: {', '.join([p.name for p in pair_configs if p.enabled])}")

    try:
        for pair_cfg in pair_configs:
            if not pair_cfg.enabled:
                continue

            pair = pair_cfg.name
            pair_dir = paths[f"pair_{pair}"]
            prompt_file = pair_dir / "prompt.md"
            verifier_prompt_file = pair_dir / "verifier_prompt.md"
            criteria_file = pair_dir / "criteria.md"
            feedback_file = pair_dir / "feedback.md"

            print(f"\n===== Pair: {PAIR_LABELS[pair]} =====")
            append_run_log(paths["run_log"], f"Started pair `{pair}`")

            cycle = 0
            while cycle < pair_cfg.max_iterations:
                cycle_num = cycle + 1
                print(f"\n--- {pair} cycle {cycle_num}/{pair_cfg.max_iterations} ---")
                pair_tracked = tracked_superloop_paths(pair)
                commit_tracked_changes(root, f"superloop: pre-cycle snapshot ({pair} #{cycle_num})", pair_tracked)

                producer_baseline = phase_snapshot_ref(root)

                producer_stdout = run_codex_phase(codex_command, root, prompt_file, "producer", pair)
                producer_question, producer_promise = extract_control_tags(producer_stdout)
                producer_delta = changed_paths_from_snapshot(root, producer_baseline)

                if producer_question:
                    if producer_delta:
                        warn(
                            f"{pair} producer emitted <question> after editing files in this phase; proceeding in lax guard mode."
                        )
                    if args.full_auto_answers:
                        answer = auto_answer_question(codex_command, root, paths["context_file"], producer_question)
                        print(f"[+] Auto-answered producer question: {answer}")
                    else:
                        answer = ask_human(producer_question)
                    append_clarification(paths["context_file"], pair, "producer", cycle_num, producer_question, answer)
                    commit_tracked_changes(root, f"superloop: answered producer question ({pair} #{cycle_num})", pair_tracked)
                    continue

                if producer_promise:
                    warn(
                        f"{pair} producer emitted <promise>{producer_promise}</promise>; ignoring because verifier controls completion."
                    )

                if producer_delta:
                    commit_paths(root, f"superloop: producer edits ({pair} #{cycle_num})", producer_delta)
                else:
                    print("[-] Producer made no changes.")

                verifier_baseline = phase_snapshot_ref(root)

                verifier_stdout = run_codex_phase(codex_command, root, verifier_prompt_file, "verifier", pair)
                verifier_question, verifier_promise = extract_control_tags(verifier_stdout)
                verifier_delta = changed_paths_from_snapshot(root, verifier_baseline)

                if verifier_question:
                    if verifier_delta:
                        warn(
                            f"{pair} verifier emitted <question> after editing files in this phase; proceeding in lax guard mode."
                        )
                    if args.full_auto_answers:
                        answer = auto_answer_question(codex_command, root, paths["context_file"], verifier_question)
                        print(f"[+] Auto-answered verifier question: {answer}")
                    else:
                        answer = ask_human(verifier_question)
                    append_clarification(paths["context_file"], pair, "verifier", cycle_num, verifier_question, answer)
                    commit_tracked_changes(root, f"superloop: answered verifier question ({pair} #{cycle_num})", pair_tracked)
                    continue

                violations = verifier_scope_violations(pair, verifier_delta)
                if violations:
                    preview = ", ".join(violations[:8])
                    if len(violations) > 8:
                        preview += ", ..."
                    warn(
                        f"{pair} verifier edited files outside recommended scope (.superloop/{pair}/): {preview}. Continuing in lax guard mode."
                    )

                if not verifier_promise:
                    with feedback_file.open("a", encoding="utf-8") as f:
                        f.write(
                            f"\n\n## System Warning (cycle {cycle_num})\n"
                            "No promise tag found, defaulted to <promise>INCOMPLETE</promise>.\n"
                        )
                    verifier_promise = PROMISE_INCOMPLETE
                    verifier_delta.add(repo_relative_path(root, feedback_file))

                if verifier_promise == PROMISE_COMPLETE:
                    if not criteria_all_checked(criteria_file):
                        warn(
                            f"{pair} verifier emitted COMPLETE with unchecked criteria; downgrading to INCOMPLETE in lax guard mode."
                        )
                        verifier_promise = PROMISE_INCOMPLETE
                    verifier_delta.add(repo_relative_path(root, feedback_file))

                if verifier_promise == PROMISE_COMPLETE:
                    print(f"[SUCCESS] Pair `{pair}` completed.")
                    append_run_log(paths["run_log"], f"Completed pair `{pair}` in {cycle_num} cycles")
                    commit_paths(root, f"superloop: pair complete ({pair})", set(pair_tracked) | verifier_delta)
                    break

                if verifier_promise == PROMISE_BLOCKED:
                    append_run_log(paths["run_log"], f"Blocked in pair `{pair}` cycle {cycle_num}")
                    commit_paths(root, f"superloop: blocked ({pair} #{cycle_num})", set(pair_tracked) | verifier_delta)
                    print(f"[BLOCKED] Pair `{pair}` emitted BLOCKED.", file=sys.stderr)
                    sys.exit(2)

                # INCOMPLETE
                commit_paths(root, f"superloop: verifier feedback ({pair} #{cycle_num})", verifier_delta)
                cycle += 1
                time.sleep(2)
            else:
                append_run_log(paths["run_log"], f"Failed pair `{pair}` after max cycles")
                commit_paths(root, f"superloop: failed ({pair} max iterations)", [repo_relative_path(root, paths["run_log"])])
                print(f"[FAILED] Pair `{pair}` reached max iterations without COMPLETE.", file=sys.stderr)
                sys.exit(1)

        append_run_log(paths["run_log"], "All enabled pairs completed")
        commit_tracked_changes(root, "superloop: successful completion")
        print("\n[SUCCESS] All enabled pairs completed.")
        sys.exit(0)

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user. Shutting down gracefully...")
        sys.exit(130)


if __name__ == "__main__":
    main()
