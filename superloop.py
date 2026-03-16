#!/usr/bin/env python3
"""Superloop: strategy-to-execution multi-pair Codex orchestration.

Implements optional producer/verifier loops using the shared Doc-Loop loop-control
contract, with canonical <loop-control> JSON output and legacy tag compatibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from loop_control import (
    LoopControl,
    LoopControlParseError,
    PROMISE_BLOCKED,
    PROMISE_COMPLETE,
    PROMISE_INCOMPLETE,
    criteria_all_checked,
    parse_loop_control,
)

PAIR_ORDER = ["plan", "implement", "test"]

PAIR_LABELS = {
    "plan": "Plan ↔ Plan Verifier",
    "implement": "Implement ↔ Code Reviewer",
    "test": "Test Author ↔ Test Auditor",
}

PAIR_ARTIFACTS = {
    "plan": ["plan.md"],
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
Update `.superloop/plan/plan.md` as the single source of truth for the plan, including milestones, interface definitions, and risk register details in that one file.

Also append a concise entry to `.superloop/plan/feedback.md` with what changed and why.

## Rules
1. Analyze codebase areas and behaviors relevant to the current user request first. Broaden analysis scope when justified: cross-cutting patterns must be checked, dependencies are unclear, behavior may be reused elsewhere, or the repository/files are small enough that full analysis is cheaper and safer.
2. Check and verify your own plan for consistency, feasibility, DRY/KISS quality, and regression risk before writing files.
3. Keep the plan concrete and implementation-ready.
4. Apply KISS and DRY; avoid speculative complexity.
5. Do not edit `.superloop/plan/criteria.md` (verifier-owned).
6. If the user request is ambiguous, logically flawed, introduces breaking changes, may cause regressions, or may create hidden unintended behavior, warn the user via a clarifying question.
7. Every clarifying question must include your best suggestion/supposition so the user can confirm or correct quickly.
8. When asking a clarifying question, do not edit files and output exactly one canonical loop-control block as the last non-empty logical block:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"question","question":"Question text.","best_supposition":"..."}
</loop-control>
Legacy `<question>...</question>` remains supported for compatibility, but the canonical loop-control block is the default contract.
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
- `.superloop/plan/plan.md`

## Rules
1. Analyze request-relevant code paths and behavior before editing. Broaden analysis scope when justified: shared patterns may exist, dependencies are unclear, regressions could propagate across modules, or the repository/files are small enough that full analysis is simpler and safer.
2. Apply minimal, high-signal changes; keep KISS/DRY.
3. Resolve reviewer findings explicitly and avoid introducing unrelated refactors.
4. When you see duplicated logic that clearly adds technical debt, centralize it into a shared abstraction/module unless that would introduce unjustified complexity.
5. Before finalizing edits, check likely regression surfaces for touched behavior (interfaces, persisted data, compatibility, tests).
6. Map your edits to the implementation checklist in `.superloop/plan/plan.md` when present, and note any checklist item you intentionally defer.
7. Update `.superloop/implement/implementation_notes.md` with: files changed, checklist mapping, assumptions, expected side effects, and any deduplication/centralization decisions.
8. Do not edit `.superloop/implement/criteria.md` (reviewer-owned).
9. If ambiguity or intent gaps remain, or if a required change may introduce breaking behavior/regressions, ask a clarifying question with your best suggestion/supposition and do not edit files:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"question","question":"Question text.","best_supposition":"..."}
</loop-control>
Legacy `<question>...</question>` remains supported for compatibility, but the canonical loop-control block is the default contract.
10. Do not output any `<promise>...</promise>` tag.
""",
    "test": """# Superloop Test Author Instructions
You are the test authoring agent for this repository.

## Goal
Create or refine tests and fixtures to validate changed behavior and prevent regressions.

## Required outputs
- Update relevant test files in the repository.
- Update `.superloop/test/test_strategy.md` with an explicit behavior-to-test coverage map.
- Append a concise entry to `.superloop/test/feedback.md` summarizing test additions.

## Rules
1. Focus on changed/request-relevant behavior first; avoid unrelated test churn. Broaden analysis when justified to find shared test patterns, dependency impacts, or when repository/files are small enough that full inspection is more reliable.
2. Favor deterministic tests with stable setup/teardown.
3. For each changed behavior, include happy path, edge case, and failure-path coverage where relevant.
4. Call out flake risks (timing, network, nondeterministic ordering) and stabilization approach.
5. Do not edit `.superloop/test/criteria.md` (auditor-owned).
6. If blocked by missing intent, ask a clarifying question with your best suggestion/supposition and do not edit files:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"question","question":"Question text.","best_supposition":"..."}
</loop-control>
Legacy `<question>...</question>` remains supported for compatibility, but the canonical loop-control block is the default contract.
7. Do not output any `<promise>...</promise>` tag.
""",
}

