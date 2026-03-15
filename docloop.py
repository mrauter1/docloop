#!/usr/bin/env python3
"""
Doc-Loop: A minimal, zero-state CLI orchestrator for iterative document refinement.
Architecture: Native I/O Edition (Ralph-style outer loop).

Delegates all cognitive work and file-editing to the official OpenAI Codex CLI.
Requires: 'git' and 'codex' CLI installed and available in your PATH.
"""

import argparse
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set

# --- Default Templates ---
DEFAULT_PROMPT = """# Doc-Loop Writer Instructions

You are the writer agent. Refine the target document until the verifier can pass every criterion.

## Working Set
- `TARGET DOCUMENT`: the spec to improve
- `.docloop/context.md`: source-of-truth requirements, constraints, and clarifications
- `.docloop/criteria.md`: completion gates
- `.docloop/progress.txt`: append-only handoff log, including verifier feedback

## Rules
1. Read the target document, context, progress, and criteria before editing.
2. Treat `.docloop/context.md` as the source of truth for product intent. Do not invent product-significant behavior that is not supported by the context or the document.
3. Treat the latest verifier feedback in `.docloop/progress.txt` as the immediate work queue unless it conflicts with `.docloop/context.md`.
4. Edit the target document in place to make it clearer, more complete, and more implementation-ready.
5. Prefer explicit contracts over aspirational prose. Define workflows, interfaces, data shapes, states, failure handling, edge cases, and non-functional constraints when a competent implementer would otherwise have to guess or could reasonably make conflicting choices.
6. Prefer general rules over repeated case-by-case restatement when the general rule fully determines the outcome without additional interpretation. If the rule does not fully determine the outcome, add the missing contract.
7. Keep the document internally consistent and avoid duplicate requirements. Give each requirement or contract one canonical home and use cross-references elsewhere when that improves clarity.
8. Do not remove or omit details that affect externally observable behavior, persisted artifacts, interoperability, security, compatibility, migration, concurrency, recovery, or other implementation-critical contracts. Those details are part of the architecture when they change what a conforming implementation must do.
9. Avoid overspecifying one implementation strategy when multiple implementations could satisfy the same contract. Internal algorithmic choices, code structure, and purely local sequencing should stay out of the document unless they are required for correctness or observability.
10. If the verifier requests an inline expansion of something an existing rule already determines completely, prefer strengthening that rule or adding a cross-reference rather than duplicating the same requirement in multiple places. Explain that choice briefly in your progress log entry.
11. Do not edit `.docloop/criteria.md`.
12. Append a concise writer log entry to `.docloop/progress.txt`. Do not overwrite it.

## Ask A Question
If you would need to invent product behavior, external interfaces, data contracts, acceptance criteria, or operational rules to continue safely, do not edit any files. Output:
<question>Ask your clarifying question here</question>

Do not output any `<promise>...</promise>` tag. The verifier decides completion.
"""

DEFAULT_VERIFIER_PROMPT = """# Doc-Loop Verifier Instructions

You are the verifier agent. Evaluate whether the target document is implementation-ready using the full workspace context. Your job has two equally important sides: ensure the document is complete enough to implement correctly, and ensure it does not drift into unnecessary redundancy or non-normative implementation detail.

## Working Set
- `TARGET DOCUMENT`: the spec under review
- `.docloop/context.md`: source-of-truth requirements, constraints, and clarifications
- `.docloop/criteria.md`: completion gates you must maintain
- `.docloop/progress.txt`: append-only handoff log for the writer

## Rules
1. Read the target document, context, progress, and criteria before deciding anything.
2. Use the full context. Do not ignore prior human clarifications or prior verifier findings.
3. Do not edit the target document or `.docloop/context.md`.
4. Update `.docloop/criteria.md` so each box accurately reflects the current target document state, including the economy and abstraction criteria.
5. If the document does not pass, append clear, actionable feedback to `.docloop/progress.txt` for the writer. Name what is missing, ambiguous, contradictory, redundant, or overspecified, and explain how the document must change.
6. Feedback must be specific enough that the writer can act on it without guessing. Prefer concrete gaps and expected additions over generic statements like "be clearer".
7. Before requesting more detail, check whether an existing general rule already determines the correct behavior without additional interpretation. If it does, accept the general rule or ask for a clarification to that rule instead of demanding case-by-case duplication.
8. Only flag a gap when you can describe at least one concrete wrong implementation or at least two plausible conflicting implementations that a competent engineer could produce from the current document.
9. Treat redundancy as a real defect when a passage adds no new normative information and increases contradiction risk. Do not treat a cross-reference, a concise summary, or a clearly informative example as a defect.
10. Do not flag detail as "too low-level" merely because it is specific. Detail is architecturally relevant when it affects externally observable behavior, persisted state, failure classification, recovery semantics, interoperability, security, migration, compatibility, or other implementation-critical contracts.
11. Flag detail for removal only when it prescribes one possible internal algorithm, code structure, or local sequencing that other conforming implementations could vary without changing the contract.

## Ask A Question
If reliable verification is blocked because the human has not provided necessary product intent or constraints, do not edit any files. Output:
<question>Ask your clarifying question here</question>

## Completion
If every box in `.docloop/criteria.md` is checked, no further writer edits are needed, and the document is implementation-ready, end your response with this exact last non-empty line:
<promise>COMPLETE</promise>

If the document is not complete but the writer can continue productively, update `.docloop/criteria.md` and `.docloop/progress.txt`, then end your response with this exact last non-empty line:
<promise>INCOMPLETE</promise>

If you cannot proceed safely because the context is contradictory, missing, or too ambiguous for another writer pass to help, prefer asking a `<question>` first. If no single clarifying question can safely unblock the work, update `.docloop/criteria.md` and `.docloop/progress.txt`, then end your response with this exact last non-empty line:
<promise>BLOCKED</promise>
"""

