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
5. Prefer explicit contracts over aspirational prose. Define workflows, interfaces, data shapes, states, failure handling, edge cases, and non-functional constraints when they matter to implementation.
6. Keep the document internally consistent and avoid duplicate requirements. If a concept appears in multiple sections, pick one canonical definition and cross-reference it.
7. Do not edit `.docloop/criteria.md`.
8. Append a concise writer log entry to `.docloop/progress.txt`. Do not overwrite it.

## Ask A Question
If you would need to invent product behavior, external interfaces, data contracts, acceptance criteria, or operational rules to continue safely, do not edit any files. Output:
<question>Ask your clarifying question here</question>

Do not output `<promise>COMPLETE</promise>`. The verifier decides completion.
"""

DEFAULT_VERIFIER_PROMPT = """# Doc-Loop Verifier Instructions

You are the verifier agent. Evaluate whether the target document is implementation-ready using the full workspace context.

## Working Set
- `TARGET DOCUMENT`: the spec under review
- `.docloop/context.md`: source-of-truth requirements, constraints, and clarifications
- `.docloop/criteria.md`: completion gates you must maintain
- `.docloop/progress.txt`: append-only handoff log for the writer

## Rules
1. Read the target document, context, progress, and criteria before deciding anything.
2. Use the full context. Do not ignore prior human clarifications or prior verifier findings.
3. Do not edit the target document or `.docloop/context.md`.
4. Update `.docloop/criteria.md` so each box accurately reflects the current target document state.
5. If the document does not pass, append clear, actionable feedback to `.docloop/progress.txt` for the writer. Name what is missing, ambiguous, contradictory, or underspecified, and explain how the document must change.
6. Feedback must be specific enough that the writer can act on it without guessing. Prefer concrete gaps and expected additions over generic statements like "be clearer".

## Ask A Question
If reliable verification is blocked because the human has not provided necessary product intent or constraints, do not edit any files. Output:
<question>Ask your clarifying question here</question>

## Completion
If every box in `.docloop/criteria.md` is checked, no further writer edits are needed, and the document is implementation-ready, output:
<promise>COMPLETE</promise>

Otherwise, exit normally without tags after updating `.docloop/criteria.md` and `.docloop/progress.txt`.
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
6. Treat the latest verifier feedback in `.docloop/progress.txt` as the immediate work queue unless it conflicts with `.docloop/context.md` or `.docloop/update_request.md`.
7. Do not edit `.docloop/update_criteria.md`, `.docloop/update_request.md`, or `.docloop/update_baseline.md`.
8. Append a concise writer log entry to `.docloop/progress.txt`. Do not overwrite it.

## Ask A Question
If the requested changes are breaking, ambiguous, likely to introduce regression bugs, or can clearly be misunderstood, and you cannot resolve them safely from the update request, context, or baseline, do not edit any files. Output:
<question>
Question: Ask your clarifying question here
Best supposition: State your best current assumption right beside this question
</question>

Every question must include its best supposition immediately beside it.
Do not output `<promise>COMPLETE</promise>`. The verifier decides completion.
"""

DEFAULT_UPDATE_VERIFIER_PROMPT = """# Doc-Loop Update Verifier Instructions

You are the update verifier agent. Verify that the requested updates were applied correctly using the full workspace context and the frozen baseline.

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
5. Update `.docloop/update_criteria.md` so each box accurately reflects the current target document state.
6. If the document does not pass, append clear, actionable feedback to `.docloop/progress.txt` for the writer. Name the missing requested change, regression risk, ambiguity, contradiction, or breaking-change handling gap, and explain exactly how the document must change.
7. Feedback must be specific enough that the writer can act on it without guessing.

## Ask A Question
If reliable verification is blocked because the requested change is breaking, ambiguous, likely to introduce regressions, or can clearly be misunderstood, do not edit any files. Output:
<question>
Question: Ask your clarifying question here
Best supposition: State your best current assumption right beside this question
</question>

Every question must include its best supposition immediately beside it.

## Completion
If every box in `.docloop/update_criteria.md` is checked, the requested changes are applied, no unintended regressions remain, and no further edits are needed, output:
<promise>COMPLETE</promise>