PAIR_VERIFIER_PROMPT = {
    "plan": """# Superloop Plan Verifier Instructions
You are the plan verifier.

## Goal
Audit planning artifacts for correctness, completeness, regression risk, and KISS/DRY quality.

## Required actions
1. Update `.superloop/plan/criteria.md` checkboxes accurately.
2. Append prioritized findings to `.superloop/plan/feedback.md` with stable IDs (for example `PLAN-001`).
3. Label each finding as `blocking` or `non-blocking`.
4. End stdout with exactly one canonical loop-control block as the last non-empty logical block:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"COMPLETE"}
</loop-control>
or the same shape with `INCOMPLETE` / `BLOCKED`.

## Rules
- You may not edit repository source code.
- Focus on request-relevant and changed-scope plan sections first; justify any out-of-scope finding. Broaden analysis when cross-cutting patterns/dependencies or small-repo economics make wider review safer.
- A finding may be `blocking` only if it materially risks correctness, compatibility, hidden behavior changes, or implementation failure.
- For each `blocking` finding include evidence: affected section(s), concrete failure/conflict scenario, and minimal correction direction.
- Do not return `INCOMPLETE` if you have no blocking findings.
- Ask a canonical `<loop-control>` question block only when missing product intent makes safe verification impossible, and include best suggestion/supposition.
- If COMPLETE, every checkbox in criteria must be checked.
Legacy `<question>...</question>` and final-line `<promise>...</promise>` remain supported for compatibility, but canonical loop-control output is the default contract.
""",
    "implement": """# Superloop Code Reviewer Instructions
You are the code reviewer.

## Goal
Audit implementation diffs for correctness, architecture conformance, security, performance, and maintainability.

## Required actions
1. Update `.superloop/implement/criteria.md` checkboxes accurately.
2. Append prioritized review findings to `.superloop/implement/feedback.md` with stable IDs (for example `IMP-001`).
3. Label each finding as `blocking` or `non-blocking`.
4. End stdout with exactly one canonical loop-control block as the last non-empty logical block:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"COMPLETE"}
</loop-control>
or the same shape with `INCOMPLETE` / `BLOCKED`.

## Rules
- Do not modify non-`.superloop/` code files.
- Review changed/request-relevant scope first; justify any out-of-scope finding. Broaden analysis when shared patterns, uncertain dependencies, or small-repo economics justify wider inspection.
- A finding may be `blocking` only if it materially risks correctness, security, reliability, compatibility, required behavior coverage, or introduces avoidable duplicated logic that increases technical debt.
- Flag duplicated logic that should be centralized for DRY/KISS as a finding; treat it as `blocking` when duplication is substantial and likely to increase maintenance or inconsistency risk.
- Each `blocking` finding must include: file/symbol reference, concrete failure or regression (or maintainability debt) scenario, and minimal fix direction including centralization target when applicable.
- Do not return `INCOMPLETE` if you have no blocking findings.
- Ask a canonical `<loop-control>` question block only for missing product intent, and include best suggestion/supposition.
- If COMPLETE, criteria must have no unchecked boxes.
Legacy `<question>...</question>` and final-line `<promise>...</promise>` remain supported for compatibility, but canonical loop-control output is the default contract.
""",
    "test": """# Superloop Test Auditor Instructions
You are the test auditor.

## Goal
Audit tests for coverage quality, edge-case depth, and flaky-risk control.

## Required actions
1. Update `.superloop/test/criteria.md` checkboxes accurately.
2. Append prioritized audit findings to `.superloop/test/feedback.md` with stable IDs (for example `TST-001`).
3. Label each finding as `blocking` or `non-blocking`.
4. End stdout with exactly one canonical loop-control block as the last non-empty logical block:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"COMPLETE"}
</loop-control>
or the same shape with `INCOMPLETE` / `BLOCKED`.

## Rules
- Do not edit repository code except `.superloop/test/*` audit artifacts.
- Focus on changed/request-relevant behavior first; justify any out-of-scope finding. Broaden analysis when shared patterns, uncertain dependencies, or small-repo economics justify wider inspection.
- A finding may be `blocking` only if it materially risks regression detection, correctness coverage, or test reliability.
- Each `blocking` finding must include evidence: affected behavior/tests, concrete missed-regression scenario, and minimal correction direction.
- Low-confidence concerns should be non-blocking suggestions.
- Do not return `INCOMPLETE` if you have no blocking findings.
- Ask a canonical `<loop-control>` question block only for missing product intent, and include best suggestion/supposition.
- If COMPLETE, criteria must have no unchecked boxes.
Legacy `<question>...</question>` and final-line `<promise>...</promise>` remain supported for compatibility, but canonical loop-control output is the default contract.
""",
}


@dataclass(frozen=True)
class PairConfig:
    name: str
    enabled: bool
    max_iterations: int


@dataclass
class EventRecorder:
    run_id: str
    events_file: Path
    sequence: int = 0

    def emit(self, event_type: str, **fields):
        self.sequence += 1
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "seq": self.sequence,
            "event_type": event_type,
            **fields,
        }
        with self.events_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")


@dataclass(frozen=True)
class ResumeCheckpoint:
    pair_start_index: int
    cycle_by_pair: Dict[str, int]
    attempts_by_pair_cycle: Dict[Tuple[str, int], int]
    last_sequence: int


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


def allowed_verifier_paths(pair: str, task_root: str) -> List[str]:
    """Returns repo-relative paths a verifier is allowed to edit for a pair."""
    return [f"{task_root}/{pair}/"]


def verifier_scope_violations(pair: str, verifier_delta: Set[str], task_root: str) -> List[str]:
    """Returns verifier writes that are outside its allowed scope."""
    allowed = tuple(allowed_verifier_paths(pair, task_root))
    return sorted(path for path in verifier_delta if not path.startswith(allowed))