DEFAULT_UPDATE_PROMPT = """# Doc-Loop Update Writer Instructions

You are the update writer agent. Apply the requested changes to the target document while preserving unrelated requirements and avoiding regressions.

## Working Set
- `TARGET DOCUMENT`: the spec to update
- `.docloop/context.md`: source-of-truth requirements, constraints, and clarifications
- `.docloop/update_request.md`: the requested updates for this run
- `.docloop/update_baseline.md`: frozen pre-update baseline to preserve unless the update request changes it
- `.docloop/update_criteria.md`: completion gates for update mode
- `.docloop/progress.txt`: append-only handoff log, including verifier feedback

## Rules
1. Read the target document, context, update request, baseline, progress, and criteria before editing.
2. Treat `.docloop/update_request.md` and `.docloop/context.md` as the source of truth for requested change intent.
3. Treat `.docloop/update_baseline.md` as the source of truth for unchanged behavior and contracts that must be preserved unless the update request explicitly changes them.
4. Make the smallest sufficient edits that fully apply the request without weakening unrelated requirements.
5. If the requested update is breaking, can introduce regressions, or changes the meaning of an existing contract, make that impact explicit in the target document.
6. Prefer integrating changes into existing canonical rules over adding parallel clauses that restate the same behavior. If the update needs a new exception or rule, place it where implementers would naturally look first.
7. Do not remove or omit detail that affects externally observable behavior, persisted artifacts, interoperability, security, compatibility, migration, concurrency, recovery, or other implementation-critical contracts touched by the update.
8. Avoid introducing implementation-specific algorithm choices, local sequencing, or code-structure guidance unless the update request or existing document makes those details part of the contract.
9. Treat the latest verifier feedback in `.docloop/progress.txt` as the immediate work queue unless it conflicts with `.docloop/context.md` or `.docloop/update_request.md`.
10. If the verifier requests inline expansion of something already covered by a general rule, prefer strengthening that rule or adding a cross-reference rather than duplicating the same contract. Explain that choice briefly in your progress log entry.
11. Do not edit `.docloop/update_criteria.md`, `.docloop/update_request.md`, or `.docloop/update_baseline.md`.
12. Append a concise writer log entry to `.docloop/progress.txt`. Do not overwrite it.

## Ask A Question
If the requested changes are breaking, ambiguous, likely to introduce regression bugs, or can clearly be misunderstood, and you cannot resolve them safely from the update request, context, or baseline, do not edit any files. Output:
<question>
Question: Ask your clarifying question here
Best supposition: State your best current assumption right beside this question
</question>

Every question must include its best supposition immediately beside it.
Do not output any `<promise>...</promise>` tag. The verifier decides completion.
"""