Otherwise, exit normally without tags after updating `.docloop/update_criteria.md` and `.docloop/progress.txt`.
"""

DEFAULT_CRITERIA = """# Document Verification Criteria
Check these boxes (`- [x]`) only when the target document itself satisfies the rule.

- [ ] **Implementation-Ready Scope**: The document defines the system purpose, major components, responsibilities, and boundaries clearly enough that an autonomous coding agent would not need to invent the overall design.
- [ ] **Behavior Completeness**: The main flows, edge cases, failure modes, and recovery behavior that materially affect implementation are specified or explicitly declared out of scope.
- [ ] **Interface & Data Contracts**: Every interface, data shape, persisted entity, protocol, file format, and integration needed for implementation is defined with enough precision to code against.
- [ ] **Operational Constraints**: Relevant runtime constraints are stated clearly, including performance, security, observability, configuration, deployment assumptions, and other non-functional requirements that affect implementation.
- [ ] **Ambiguity Control**: The document contains no unresolved placeholders such as TBD/TODO/??? and no materially ambiguous language that would force an implementer to guess.
- [ ] **Internal Consistency**: Sections, examples, tables, and terminology do not contradict each other.
- [ ] **Single Source of Truth**: Requirements and contracts are defined once and referenced consistently rather than duplicated with diverging wording.
"""

UPDATE_CRITERIA = """# Update Verification Criteria
Check these boxes (`- [x]`) only when the target document itself satisfies the rule for this update request.

- [ ] **Requested Changes Applied**: Every requested change in `.docloop/update_request.md` is reflected in the target document clearly and completely.
- [ ] **No Unintended Regression Against Baseline**: Requirements and contracts from `.docloop/update_baseline.md` that were not meant to change are still present and compatible, or any removal/change is explicitly justified by the update request.
- [ ] **Breaking Change Handling**: Any breaking change, compatibility impact, migration need, or behavior removal introduced by the update is stated explicitly enough that implementers will not miss it.
- [ ] **Interface & Data Contracts**: Every interface, data shape, persisted entity, protocol, file format, and integration touched by the update is defined with enough precision to code against.
- [ ] **Operational Constraints**: Relevant runtime constraints introduced or affected by the update are stated clearly, including performance, security, observability, configuration, deployment assumptions, and other non-functional requirements that affect implementation.
- [ ] **Ambiguity Control**: The updated document contains no unresolved placeholders such as TBD/TODO/??? and no materially ambiguous language that would force an implementer to guess, especially around the requested changes.
- [ ] **Internal Consistency**: Updated sections, unchanged sections, examples, tables, and terminology do not contradict each other.
- [ ] **Single Source of Truth**: Updated requirements and contracts are defined once and referenced consistently rather than duplicated with diverging wording.
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

def fatal(message: str, exit_code: int = 1):
    """Prints a fatal error and exits immediately."""
    print(message, file=sys.stderr)
    sys.exit(exit_code)

def check_dependencies():
    """Fails fast if required CLI tools are missing."""
    missing = []
    if not shutil.which("git"):
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
    """Builds the Codex exec command and verifies full-auto support."""
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

    if "--full-auto" in help_text:
        return ["codex", "exec", "--ephemeral", "--full-auto", "--model", model, "-"]

    fatal("[!] FATAL CODEX ERROR: This Doc-Loop version requires `codex exec --full-auto` support.")

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

def init_workspace(workspace: Workspace, target_seed: Optional[str], run_mode: RunMode, update_text: Optional[str]) -> Path:
    """Initializes the minimal filesystem-as-memory architecture."""
    workspace.root.mkdir(parents=True, exist_ok=True)
    repo_exists = has_git_repo(workspace.root)

    if repo_exists:
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

    if not repo_exists:
        print("[*] Initializing local Git repository...")
        run_git(["init"], cwd=workspace.root)
        # Ensure a local git identity exists so commits don't fail silently
        run_git(["config", "user.name", "Doc-Loop Agent"], cwd=workspace.root)
        run_git(["config", "user.email", "docloop@localhost"], cwd=workspace.root)
        ensure_git_commit_ready(workspace.root)
    
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