def tracked_superloop_paths(task_root: str, pair: Optional[str] = None) -> List[str]:
    """Returns paths that Superloop may stage/commit."""
    shared_paths = [
        f"{task_root}/context.md",
        f"{task_root}/task.json",
        f"{task_root}/run_log.md",
        f"{task_root}/raw_phase_log.md",
        f"{task_root}/runs/",
    ]
    if pair is None:
        pair_paths = [f"{task_root}/{name}/" for name in PAIR_ORDER]
    else:
        pair_paths = [f"{task_root}/{pair}/"]
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
    tracked = list(tracked_paths) if tracked_paths else []
    if not tracked:
        return False
    return commit_paths(root, message, tracked)


def check_dependencies(require_git: bool = True):
    missing = []
    if require_git and not shutil.which("git"):
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
    supports_bypass = "--dangerously-bypass-approvals-and-sandbox" in help_text
    supports_full_auto = "--full-auto" in help_text

    if supports_bypass:
        return [
            "codex",
            "exec",
            "--ephemeral",
            "--dangerously-bypass-approvals-and-sandbox",
            "--model",
            model,
            "-",
        ]

    if supports_full_auto:
        return [
            "codex",
            "exec",
            "--ephemeral",
            "--full-auto",
            "--model",
            model,
            "-",
        ]

    fatal(
        "[!] FATAL CODEX ERROR: This Superloop version requires `codex exec` support for "
        "either --dangerously-bypass-approvals-and-sandbox or --full-auto."
    )

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


def slugify_task(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:48] or "task"


def derive_intent_task_id(intent: str) -> str:
    slug = slugify_task(intent)
    digest = hashlib.sha1(intent.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}"


def render_task_prompt(template: str, task_root_rel: str) -> str:
    return template.replace(".superloop/", f"{task_root_rel}/")