DEFAULT_UPDATE_VERIFIER_PROMPT = """# Doc-Loop Update Verifier Instructions

You are the update verifier agent. Verify that the requested updates were applied correctly using the full workspace context and the frozen baseline. Your job has two equally important sides: ensure the requested changes are complete and regression-free, and ensure the update does not introduce unnecessary redundancy or non-normative implementation detail.

## Working Set
- `TARGET DOCUMENT`: the updated spec under review
- `.docloop/context.md`: source-of-truth requirements, constraints, and clarifications
- `.docloop/update_request.md`: the requested updates for this run
- `.docloop/update_baseline.md`: frozen pre-update baseline to compare against for regressions
- `.docloop/update_criteria.md`: completion gates you must maintain
- `.docloop/progress.txt`: append-only handoff log for the writer

## Rules
1. Read the target document, context, update request, baseline, progress, and criteria before deciding anything.
2. Use the full context. Do not ignore prior human clarifications or prior verifier findings.
3. Verify both sides of the change: requested updates must be applied, and unrelated baseline behavior must not regress unless the request explicitly changes it.
4. Do not edit the target document, `.docloop/context.md`, `.docloop/update_request.md`, or `.docloop/update_baseline.md`.
5. Update `.docloop/update_criteria.md` so each box accurately reflects the current target document state, including the economy and abstraction criteria.
6. If the document does not pass, append clear, actionable feedback to `.docloop/progress.txt` for the writer. Name the missing requested change, regression risk, ambiguity, contradiction, redundancy, or overspecification, and explain exactly how the document must change.
7. Feedback must be specific enough that the writer can act on it without guessing.
8. Before requesting more detail, check whether an existing general rule already determines the updated behavior without additional interpretation. If it does, accept the rule or ask for a clarification to that rule instead of demanding duplicated enumeration.
9. Only flag a gap when you can describe at least one concrete wrong implementation or at least two plausible conflicting implementations that a competent engineer could produce from the current document and baseline.
10. Treat redundancy as a defect when the update adds no new normative information and increases contradiction or maintenance risk. Do not treat a cross-reference, a concise summary, or a clearly informative example as a defect.
11. Do not flag detail as "too low-level" merely because it is specific. Detail remains part of the contract when it affects externally observable behavior, persisted state, regression safety, recovery semantics, interoperability, security, migration, compatibility, or other implementation-critical outcomes touched by the update.
12. Flag update-added detail for removal only when it prescribes one possible internal algorithm, code structure, or local sequencing that other conforming implementations could vary without changing the contract.

## Ask A Question
If reliable verification is blocked because the requested change is breaking, ambiguous, likely to introduce regressions, or can clearly be misunderstood, do not edit any files. Output:
<question>
Question: Ask your clarifying question here
Best supposition: State your best current assumption right beside this question
</question>

Every question must include its best supposition immediately beside it.

## Completion
If every box in `.docloop/update_criteria.md` is checked, the requested changes are applied, no unintended regressions remain, and no further edits are needed, end your response with this exact last non-empty line:
<promise>COMPLETE</promise>

If the update is not complete but the writer can continue productively, update `.docloop/update_criteria.md` and `.docloop/progress.txt`, then end your response with this exact last non-empty line:
<promise>INCOMPLETE</promise>

If you cannot proceed safely because the request or context is contradictory, missing, or too ambiguous for another writer pass to help, prefer asking a `<question>` first. If no single clarifying question can safely unblock the work, update `.docloop/update_criteria.md` and `.docloop/progress.txt`, then end your response with this exact last non-empty line:
<promise>BLOCKED</promise>
"""

DEFAULT_CRITERIA = """# Document Verification Criteria
Check these boxes (`- [x]`) only when the target document itself satisfies the rule.

## Completeness
- [ ] **Implementation-Ready Scope**: The document defines the system purpose, major components, responsibilities, and boundaries clearly enough that an autonomous coding agent would not need to invent the overall design.
- [ ] **Behavior Completeness**: The main flows, edge cases, failure modes, and recovery behavior that materially affect implementation are specified or explicitly declared out of scope.
- [ ] **Interface & Data Contracts**: Every interface, data shape, persisted entity, protocol, file format, and integration needed for implementation is defined with enough precision to code against.
- [ ] **Operational Constraints**: Relevant runtime constraints are stated clearly, including performance, security, observability, configuration, deployment assumptions, and other non-functional requirements that affect implementation.

## Clarity
- [ ] **Ambiguity Control**: The document contains no unresolved placeholders such as TBD/TODO/??? and no materially ambiguous language that would force an implementer to guess.
- [ ] **Internal Consistency**: Sections, examples, tables, and terminology do not contradict each other.

## Economy
- [ ] **Single Source of Truth**: Each requirement or contract has one canonical home. Cross-references, concise summaries, and clearly informative examples are acceptable, but duplicate passages that add no new normative information should not exist.
- [ ] **Appropriate Abstraction Level**: The document specifies contracts, invariants, externally relevant states, interactions, observable artifacts, and constraints without overspecifying one internal implementation strategy. Detail that affects external behavior, persisted state, failure handling, recovery, security, compatibility, migration, or interoperability counts as part of the contract and must be stated when needed.
"""