def extract_control_tags(stdout: str) -> tuple[Optional[str], bool]:
    """Extracts supported control tags from a Codex stdout payload."""
    question_match = re.search(r"<question>(.*?)</question>", stdout, re.DOTALL | re.IGNORECASE)
    complete_match = re.search(r"<promise>COMPLETE</promise>", stdout, re.IGNORECASE)
    question_text = question_match.group(1).strip() if question_match else None
    return question_text, bool(complete_match)

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

    check_dependencies()
    codex_command = resolve_codex_exec_command(args.model)
    target_doc = resolve_output_target(args.type, args.output)
    workspace = build_workspace(target_doc)
    run_mode = select_run_mode(workspace, args.update)
    target_seed = load_input_text(args.input_text, args.input_file)
    target_doc = init_workspace(workspace, target_seed, run_mode, args.update_text)
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
            commit_tracked_changes(workspace, f"docloop: pre-cycle {cycle_number} snapshot")

            writer_stdout = run_codex_phase(codex_command, workspace, run_mode.writer_prompt_file, "writer")
            writer_question, writer_complete = extract_control_tags(writer_stdout)

            if writer_question:
                if tracked_files_changed(workspace):
                    fatal("[!] Writer emitted <question> after editing tracked files. Refusing to continue with a mixed state.")

                human_answer = ask_human(writer_question)
                save_human_clarification(workspace, writer_question, human_answer, cycle_number, "writer")

                print("[+] Saving human clarification to git history...")
                commit_tracked_changes(workspace, f"docloop: human answered writer question in cycle {cycle_number}")
                continue

            if writer_complete:
                fatal("[!] Writer emitted <promise>COMPLETE</promise>. Only the verifier may declare completion.")

            writer_changed = changed_tracked_paths(workspace)
            active_criteria = str(run_mode.criteria_file.relative_to(workspace.root))
            if active_criteria in writer_changed:
                fatal(f"[!] Writer modified {active_criteria}. Criteria are verifier-owned.")

            if writer_changed:
                print("[+] Writer mutated files. Committing diffs...")
                commit_tracked_changes(workspace, f"docloop: cycle {cycle_number} writer edits")
            else:
                print("[-] Writer made no tracked changes.")

            verifier_stdout = run_codex_phase(
                codex_command,
                workspace,
                run_mode.verifier_prompt_file,
                "verifier"
            )
            verifier_question, verifier_complete = extract_control_tags(verifier_stdout)

            if verifier_question:
                if tracked_files_changed(workspace):
                    fatal("[!] Verifier emitted <question> after editing tracked files. Refusing to continue with a mixed state.")

                human_answer = ask_human(verifier_question)
                save_human_clarification(workspace, verifier_question, human_answer, cycle_number, "verifier")

                print("[+] Saving human clarification to git history...")
                commit_tracked_changes(workspace, f"docloop: human answered verifier question in cycle {cycle_number}")
                continue

            verifier_changed = changed_tracked_paths(workspace)
            if workspace.target_doc.name in verifier_changed:
                fatal("[!] Verifier modified the target document. The verifier may only update Doc-Loop control files.")

            if verifier_complete:
                print("\n[SUCCESS] Verifier emitted <promise>COMPLETE</promise>.")
                commit_tracked_changes(workspace, f"docloop: SUCCESSFUL COMPLETION ({workspace.target_doc.name})")
                sys.exit(0)

            if not verifier_changed:
                print("[!] Verifier produced no actionable output. Injecting protocol warning into progress.txt...")
                with workspace.progress_file.open("a", encoding='utf-8') as f:
                    f.write(f"\n\n### System Warning (Cycle {cycle_number})\n")
                    f.write("Verifier produced neither `<promise>COMPLETE</promise>` nor actionable feedback. ")
                    f.write(f"Verifier must update `{active_criteria}` and `.docloop/progress.txt`, ask a `<question>`, or declare completion.\n")
                commit_tracked_changes(workspace, f"docloop: injected verifier protocol warning in cycle {cycle_number}")
            else:
                print("[+] Verifier wrote feedback. Committing diffs...")
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