def ensure_workspace(
    root: Path,
    task_id: str,
    product_intent: Optional[str],
    intent_mode: str,
) -> Dict[str, Path]:
    super_dir = root / ".superloop"
    super_dir.mkdir(parents=True, exist_ok=True)

    tasks_dir = super_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    task_dir = tasks_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    task_root_rel = repo_relative_path(root, task_dir)

    context_file = task_dir / "context.md"
    if not context_file.exists():
        starter = "# Product Context\n\n"
        if product_intent:
            starter += f"{product_intent.strip()}\n"
        else:
            starter += "Add business goals, constraints, and non-negotiable requirements here.\n"
        context_file.write_text(starter, encoding="utf-8")
    elif product_intent:
        if intent_mode == "replace":
            context_file.write_text(f"# Product Context\n\n{product_intent.strip()}\n", encoding="utf-8")
        elif intent_mode == "append":
            stamp = datetime.now(timezone.utc).isoformat()
            with context_file.open("a", encoding="utf-8") as f:
                f.write(f"\n\n## Run Intent ({stamp})\n{product_intent.strip()}\n")

    run_log = task_dir / "run_log.md"
    if not run_log.exists():
        run_log.write_text("# Superloop Run Log\n", encoding="utf-8")

    raw_phase_log = task_dir / "raw_phase_log.md"
    if not raw_phase_log.exists():
        raw_phase_log.write_text("# Superloop Raw Phase Log\n", encoding="utf-8")

    runs_dir = task_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    task_meta_file = task_dir / "task.json"
    if not task_meta_file.exists():
        task_meta_file.write_text(
            json.dumps(
                {
                    "task_id": task_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    pair_dirs: Dict[str, Path] = {}
    for pair in PAIR_ORDER:
        pair_dir = task_dir / pair
        pair_dir.mkdir(parents=True, exist_ok=True)
        pair_dirs[pair] = pair_dir

        prompt_file = pair_dir / "prompt.md"
        if not prompt_file.exists():
            prompt_file.write_text(render_task_prompt(PAIR_PRODUCER_PROMPT[pair], task_root_rel), encoding="utf-8")

        verifier_prompt_file = pair_dir / "verifier_prompt.md"
        if not verifier_prompt_file.exists():
            verifier_prompt_file.write_text(render_task_prompt(PAIR_VERIFIER_PROMPT[pair], task_root_rel), encoding="utf-8")

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
        "tasks_dir": tasks_dir,
        "task_dir": task_dir,
        "task_meta_file": task_meta_file,
        "task_root_rel": Path(task_root_rel),
        "task_id": task_id,
        "runs_dir": runs_dir,
        "context_file": context_file,
        "run_log": run_log,
        "raw_phase_log": raw_phase_log,
        **{f"pair_{k}": v for k, v in pair_dirs.items()},
    }


def create_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{timestamp}-{uuid4().hex[:8]}"


def create_run_paths(runs_dir: Path, run_id: str) -> Dict[str, Path]:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    run_log = run_dir / "run_log.md"
    run_log.write_text(f"# Superloop Run Log ({run_id})\n", encoding="utf-8")

    raw_phase_log = run_dir / "raw_phase_log.md"
    raw_phase_log.write_text(f"# Superloop Raw Phase Log ({run_id})\n", encoding="utf-8")

    events_file = run_dir / "events.jsonl"
    events_file.write_text("", encoding="utf-8")

    summary_file = run_dir / "summary.md"

    return {
        "run_dir": run_dir,
        "run_log": run_log,
        "raw_phase_log": raw_phase_log,
        "events_file": events_file,
        "summary_file": summary_file,
    }


def open_existing_run_paths(runs_dir: Path, run_id: str) -> Dict[str, Path]:
    run_dir = runs_dir / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        fatal(f"[!] FATAL: run_id not found under task runs/: {run_id}")

    run_log = run_dir / "run_log.md"
    raw_phase_log = run_dir / "raw_phase_log.md"
    events_file = run_dir / "events.jsonl"
    summary_file = run_dir / "summary.md"

    if not run_log.exists():
        run_log.write_text(f"# Superloop Run Log ({run_id})\n", encoding="utf-8")
    if not raw_phase_log.exists():
        raw_phase_log.write_text(f"# Superloop Raw Phase Log ({run_id})\n", encoding="utf-8")
    if not events_file.exists():
        events_file.write_text("", encoding="utf-8")

    return {
        "run_dir": run_dir,
        "run_log": run_log,
        "raw_phase_log": raw_phase_log,
        "events_file": events_file,
        "summary_file": summary_file,
    }


def run_codex_phase(
    codex_command: List[str],
    cwd: Path,
    prompt_file: Path,
    phase_name: str,
    pair_name: str,
    cycle_num: int,
    attempt_num: int,
    run_id: str,
    run_raw_phase_log: Path,
    raw_phase_log: Path,
) -> str:
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
    append_raw_phase_log(
        raw_phase_log,
        pair_name,
        phase_name,
        cycle_num,
        attempt_num,
        "codex-agent",
        stdout,
        run_id=run_id,
    )
    append_raw_phase_log(
        run_raw_phase_log,
        pair_name,
        phase_name,
        cycle_num,
        attempt_num,
        "codex-agent",
        stdout,
        run_id=run_id,
    )

    if process.returncode != 0:
        if stdout.strip():
            print(stdout.rstrip(), file=sys.stderr)
        fatal(f"\n[!] Codex CLI failed during {pair_name}:{phase_name} with exit code {process.returncode}.")
    return stdout




def append_raw_phase_log(
    raw_phase_log: Path,
    pair: str,
    phase: str,
    cycle: int,
    attempt: int,
    process_name: str,
    stdout: str,
    run_id: str,
):
    with raw_phase_log.open("a", encoding="utf-8") as f:
        f.write(
            "\n\n---\n"
            f"run_id={run_id} | pair={pair} | phase={phase} | process={process_name} | cycle={cycle} | attempt={attempt}\n"
            "---\n"
        )
        f.write(stdout if stdout else "[empty stdout]\n")

@dataclass(frozen=True)
class PhaseControlDecision:
    action: str
    warning: Optional[str] = None


def format_question(control: LoopControl) -> Optional[str]:
    if not control.question:
        return None
    if control.question.best_supposition:
        return (
            f"{control.question.text}\n"
            f"Best supposition: {control.question.best_supposition}"
        )
    return control.question.text


def parse_phase_control(stdout: str, phase_name: str, pair_name: str) -> LoopControl:
    try:
        return parse_loop_control(stdout)
    except LoopControlParseError as exc:
        fatal(
            f"[!] {pair_name} {phase_name} emitted malformed or conflicting loop-control output: {exc}"
        )


def decide_producer_control(control: LoopControl) -> PhaseControlDecision:
    if control.question:
        return PhaseControlDecision(action="question")
    if control.promise:
        return PhaseControlDecision(action="ignore_promise")
    return PhaseControlDecision(action="continue")


def decide_verifier_control(control: LoopControl, criteria_checked: bool) -> PhaseControlDecision:
    if control.question:
        return PhaseControlDecision(action="question")
    if not control.promise:
        return PhaseControlDecision(
            action="incomplete",
            warning="No promise tag found, defaulted to <promise>INCOMPLETE</promise>.",
        )
    if control.promise == PROMISE_COMPLETE and not criteria_checked:
        return PhaseControlDecision(
            action="incomplete",
            warning="verifier emitted COMPLETE with unchecked criteria; downgrading to INCOMPLETE in lax guard mode.",
        )
    if control.promise == PROMISE_COMPLETE:
        return PhaseControlDecision(action="complete")
    if control.promise == PROMISE_BLOCKED:
        return PhaseControlDecision(action="blocked")
    return PhaseControlDecision(action="incomplete")


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


def append_run_log(
    run_log: Path,
    message: str,
    run_id: str,
    pair: Optional[str] = None,
    cycle: Optional[int] = None,
    attempt: Optional[int] = None,
):
    scope_bits = [f"run_id={run_id}"]
    if pair is not None:
        scope_bits.append(f"pair={pair}")
    if cycle is not None:
        scope_bits.append(f"cycle={cycle}")
    if attempt is not None:
        scope_bits.append(f"attempt={attempt}")
    scope = " | ".join(scope_bits)
    with run_log.open("a", encoding="utf-8") as f:
        f.write(f"\n- {message} ({scope})\n")


def write_run_summary(summary_file: Path, run_id: str, events_file: Path):
    if not events_file.exists():
        summary_file.write_text(f"# Superloop Run Summary ({run_id})\n\nNo events recorded.\n", encoding="utf-8")
        return

    counters = {
        "phase_output_empty": 0,
        "missing_promise_default": 0,
        "question": 0,
        "blocked": 0,
        "pair_completed": 0,
        "pair_failed": 0,
    }

    invariant_violations: List[str] = []
    completed_pairs: Set[str] = set()

    with events_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            event_type = event.get("event_type")
            if event_type in counters:
                counters[event_type] += 1

            pair = event.get("pair")
            if pair and pair in completed_pairs and event_type not in {"pair_completed", "run_finished"}:
                invariant_violations.append(
                    f"Pair {pair} received event {event_type} after pair_completed (seq={event.get('seq')})."
                )

            if event_type == "pair_completed" and pair:
                completed_pairs.add(pair)

    summary = (
        f"# Superloop Run Summary ({run_id})\n\n"
        f"- phase_output_empty: {counters['phase_output_empty']}\n"
        f"- missing_promise_default: {counters['missing_promise_default']}\n"
        f"- question events: {counters['question']}\n"
        f"- blocked events: {counters['blocked']}\n"
        f"- pair_completed events: {counters['pair_completed']}\n"
        f"- pair_failed events: {counters['pair_failed']}\n"
    )
    if invariant_violations:
        summary += "\n## Invariant violations\n"
        for violation in invariant_violations:
            summary += f"- {violation}\n"
    summary_file.write_text(summary, encoding="utf-8")


def list_tasks(tasks_dir: Path) -> List[str]:
    if not tasks_dir.exists():
        return []
    return sorted([entry.name for entry in tasks_dir.iterdir() if entry.is_dir()])


def _parse_iso8601_utc(text: str) -> Optional[datetime]:
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text[:-1] + "+00:00")
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def latest_task_id(tasks_dir: Path) -> Optional[str]:
    if not tasks_dir.exists():
        return None
    tasks = [entry for entry in tasks_dir.iterdir() if entry.is_dir()]
    if not tasks:
        return None

    best: Optional[Tuple[datetime, str]] = None
    for task in tasks:
        created_at: Optional[datetime] = None
        task_meta = task / "task.json"
        if task_meta.exists():
            try:
                payload = json.loads(task_meta.read_text(encoding="utf-8"))
                raw_created = payload.get("created_at")
                if isinstance(raw_created, str):
                    created_at = _parse_iso8601_utc(raw_created)
            except (json.JSONDecodeError, OSError):
                created_at = None
        if created_at is None:
            created_at = datetime.min.replace(tzinfo=timezone.utc)

        candidate = (created_at, task.name)
        if best is None or candidate > best:
            best = candidate

    return best[1] if best else None


def _run_id_timestamp(run_id: str) -> Optional[datetime]:
    match = re.fullmatch(r"run-(\d{8}T\d{6}Z)-[0-9a-f]{8}", run_id)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def latest_run_id(runs_dir: Path) -> Optional[str]:
    if not runs_dir.exists():
        return None
    runs = [entry for entry in runs_dir.iterdir() if entry.is_dir()]
    if not runs:
        return None

    def run_sort_key(run_path: Path) -> Tuple[datetime, str]:
        parsed = _run_id_timestamp(run_path.name)
        if parsed is not None:
            return (parsed, run_path.name)

        events_file = run_path / "events.jsonl"
        if events_file.exists():
            try:
                with events_file.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        event = json.loads(line)
                        ts = event.get("ts")
                        if isinstance(ts, str):
                            parsed_ts = _parse_iso8601_utc(ts)
                            if parsed_ts is not None:
                                return (parsed_ts, run_path.name)
            except (OSError, json.JSONDecodeError):
                pass

        return (datetime.min.replace(tzinfo=timezone.utc), run_path.name)

    return max(runs, key=run_sort_key).name


def latest_run_status(events_file: Path) -> Optional[str]:
    if not events_file.exists():
        return None
    last_status: Optional[str] = None
    with events_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event.get("event_type") == "run_finished":
                status = event.get("status")
                if isinstance(status, str):
                    last_status = status
    return last_status


def task_id_for_run(tasks_dir: Path, run_id: str) -> Optional[str]:
    if not tasks_dir.exists():
        return None
    for task_dir in tasks_dir.iterdir():
        if not task_dir.is_dir():
            continue
        if (task_dir / "runs" / run_id).is_dir():
            return task_dir.name
    return None


def load_resume_checkpoint(events_file: Path, enabled_pairs: Sequence[str]) -> ResumeCheckpoint:
    attempts: Dict[Tuple[str, int], int] = {}
    max_cycle_by_pair: Dict[str, int] = {}
    completed_pairs: Set[str] = set()
    last_seq = 0

    if events_file.exists():
        with events_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                event_type = event.get("event_type")
                pair = event.get("pair")
                cycle = event.get("cycle")
                attempt = event.get("attempt")
                seq = event.get("seq")

                if isinstance(seq, int):
                    last_seq = max(last_seq, seq)
                if pair in enabled_pairs and isinstance(cycle, int):
                    max_cycle_by_pair[pair] = max(max_cycle_by_pair.get(pair, 0), cycle)
                    if isinstance(attempt, int):
                        key = (pair, cycle)
                        attempts[key] = max(attempts.get(key, 0), attempt)
                if event_type == "pair_completed" and pair in enabled_pairs:
                    completed_pairs.add(pair)

    pair_start_index = len(enabled_pairs)
    for idx, pair in enumerate(enabled_pairs):
        if pair not in completed_pairs:
            pair_start_index = idx
            break

    cycle_by_pair: Dict[str, int] = {}
    if pair_start_index < len(enabled_pairs):
        active_pair = enabled_pairs[pair_start_index]
        cycle_by_pair[active_pair] = max(0, max_cycle_by_pair.get(active_pair, 0) - 1)

    return ResumeCheckpoint(
        pair_start_index=pair_start_index,
        cycle_by_pair=cycle_by_pair,
        attempts_by_pair_cycle=attempts,
        last_sequence=last_seq,
    )


def resolve_task_id(task_id: Optional[str], intent: Optional[str]) -> str:
    if task_id:
        return slugify_task(task_id)
    if intent:
        return derive_intent_task_id(intent)
    fatal("[!] FATAL: Provide --task-id or --intent so Superloop can select a task workspace.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Superloop: optional strategy-to-execution Codex loop orchestration")
    parser.add_argument("--pairs", type=str, default="plan,implement,test", help="Comma list from: plan,implement,test")
    parser.add_argument("--max-iterations", type=int, default=15, help="Maximum verifier cycles per enabled pair")
    parser.add_argument("--model", type=str, default="gpt-5.4", help="Codex model")
    parser.add_argument("--workspace", type=str, default=".", help="Repository/workspace root")
    parser.add_argument("--intent", type=str, help="Optional initial product intent text")
    parser.add_argument("--task-id", type=str, help="Task workspace id/slug under .superloop/tasks")
    parser.add_argument(
        "--intent-mode",
        choices=["replace", "append", "preserve"],
        default="preserve",
        help="How --intent updates an existing task context",
    )
    parser.add_argument("--resume", action="store_true", help="Resume from an existing task/run state")
    parser.add_argument("--run-id", type=str, help="Run ID under .superloop/tasks/<task-id>/runs")
    parser.add_argument("--list-tasks", action="store_true", help="List existing .superloop task IDs and exit")
    parser.add_argument("--full-auto-answers", action="store_true", help="Auto-answer agent questions using an extra Codex pass")
    parser.add_argument("--no-git", action="store_true", help="Do not initialize git or create git commits/checkpoints")
    args = parser.parse_args()

    if args.max_iterations < 1:
        fatal("[!] FATAL: --max-iterations must be >= 1")

    root = Path(args.workspace).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        fatal(f"[!] FATAL: --workspace must be an existing directory: {root}")

    if args.list_tasks:
        tasks = list_tasks(root / ".superloop" / "tasks")
        if tasks:
            for task in tasks:
                print(task)
        else:
            print("(no tasks found)")
        return 0

    use_git = not args.no_git
    tasks_dir = root / ".superloop" / "tasks"
    if args.run_id and not args.resume:
        fatal("[!] FATAL: --run-id requires --resume.")

    if args.resume:
        if args.task_id:
            task_id = slugify_task(args.task_id)
        elif args.run_id:
            found_task = task_id_for_run(tasks_dir, args.run_id)
            if not found_task:
                fatal(f"[!] FATAL: Unable to resolve task for run_id: {args.run_id}")
            task_id = found_task
        else:
            resolved_latest_task = latest_task_id(tasks_dir)
            if resolved_latest_task is None:
                fatal("[!] FATAL: No existing tasks available to resume.")
            task_id = resolved_latest_task
    else:
        task_id = resolve_task_id(args.task_id, args.intent)
    run_id: Optional[str] = None
    run_paths: Optional[Dict[str, Path]] = None
    recorder: Optional[EventRecorder] = None
    run_status = "setup"
    exit_code = 1
    if use_git and not shutil.which("git"):
        warn("git is not installed; forcing --no-git mode.")
        use_git = False
    check_dependencies(require_git=use_git)
    codex_command = resolve_codex_exec_command(args.model)
    pair_configs = parse_pairs(args.pairs, args.max_iterations)

    if use_git:
        repo_exists = has_git_repo(root)
        if not repo_exists:
            print("[*] Initializing local Git repository...")
            run_git(["init"], cwd=root)
            run_git(["config", "user.name", "Superloop Agent"], cwd=root)
            run_git(["config", "user.email", "superloop@localhost"], cwd=root)

        ensure_git_commit_ready(root)
    paths = ensure_workspace(root, task_id, args.intent, args.intent_mode)
    task_root_rel = str(paths["task_root_rel"])
    task_scoped_paths = tracked_superloop_paths(task_root_rel)
    resume_checkpoint: Optional[ResumeCheckpoint] = None
    if args.resume:
        run_id = args.run_id or latest_run_id(paths["runs_dir"])
        if not run_id:
            fatal(f"[!] FATAL: No runs found to resume for task: {task_id}")
        run_paths = open_existing_run_paths(paths["runs_dir"], run_id)
        terminal_status = latest_run_status(run_paths["events_file"])
        if terminal_status in {"success", "blocked", "failed", "fatal_error", "interrupted"}:
            fatal(f"[!] FATAL: Refusing to resume terminal run {run_id} (status={terminal_status}).")
        enabled_pairs = [p.name for p in pair_configs if p.enabled]
        resume_checkpoint = load_resume_checkpoint(run_paths["events_file"], enabled_pairs)
        recorder = EventRecorder(run_id=run_id, events_file=run_paths["events_file"], sequence=resume_checkpoint.last_sequence)
    else:
        run_id = create_run_id()
        run_paths = create_run_paths(paths["runs_dir"], run_id)
        recorder = EventRecorder(run_id=run_id, events_file=run_paths["events_file"])
    run_status = "running"

    if use_git and not args.resume:
        commit_tracked_changes(root, "superloop: baseline", task_scoped_paths)

    print("\n[+] Starting Superloop")
    print(f"[*] Workspace root: {root}")
    print(f"[*] Task ID: {task_id}")
    print(f"[*] Task root: {task_root_rel}")
    print(f"[*] Enabled pairs: {', '.join([p.name for p in pair_configs if p.enabled])}")
    print(f"[*] Run ID: {run_id}")
    append_run_log(paths["run_log"], "Run resumed" if args.resume else "Run started", run_id=run_id)
    append_run_log(run_paths["run_log"], "Run resumed" if args.resume else "Run started", run_id=run_id)
    recorder.emit(
        "run_resumed" if args.resume else "run_started",
        workspace=str(root),
        pairs=[p.name for p in pair_configs if p.enabled],
        max_iterations=args.max_iterations,
        use_git=use_git,
        task_id=task_id,
        task_root=task_root_rel,
    )

    try:
        enabled_pair_index = -1
        for pair_cfg in pair_configs:
            if not pair_cfg.enabled:
                continue
            enabled_pair_index += 1
            if resume_checkpoint is not None and enabled_pair_index < resume_checkpoint.pair_start_index:
                continue

            pair = pair_cfg.name
            pair_dir = paths[f"pair_{pair}"]
            prompt_file = pair_dir / "prompt.md"
            verifier_prompt_file = pair_dir / "verifier_prompt.md"
            criteria_file = pair_dir / "criteria.md"
            feedback_file = pair_dir / "feedback.md"

            print(f"\n===== Pair: {PAIR_LABELS[pair]} =====")
            append_run_log(paths["run_log"], f"Started pair `{pair}`", run_id=run_id, pair=pair)
            append_run_log(run_paths["run_log"], f"Started pair `{pair}`", run_id=run_id, pair=pair)
            recorder.emit("pair_started", pair=pair)

            cycle = 0
            attempt_counts: Dict[int, int] = {}
            if resume_checkpoint is not None:
                cycle = resume_checkpoint.cycle_by_pair.get(pair, 0)
                for (attempt_pair, attempt_cycle), attempt_value in resume_checkpoint.attempts_by_pair_cycle.items():
                    if attempt_pair == pair:
                        attempt_counts[attempt_cycle] = attempt_value
            while cycle < pair_cfg.max_iterations:
                cycle_num = cycle + 1
                attempt_counts[cycle_num] = attempt_counts.get(cycle_num, 0) + 1
                attempt_num = attempt_counts[cycle_num]
                print(f"\n--- {pair} cycle {cycle_num}/{pair_cfg.max_iterations} ---")
                recorder.emit("cycle_started", pair=pair, cycle=cycle_num, attempt=attempt_num)
                pair_tracked = tracked_superloop_paths(task_root_rel, pair)
                if use_git:
                    commit_tracked_changes(root, f"superloop: pre-cycle snapshot ({pair} #{cycle_num})", pair_tracked)

                producer_baseline = phase_snapshot_ref(root) if use_git else None

                producer_stdout = run_codex_phase(
                    codex_command,
                    root,
                    prompt_file,
                    "producer",
                    pair,
                    cycle_num,
                    attempt_num,
                    run_id,
                    run_paths["raw_phase_log"],
                    paths["raw_phase_log"],
                )
                recorder.emit(
                    "phase_finished",
                    pair=pair,
                    phase="producer",
                    cycle=cycle_num,
                    attempt=attempt_num,
                    empty_output=(not producer_stdout.strip()),
                )
                if not producer_stdout.strip():
                    recorder.emit("phase_output_empty", pair=pair, phase="producer", cycle=cycle_num, attempt=attempt_num)
                    warn(f"{pair} producer returned empty stdout (cycle {cycle_num}, attempt {attempt_num}).")
                producer_control = parse_phase_control(producer_stdout, "producer", pair)
                producer_decision = decide_producer_control(producer_control)
                producer_delta = changed_paths_from_snapshot(root, producer_baseline) if use_git else set()

                if producer_decision.action == "question":
                    recorder.emit("question", pair=pair, phase="producer", cycle=cycle_num, attempt=attempt_num)
                    producer_question = format_question(producer_control)
                    if args.full_auto_answers:
                        answer = auto_answer_question(codex_command, root, paths["context_file"], producer_question)
                        print(f"[+] Auto-answered producer question: {answer}")
                    else:
                        answer = ask_human(producer_question)
                    append_clarification(paths["context_file"], pair, "producer", cycle_num, producer_question, answer)
                    if use_git:
                        commit_tracked_changes(root, f"superloop: answered producer question ({pair} #{cycle_num})", pair_tracked)
                    continue

                if producer_decision.action == "ignore_promise":
                    warn(
                        f"{pair} producer emitted <promise>{producer_control.promise}</promise>; ignoring because verifier controls completion."
                    )

                if use_git and producer_delta:
                    commit_paths(root, f"superloop: producer edits ({pair} #{cycle_num})", producer_delta)
                else:
                    if use_git:
                        print("[-] Producer made no changes.")
                    else:
                        print("[-] Change detection skipped in --no-git mode.")

                verifier_baseline = phase_snapshot_ref(root) if use_git else None

                verifier_stdout = run_codex_phase(
                    codex_command,
                    root,
                    verifier_prompt_file,
                    "verifier",
                    pair,
                    cycle_num,
                    attempt_num,
                    run_id,
                    run_paths["raw_phase_log"],
                    paths["raw_phase_log"],
                )
                recorder.emit(
                    "phase_finished",
                    pair=pair,
                    phase="verifier",
                    cycle=cycle_num,
                    attempt=attempt_num,
                    empty_output=(not verifier_stdout.strip()),
                )
                if not verifier_stdout.strip():
                    recorder.emit("phase_output_empty", pair=pair, phase="verifier", cycle=cycle_num, attempt=attempt_num)
                    warn(f"{pair} verifier returned empty stdout (cycle {cycle_num}, attempt {attempt_num}).")
                verifier_control = parse_phase_control(verifier_stdout, "verifier", pair)
                verifier_decision = decide_verifier_control(
                    verifier_control,
                    criteria_checked=criteria_all_checked(criteria_file),
                )
                verifier_delta = changed_paths_from_snapshot(root, verifier_baseline) if use_git else set()

                if verifier_decision.action == "question":
                    recorder.emit("question", pair=pair, phase="verifier", cycle=cycle_num, attempt=attempt_num)
                    verifier_question = format_question(verifier_control)
                    if args.full_auto_answers:
                        answer = auto_answer_question(codex_command, root, paths["context_file"], verifier_question)
                        print(f"[+] Auto-answered verifier question: {answer}")
                    else:
                        answer = ask_human(verifier_question)
                    append_clarification(paths["context_file"], pair, "verifier", cycle_num, verifier_question, answer)
                    if use_git:
                        commit_tracked_changes(root, f"superloop: answered verifier question ({pair} #{cycle_num})", pair_tracked)
                    continue

                violations = verifier_scope_violations(pair, verifier_delta, task_root_rel) if use_git else []
                if use_git and violations:
                    preview = ", ".join(violations[:8])
                    if len(violations) > 8:
                        preview += ", ..."
                    warn(
                        f"{pair} verifier edited files outside recommended scope ({task_root_rel}/{pair}/): {preview}. Continuing in lax guard mode."
                    )

                if verifier_control.promise is None:
                    recorder.emit("missing_promise_default", pair=pair, cycle=cycle_num, attempt=attempt_num)
                    with feedback_file.open("a", encoding="utf-8") as f:
                        f.write(
                            f"\n\n## System Warning (cycle {cycle_num})\n"
                            f"{verifier_decision.warning}\n"
                        )
                    verifier_delta.add(repo_relative_path(root, feedback_file))

                if verifier_control.promise == PROMISE_COMPLETE and verifier_decision.warning:
                    warn(f"{pair} {verifier_decision.warning}")
                    verifier_delta.add(repo_relative_path(root, feedback_file))

                if verifier_decision.action == "complete":
                    print(f"[SUCCESS] Pair `{pair}` completed.")
                    append_run_log(paths["run_log"], f"Completed pair `{pair}` in {cycle_num} cycles", run_id=run_id, pair=pair, cycle=cycle_num, attempt=attempt_num)
                    append_run_log(run_paths["run_log"], f"Completed pair `{pair}` in {cycle_num} cycles", run_id=run_id, pair=pair, cycle=cycle_num, attempt=attempt_num)
                    recorder.emit("pair_completed", pair=pair, cycle=cycle_num, attempt=attempt_num)
                    if use_git:
                        commit_paths(root, f"superloop: pair complete ({pair})", set(pair_tracked) | verifier_delta)
                    break

                if verifier_decision.action == "blocked":
                    append_run_log(paths["run_log"], f"Blocked in pair `{pair}` cycle {cycle_num}", run_id=run_id, pair=pair, cycle=cycle_num, attempt=attempt_num)
                    append_run_log(run_paths["run_log"], f"Blocked in pair `{pair}` cycle {cycle_num}", run_id=run_id, pair=pair, cycle=cycle_num, attempt=attempt_num)
                    recorder.emit("blocked", pair=pair, cycle=cycle_num, attempt=attempt_num)
                    if use_git:
                        commit_paths(root, f"superloop: blocked ({pair} #{cycle_num})", set(pair_tracked) | verifier_delta)
                    print(f"[BLOCKED] Pair `{pair}` emitted BLOCKED.", file=sys.stderr)
                    run_status = "blocked"
                    exit_code = 2
                    return exit_code

                # INCOMPLETE
                if use_git:
                    commit_paths(root, f"superloop: verifier feedback ({pair} #{cycle_num})", verifier_delta)
                else:
                    print("[-] Change detection skipped in --no-git mode.")
                cycle += 1
                time.sleep(2)
            else:
                append_run_log(paths["run_log"], f"Failed pair `{pair}` after max cycles", run_id=run_id, pair=pair)
                append_run_log(run_paths["run_log"], f"Failed pair `{pair}` after max cycles", run_id=run_id, pair=pair)
                recorder.emit("pair_failed", pair=pair)
                if use_git:
                    commit_paths(root, f"superloop: failed ({pair} max iterations)", [repo_relative_path(root, paths["run_log"])])
                print(f"[FAILED] Pair `{pair}` reached max iterations without COMPLETE.", file=sys.stderr)
                run_status = "failed"
                exit_code = 1
                return exit_code

        append_run_log(paths["run_log"], "All enabled pairs completed", run_id=run_id)
        append_run_log(run_paths["run_log"], "All enabled pairs completed", run_id=run_id)
        if use_git:
            commit_tracked_changes(root, "superloop: successful completion", task_scoped_paths)
        print("\n[SUCCESS] All enabled pairs completed.")
        run_status = "success"
        exit_code = 0
        return exit_code

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user. Shutting down gracefully...")
        run_status = "interrupted"
        exit_code = 130
        return exit_code
    except SystemExit as exc:
        if isinstance(exc.code, int):
            exit_code = exc.code
        else:
            exit_code = 1
        if run_status == "running":
            run_status = "fatal_error"
        return exit_code
    finally:
        if recorder is not None and run_paths is not None and run_id is not None and run_status != "setup":
            recorder.emit("run_finished", status=run_status, exit_code=exit_code)
            write_run_summary(run_paths["summary_file"], run_id, run_paths["events_file"])


if __name__ == "__main__":
    sys.exit(main())