UPDATE_CRITERIA = """# Update Verification Criteria
Check these boxes (`- [x]`) only when the target document itself satisfies the rule for this update request.

## Completeness
- [ ] **Requested Changes Applied**: Every requested change in `.docloop/update_request.md` is reflected in the target document clearly and completely.
- [ ] **No Unintended Regression Against Baseline**: Requirements and contracts from `.docloop/update_baseline.md` that were not meant to change are still present and compatible, or any removal/change is explicitly justified by the update request.
- [ ] **Breaking Change Handling**: Any breaking change, compatibility impact, migration need, or behavior removal introduced by the update is stated explicitly enough that implementers will not miss it.
- [ ] **Interface & Data Contracts**: Every interface, data shape, persisted entity, protocol, file format, and integration touched by the update is defined with enough precision to code against.
- [ ] **Operational Constraints**: Relevant runtime constraints introduced or affected by the update are stated clearly, including performance, security, observability, configuration, deployment assumptions, and other non-functional requirements that affect implementation.

## Clarity
- [ ] **Ambiguity Control**: The updated document contains no unresolved placeholders such as TBD/TODO/??? and no materially ambiguous language that would force an implementer to guess, especially around the requested changes.
- [ ] **Internal Consistency**: Updated sections, unchanged sections, examples, tables, and terminology do not contradict each other.

## Economy
- [ ] **Single Source of Truth**: Updated requirements and contracts have one canonical home. Cross-references, concise summaries, and clearly informative examples are acceptable, but the update must not introduce duplicate passages that add no new normative information.
- [ ] **Appropriate Abstraction Level**: The update preserves contract-level detail and does not introduce unnecessary implementation-specific algorithm choices, local sequencing, or code-structure guidance. Detail that affects external behavior, persisted state, failure handling, recovery, security, compatibility, migration, or interoperability remains part of the contract and must stay explicit when needed.
"""

DEFAULT_CONTEXT = """# Context and Requirements

Describe the product intent and implementation-critical constraints here.

Suggested topics:
- users or actors
- core workflows
- inputs and outputs
- integrations and data sources
- non-functional requirements
- explicit out-of-scope boundaries
"""


@dataclass(frozen=True)
class Workspace:
    """Paths Doc-Loop owns for one target document."""

    root: Path
    target_doc: Path
    docloop_dir: Path
    prompt_file: Path
    verifier_prompt_file: Path
    update_prompt_file: Path
    update_verifier_prompt_file: Path
    criteria_file: Path
    update_criteria_file: Path
    progress_file: Path
    context_file: Path
    update_request_file: Path
    update_baseline_file: Path


@dataclass(frozen=True)
class RunMode:
    """Files Doc-Loop should use for the current run mode."""

    name: str
    writer_prompt_file: Path
    verifier_prompt_file: Path
    criteria_file: Path


PROMISE_COMPLETE = "COMPLETE"
PROMISE_INCOMPLETE = "INCOMPLETE"
PROMISE_BLOCKED = "BLOCKED"
PROMISE_LINE_RE = re.compile(
    r"^\s*<promise>(COMPLETE|INCOMPLETE|BLOCKED)</promise>\s*$",
    re.IGNORECASE,
)

def fatal(message: str, exit_code: int = 1):
    """Prints a fatal error and exits immediately."""
    print(message, file=sys.stderr)
    sys.exit(exit_code)


def warn(message: str):
    """Prints a non-fatal warning."""
    print(f"[!] WARNING: {message}", file=sys.stderr)

def check_dependencies(require_git: bool = True):
    """Fails fast if required CLI tools are missing."""
    missing = []
    if require_git and not shutil.which("git"):
        missing.append("git")
    if not shutil.which("codex"):
        missing.append("codex (install via 'npm i -g @openai/codex')")
    
    if missing:
        fatal(f"[!] FATAL: Missing required dependencies: {', '.join(missing)}")

def run_git(
    args: List[str],
    cwd: Path,
    allow_fail: bool = False
) -> subprocess.CompletedProcess[str]:
    """Executes a git command and returns the completed process."""
    res = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    if res.returncode != 0 and not allow_fail:
        fatal(f"[!] FATAL GIT ERROR: {' '.join(args)}\n{res.stderr.strip()}")
    return res

def git_stdout(args: List[str], cwd: Path, allow_fail: bool = False) -> str:
    """Returns stripped stdout from a git command."""
    return run_git(args, cwd=cwd, allow_fail=allow_fail).stdout.strip()

def has_git_repo(root: Path) -> bool:
    """Returns True when the workspace root lives inside a git repository."""
    probe = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    return probe.returncode == 0

def tracked_paths(workspace: Workspace) -> List[str]:
    """Returns the tracked paths Doc-Loop owns."""
    return [workspace.target_doc.name, workspace.docloop_dir.name]

def stage_tracked_files(workspace: Workspace):
    """Stages only the target document and .docloop state."""
    run_git(["add", "--", *tracked_paths(workspace)], cwd=workspace.root)

def tracked_status(workspace: Workspace) -> str:
    """Returns porcelain status for the tracked Doc-Loop paths."""
    return git_stdout(
        ["status", "--porcelain", "--", *tracked_paths(workspace)],
        cwd=workspace.root
    )

def tracked_files_changed(workspace: Workspace) -> bool:
    """Returns True when tracked Doc-Loop files have staged or unstaged changes."""
    return bool(tracked_status(workspace))

def changed_tracked_paths(workspace: Workspace) -> Set[str]:
    """Returns tracked paths with unstaged or staged changes."""
    changed: Set[str] = set()
    for line in tracked_status(workspace).splitlines():
        if len(line) < 4:
            continue
        path_text = line[3:].strip()
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        changed.add(path_text)
    return changed

def commit_tracked_changes(workspace: Workspace, message: str) -> bool:
    """Commits tracked Doc-Loop changes when there is something to commit."""
    stage_tracked_files(workspace)
    if not tracked_files_changed(workspace):
        return False
    run_git(["commit", "-m", message], cwd=workspace.root)
    return True

def ensure_git_commit_ready(root: Path):
    """Fails fast if this repository cannot create commits."""
    author = run_git(["var", "GIT_AUTHOR_IDENT"], cwd=root, allow_fail=True)
    committer = run_git(["var", "GIT_COMMITTER_IDENT"], cwd=root, allow_fail=True)

    if author.returncode != 0 or committer.returncode != 0:
        details = author.stderr.strip() or committer.stderr.strip() or "Configure user.name and user.email for this repository."
        fatal(f"[!] FATAL GIT ERROR: Unable to determine a valid git author identity.\n{details}")

def resolve_codex_exec_command(model: str) -> List[str]:
    """Builds the Codex exec command and verifies required automation flags."""
    help_result = subprocess.run(
        ["codex", "exec", "--help"],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )

    if help_result.returncode != 0:
        details = help_result.stderr.strip() or help_result.stdout.strip() or "Unable to inspect `codex exec --help`."
        fatal(f"[!] FATAL CODEX ERROR: {details}")

    help_text = f"{help_result.stdout}\n{help_result.stderr}"

    missing_flags = [flag for flag in ("--full-auto", "--dangerously-bypass-approvals-and-sandbox") if flag not in help_text]
    if missing_flags:
        fatal(
            "[!] FATAL CODEX ERROR: This Doc-Loop version requires `codex exec` support for: "
            + ", ".join(missing_flags)
        )

    return [
        "codex",
        "exec",
        "--ephemeral",
        "--full-auto",
        "--dangerously-bypass-approvals-and-sandbox",
        "--model",
        model,
        "-",
    ]

def resolve_output_target(doc_type: str, output_arg: Optional[str]) -> Path:
    """Resolves the target document path from the CLI output flag."""
    if not output_arg:
        return Path.cwd() / f"{doc_type}.md"

    output_path = Path(output_arg).expanduser()
    treat_as_dir = (
        output_arg.endswith(("/", "\\"))
        or (output_path.exists() and output_path.is_dir())
        or (not output_path.exists() and output_path.suffix == "")
    )

    if treat_as_dir:
        return output_path / f"{doc_type}.md"

    return output_path

def build_workspace(target_doc: Path) -> Workspace:
    """Builds the workspace path set for the selected output target."""
    resolved_target = target_doc.expanduser()
    if not resolved_target.is_absolute():
        resolved_target = (Path.cwd() / resolved_target).resolve()
    else:
        resolved_target = resolved_target.resolve()

    root = resolved_target.parent
    docloop_dir = root / ".docloop"
    return Workspace(
        root=root,
        target_doc=resolved_target,
        docloop_dir=docloop_dir,
        prompt_file=docloop_dir / "prompt.md",
        verifier_prompt_file=docloop_dir / "verifier_prompt.md",
        update_prompt_file=docloop_dir / "update_prompt.md",
        update_verifier_prompt_file=docloop_dir / "update_verifier_prompt.md",
        criteria_file=docloop_dir / "criteria.md",
        update_criteria_file=docloop_dir / "update_criteria.md",
        progress_file=docloop_dir / "progress.txt",
        context_file=docloop_dir / "context.md",
        update_request_file=docloop_dir / "update_request.md",
        update_baseline_file=docloop_dir / "update_baseline.md",
    )

def select_run_mode(workspace: Workspace, update_mode: bool) -> RunMode:
    """Returns the prompt and criteria files for the selected run mode."""
    if update_mode:
        return RunMode(
            name="update",
            writer_prompt_file=workspace.update_prompt_file,
            verifier_prompt_file=workspace.update_verifier_prompt_file,
            criteria_file=workspace.update_criteria_file,
        )

    return RunMode(
        name="refine",
        writer_prompt_file=workspace.prompt_file,
        verifier_prompt_file=workspace.verifier_prompt_file,
        criteria_file=workspace.criteria_file,
    )

def load_input_text(input_text: Optional[str], input_file: Optional[str]) -> Optional[str]:
    """Loads optional target-document seed content from text or a file."""
    if input_text is not None:
        return input_text

    if input_file is None:
        return None

    source_path = Path(input_file).expanduser()
    if not source_path.exists():
        fatal(f"[!] FATAL: Input file does not exist: {source_path}")
    if source_path.is_dir():
        fatal(f"[!] FATAL: Input file must be a file, not a directory: {source_path}")

    try:
        return source_path.read_text(encoding='utf-8')
    except OSError as exc:
        fatal(f"[!] FATAL: Unable to read input file {source_path}: {exc}")

def default_target_text(target_doc: Path) -> str:
    """Returns the starter text for a missing target document."""
    return f"# {target_doc.stem}\n\nDraft starting point...\n"

def default_context_text(seed_target: bool) -> str:
    """Returns the starter context for the workspace."""
    if seed_target:
        return (
            "# Context and Requirements\n\n"
            "The target document was seeded from CLI input. "
            "Add any missing implementation-critical constraints here, such as users, workflows, integrations, non-functional requirements, and explicit out-of-scope boundaries.\n"
        )

    return DEFAULT_CONTEXT

def init_workspace(
    workspace: Workspace,
    target_seed: Optional[str],
    run_mode: RunMode,
    update_text: Optional[str],
    use_git: bool = True,
) -> Path:
    """Initializes the minimal filesystem-as-memory architecture."""
    workspace.root.mkdir(parents=True, exist_ok=True)
    repo_exists = has_git_repo(workspace.root) if use_git else False

    if use_git and repo_exists:
        ensure_git_commit_ready(workspace.root)
    
    if not workspace.docloop_dir.exists():
        print(f"[*] Initializing Doc-Loop workspace for target: {workspace.target_doc.name}")
        workspace.docloop_dir.mkdir()

    if run_mode.name == "update" and target_seed is None and not workspace.target_doc.exists():
        fatal(f"[!] FATAL: Update mode requires an existing target document or an input seed: {workspace.target_doc}")

    if target_seed is not None:
        print(f"[*] Writing CLI input to target document: {workspace.target_doc}")
        workspace.target_doc.write_text(target_seed, encoding='utf-8')
    elif not workspace.target_doc.exists():
        workspace.target_doc.write_text(default_target_text(workspace.target_doc), encoding='utf-8')
    if not workspace.prompt_file.exists():
        workspace.prompt_file.write_text(DEFAULT_PROMPT, encoding='utf-8')
    if not workspace.verifier_prompt_file.exists():
        workspace.verifier_prompt_file.write_text(DEFAULT_VERIFIER_PROMPT, encoding='utf-8')
    if not workspace.update_prompt_file.exists():
        workspace.update_prompt_file.write_text(DEFAULT_UPDATE_PROMPT, encoding='utf-8')
    if not workspace.update_verifier_prompt_file.exists():
        workspace.update_verifier_prompt_file.write_text(DEFAULT_UPDATE_VERIFIER_PROMPT, encoding='utf-8')
    if not workspace.criteria_file.exists():
        workspace.criteria_file.write_text(DEFAULT_CRITERIA, encoding='utf-8')
    if not workspace.update_criteria_file.exists():
        workspace.update_criteria_file.write_text(UPDATE_CRITERIA, encoding='utf-8')
    if not workspace.progress_file.exists():
        workspace.progress_file.write_text("## Doc-Loop Progress Log\n\n", encoding='utf-8')
    if not workspace.context_file.exists():
        workspace.context_file.write_text(default_context_text(target_seed is not None), encoding='utf-8')
    if update_text is not None:
        workspace.update_request_file.write_text(
            "# Requested Update\n\n"
            f"{update_text.strip()}\n",
            encoding='utf-8'
        )
        workspace.update_baseline_file.write_text(
            workspace.target_doc.read_text(encoding='utf-8'),
            encoding='utf-8'
        )

    if use_git and not repo_exists:
        print("[*] Initializing local Git repository...")
        run_git(["init"], cwd=workspace.root)
        # Ensure a local git identity exists so commits don't fail silently
        run_git(["config", "user.name", "Doc-Loop Agent"], cwd=workspace.root)
        run_git(["config", "user.email", "docloop@localhost"], cwd=workspace.root)
        ensure_git_commit_ready(workspace.root)
    
    if use_git:
        # Only track Doc-Loop specific files to avoid polluting existing repos
        commit_tracked_changes(workspace, "docloop: baseline")
    
    return workspace.target_doc

def ask_human(question_text: str) -> str:
    """Prompts human for input, ensuring we don't return an empty string."""
    print(f"\n[AGENT QUESTION]:\n{question_text}\n")
    while True:
        try:
            answer = input("Your answer (type 'skip' to provide no answer): ").strip()
            if answer.lower() == 'skip':
                return "[User skipped providing an answer]"
            if answer:
                return answer
            print("Please provide an answer, or type 'skip'.")
        except EOFError:
            print("\n[!] EOF detected. Exiting.")
            sys.exit(130)

def run_codex_phase(codex_command: List[str], workspace: Workspace, prompt_path: Path, phase_name: str) -> str:
    """Runs one Codex phase and returns captured stdout for tag parsing."""
    base_instructions = prompt_path.read_text(encoding='utf-8')
    prompt_payload = f"TARGET DOCUMENT: {workspace.target_doc.name}\n\n{base_instructions}"

    print(f"[*] Spawning {phase_name} agent... (Streaming progress below)")

    process = subprocess.run(
        codex_command,
        cwd=workspace.root,
        input=prompt_payload,
        text=True,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        encoding='utf-8'
    )

    stdout = process.stdout or ""
    if process.returncode != 0:
        if stdout.strip():
            print(stdout.rstrip(), file=sys.stderr)
        fatal(f"\n[!] Codex CLI failed during {phase_name} phase with exit code {process.returncode}. Aborting.")

    return stdout

def last_non_empty_line(text: str) -> str:
    """Returns the last non-empty line from a text payload, or an empty string."""
    for line in reversed(text.splitlines()):
        if line.strip():
            return line.strip()
    return ""

def extract_control_tags(stdout: str) -> tuple[Optional[str], Optional[str]]:
    """Extracts supported control tags from a Codex stdout payload."""
    question_match = re.search(r"<question>(.*?)</question>", stdout, re.DOTALL | re.IGNORECASE)
    promise_match = PROMISE_LINE_RE.fullmatch(last_non_empty_line(stdout))
    question_text = question_match.group(1).strip() if question_match else None
    promise = promise_match.group(1).upper() if promise_match else None
    return question_text, promise

def criteria_all_checked(criteria_file: Path) -> bool:
    """Returns True when the verifier-owned checklist has no unchecked boxes."""
    criteria_text = criteria_file.read_text(encoding='utf-8')
    return re.search(r"^- \[ \]", criteria_text, re.MULTILINE) is None

def save_human_clarification(workspace: Workspace, question_text: str, human_answer: str, cycle_number: int, phase_name: str):
    """Appends a human clarification to context.md."""
    with workspace.context_file.open("a", encoding='utf-8') as f:
        f.write(f"\n\n### Human Clarification (Cycle {cycle_number}, {phase_name})\n")
        f.write(f"**Q:** {question_text}\n")
        f.write(f"**A:** {human_answer}\n")

def main():
    parser = argparse.ArgumentParser(description="Doc-Loop: Adversarial Document Refinement")
    parser.add_argument("--type", choices=["SAD", "PRD"], default="SAD", help="Target document type")
    parser.add_argument("--max-iterations", type=int, default=15, help="Maximum number of non-question agent loops")
    parser.add_argument("--model", type=str, default="gpt-5.4", help="Codex model to use")
    parser.add_argument("--update", action="store_true", help="Update an existing target document using explicit change instructions")
    parser.add_argument("--update-text", type=str, help="Requested document updates to apply when --update is set")
    parser.add_argument("--no-git", action="store_true", help="Do not initialize git or create git commits/checkpoints")
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--input-text", type=str, help="Seed the target document from inline text")
    input_group.add_argument("--input-file", type=str, help="Seed the target document from a file")
    parser.add_argument(
        "-o",
        "-output",
        "--output",
        dest="output",
        help="Output file or directory. Defaults to ./TYPE.md in the current directory"
    )
    args = parser.parse_args()

    if args.update and not args.update_text:
        fatal("[!] FATAL: --update requires --update-text.")
    if args.update_text and not args.update:
        fatal("[!] FATAL: --update-text can only be used together with --update.")

    use_git = not args.no_git
    if use_git and not shutil.which("git"):
        warn("git is not installed; forcing --no-git mode.")
        use_git = False
    check_dependencies(require_git=use_git)
    codex_command = resolve_codex_exec_command(args.model)
    target_doc = resolve_output_target(args.type, args.output)
    workspace = build_workspace(target_doc)
    run_mode = select_run_mode(workspace, args.update)
    target_seed = load_input_text(args.input_text, args.input_file)
    target_doc = init_workspace(workspace, target_seed, run_mode, args.update_text, use_git=use_git)
    cycle_counter = 0

    print("\n[+] Starting Doc-Loop Orchestrator (Codex Native I/O)")
    print(f"[*] Target: {target_doc} | Model: {args.model} | Mode: {run_mode.name}")
    print(f"[*] Workspace root: {workspace.root}")
    print("[*] Press Ctrl+C at any time to gracefully stop the loop.")
    
    try:
        while cycle_counter < args.max_iterations:
            cycle_number = cycle_counter + 1
            print(f"\n================ Cycle {cycle_number}/{args.max_iterations} ================")
            
            # Baseline filesystem state
            if use_git:
                commit_tracked_changes(workspace, f"docloop: pre-cycle {cycle_number} snapshot")

            writer_stdout = run_codex_phase(codex_command, workspace, run_mode.writer_prompt_file, "writer")
            writer_question, writer_promise = extract_control_tags(writer_stdout)

            if writer_question:
                human_answer = ask_human(writer_question)
                save_human_clarification(workspace, writer_question, human_answer, cycle_number, "writer")

                if use_git:
                    print("[+] Saving human clarification to git history...")
                    commit_tracked_changes(workspace, f"docloop: human answered writer question in cycle {cycle_number}")
                continue

            if writer_promise:
                fatal(f"[!] Writer emitted <promise>{writer_promise}</promise>. Only the verifier may declare completion.")

            writer_changed = changed_tracked_paths(workspace) if use_git else set()
            active_criteria = str(run_mode.criteria_file.relative_to(workspace.root))
            if active_criteria in writer_changed:
                fatal(f"[!] Writer modified {active_criteria}. Criteria are verifier-owned.")

            if writer_changed:
                if use_git:
                    print("[+] Writer mutated files. Committing diffs...")
                    commit_tracked_changes(workspace, f"docloop: cycle {cycle_number} writer edits")
            else:
                if use_git:
                    print("[-] Writer made no tracked changes.")
                else:
                    print("[-] Change detection skipped in --no-git mode.")

            verifier_stdout = run_codex_phase(
                codex_command,
                workspace,
                run_mode.verifier_prompt_file,
                "verifier"
            )
            verifier_question, verifier_promise = extract_control_tags(verifier_stdout)

            if verifier_question:
                human_answer = ask_human(verifier_question)
                save_human_clarification(workspace, verifier_question, human_answer, cycle_number, "verifier")

                if use_git:
                    print("[+] Saving human clarification to git history...")
                    commit_tracked_changes(workspace, f"docloop: human answered verifier question in cycle {cycle_number}")
                continue

            verifier_changed = changed_tracked_paths(workspace) if use_git else set()
            if use_git and workspace.target_doc.name in verifier_changed:
                fatal("[!] Verifier modified the target document. The verifier may only update Doc-Loop control files.")

            if not verifier_promise:
                print("[!] No verifier promise tag found. Defaulting to <promise>INCOMPLETE</promise>.")
                with workspace.progress_file.open("a", encoding='utf-8') as f:
                    f.write(f"\n\n### System Warning (Cycle {cycle_number})\n")
                    f.write("No promise tag found, defaulted to <promise>INCOMPLETE</promise>\n")
                verifier_promise = PROMISE_INCOMPLETE
                verifier_changed = changed_tracked_paths(workspace) if use_git else set()

            if verifier_promise == PROMISE_COMPLETE:
                if not criteria_all_checked(run_mode.criteria_file):
                    fatal("[!] Verifier emitted <promise>COMPLETE</promise> but the criteria file still has unchecked boxes.")
                print("\n[SUCCESS] Verifier emitted <promise>COMPLETE</promise>.")
                if use_git:
                    commit_tracked_changes(workspace, f"docloop: SUCCESSFUL COMPLETION ({workspace.target_doc.name})")
                sys.exit(0)

            if verifier_promise == PROMISE_BLOCKED:
                print("\n[BLOCKED] Verifier emitted <promise>BLOCKED</promise>.", file=sys.stderr)
                if verifier_changed:
                    print("[+] Verifier wrote blocking feedback. Committing diffs...")
                    if use_git:
                        commit_tracked_changes(workspace, f"docloop: BLOCKED ({workspace.target_doc.name})")
                else:
                    print("[!] Verifier blocked without actionable output.", file=sys.stderr)
                sys.exit(2)

            if verifier_promise == PROMISE_INCOMPLETE and verifier_changed:
                print("[+] Verifier emitted <promise>INCOMPLETE</promise> and wrote feedback. Committing diffs...")
                if use_git:
                    commit_tracked_changes(workspace, f"docloop: cycle {cycle_number} verifier feedback")
            elif not verifier_changed:
                print("[!] Verifier produced no actionable output. Injecting protocol warning into progress.txt...")
                with workspace.progress_file.open("a", encoding='utf-8') as f:
                    f.write(f"\n\n### System Warning (Cycle {cycle_number})\n")
                    f.write("Verifier produced neither a valid final promise tag nor actionable feedback. ")
                    f.write(
                        f"Verifier must update `{active_criteria}` and `.docloop/progress.txt`, "
                        "ask a `<question>`, or end with a final promise line.\n"
                    )
                if use_git:
                    commit_tracked_changes(workspace, f"docloop: injected verifier protocol warning in cycle {cycle_number}")
            else:
                print("[+] Verifier wrote feedback. Committing diffs...")
                if use_git:
                    commit_tracked_changes(workspace, f"docloop: cycle {cycle_number} verifier feedback")

            cycle_counter += 1
            time.sleep(2) # API Rate-limit cooldown

        print(f"\n[FAILED] Reached max iterations ({args.max_iterations}) without a COMPLETE signal from the verifier.", file=sys.stderr)
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user. Shutting down gracefully...")
        sys.exit(130)

if __name__ == "__main__":
    main()
