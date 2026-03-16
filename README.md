# Doc-Loop

`docloop.py` is a minimal CLI orchestrator for iterative document refinement. It creates a small workspace on disk, runs a writer-verifier Codex loop, and uses git commits as checkpoints between iterations. It supports both a general refinement mode and a dedicated update mode for applying requested changes to an existing SAD or PRD.

## What It Does

- Checks that `git` and `codex` are available in `PATH`.
- Resolves an output target file, defaulting to `./SAD.md` or `./PRD.md` in the current directory.
- Creates a `.docloop/` workspace with writer prompt, verifier prompt, criteria, progress, and context files next to the output target.
- Seeds the target markdown document from `--input-text` or `--input-file` when provided.
- Supports `--update` mode with `--update-text`, a frozen baseline snapshot, and dedicated writer/verifier prompts for change requests.
- Initializes a local git repository in the output workspace if no repository already exists there or above it.
- Repeatedly runs `codex exec` twice per cycle: once as the writer and once as the verifier.
- Parses loop-control output from agent stdout:
  - Canonical output is a tagged JSON block:
    - `<loop-control>{"schema":"docloop.loop_control/v1",...}</loop-control>`
  - Canonical `kind:"question"` pauses for human input and appends the answer to `.docloop/context.md`.
  - Canonical `kind:"promise"` supports verifier-only `COMPLETE`, `INCOMPLETE`, and `BLOCKED`.
  - Legacy compatibility remains enabled:
    - `<question>...</question>` is still recognized anywhere in stdout.
    - A legacy `<promise>...</promise>` is still recognized only when it is the last non-empty line.
  - If the verifier omits a promise tag entirely, Doc-Loop defaults that pass to `<promise>INCOMPLETE</promise>` and appends this warning to `.docloop/progress.txt`: `No promise tag found, defaulted to <promise>INCOMPLETE</promise>`.
  - Multiple canonical `<loop-control>` blocks, malformed canonical JSON, or canonical output mixed with legacy semantic control tags are hard failures.
- Makes the verifier update `.docloop/criteria.md` and write actionable feedback to `.docloop/progress.txt` when the document is not ready, balancing completeness against redundancy and unnecessary implementation detail.
- Commits baseline state, pre-cycle snapshots, writer edits, verifier feedback, human clarifications, and successful completion markers to git.

## Requirements

- Python 3
- `git`
- `codex`

The script expects `codex` to support this execution pattern:

```bash
codex exec --ephemeral --full-auto --dangerously-bypass-approvals-and-sandbox --model MODEL -
```

## Usage

Run the script from the directory where you want the default output file to be created:

```bash
python3 docloop.py
```

Options:

- `--type {SAD,PRD}`: Selects the default target document name. Default: `SAD`
- `--max-iterations N`: Maximum loop count before failing. Default: `15`
- `--model MODEL`: Codex model passed through to `codex exec`. Default: `gpt-5.4`
- `--no-git`: Disable git initialization and checkpoint commits for this run (also auto-enabled with a warning when `git` is unavailable)
- `--update`: Update an existing target document using explicit change instructions
- `--update-text TEXT`: Requested document updates to apply when `--update` is set
- `--input-text TEXT`: Seed the output document from inline text
- `--input-file PATH`: Seed the output document from a file
- `-o`, `-output`, `--output`: Output file or directory. Default: `./SAD.md` or `./PRD.md`

Example:

```bash
python3 docloop.py --input-file ./notes/source.md --output ./reports/
```

```bash
python3 docloop.py --type PRD --input-text "# Draft PRD" --output ./prd-review.md
```

```bash
python3 docloop.py --update --update-text "Add offline deployment constraints and clarify backward compatibility." --output ./SAD.md
```

## Workspace Layout

On first run, the script creates the workspace next to the resolved output target. For example, with the default output in the current directory:

```text
.docloop/
  prompt.md
  verifier_prompt.md
  criteria.md
  update_prompt.md
  update_verifier_prompt.md
  update_criteria.md
  update_request.md
  update_baseline.md
  progress.txt
  context.md
SAD.md or PRD.md
```

File roles:

- `.docloop/prompt.md`: Writer instructions sent to Codex for the write pass.
- `.docloop/verifier_prompt.md`: Verifier instructions sent to Codex for the verification pass.
- `.docloop/criteria.md`: Verifier-owned checklist for implementation-ready completeness, clarity, single-source-of-truth discipline, and appropriate abstraction level.
- `.docloop/update_prompt.md`: Writer instructions used only in update mode.
- `.docloop/update_verifier_prompt.md`: Verifier instructions used only in update mode.
- `.docloop/update_criteria.md`: Verifier-owned checklist for requested-change coverage, regression control, single-source-of-truth discipline, and appropriate abstraction level in update mode.
- `.docloop/update_request.md`: The requested document changes for the current update run.
- `.docloop/update_baseline.md`: Frozen pre-update target snapshot used to detect unintended regressions.
- `.docloop/progress.txt`: Append-only writer/verifier handoff log and system warnings.
- `.docloop/context.md`: Human requirements, implementation constraints, and later clarification answers.
- `SAD.md` / `PRD.md` or your custom `--output` file: The target document being refined.

Output rules:

- No `--output`: write `./SAD.md` or `./PRD.md` in the current directory.
- `--output path/to/file.md`: write exactly that file and place `.docloop/` beside it.
- `--output path/to/dir` or `--output path/to/dir/`: write `path/to/dir/SAD.md` or `path/to/dir/PRD.md`.

## Loop Behavior

For each cycle, `docloop.py`:

1. Stages and commits the current target document and `.docloop/` state as a pre-cycle snapshot.
2. Runs the writer using `.docloop/prompt.md` with the full workspace context.
3. If the writer asks a question, the human answer is appended to `.docloop/context.md`, committed, and the cycle restarts.
4. Commits any writer edits, then runs the verifier using `.docloop/verifier_prompt.md` against the same full workspace context.
5. If the verifier asks a question, the human answer is appended to `.docloop/context.md`, committed, and the cycle restarts.
6. If the verifier does not pass the document, it must update `.docloop/criteria.md` and append actionable feedback to `.docloop/progress.txt` for the writer, then the next cycle begins.
7. If the verifier emits canonical `{"kind":"promise","promise":"COMPLETE"}` in `<loop-control>` as the final control block, or the legacy final-line `<promise>COMPLETE</promise>`, the final state is committed and the script exits `0`.
8. If the verifier emits canonical or legacy `INCOMPLETE`, the verifier feedback is committed and the next cycle begins.
9. If the verifier emits canonical or legacy `BLOCKED`, the verifier feedback is committed and the script exits blocked.

The script sleeps for two seconds between iterations as a cooldown.

## Update Mode

When `--update` is enabled:

1. `--update-text` is required.
2. The target document must already exist unless you also seed it with `--input-text` or `--input-file`.
3. Doc-Loop writes the requested change text to `.docloop/update_request.md`.
4. Doc-Loop snapshots the pre-update target into `.docloop/update_baseline.md`.
5. The writer and verifier switch to `.docloop/update_prompt.md`, `.docloop/update_verifier_prompt.md`, and `.docloop/update_criteria.md`.

Update-mode questions are stricter:

- The writer and verifier are instructed to ask clarifying questions when a requested change is breaking, ambiguous, likely to introduce regressions, or likely to be misunderstood.
- Every such question must include the agent's best supposition immediately beside the question so the human can confirm or correct it quickly.

## Exit Conditions

- Success: the verifier emits canonical or legacy `COMPLETE`, and the script exits `0`.
- Blocked: the verifier emits canonical or legacy `BLOCKED`, and the script exits `2`.
- Failure: the maximum iteration count is reached without completion, and the script exits `1`.
- Interrupt: `Ctrl+C` exits gracefully with code `130`.
- Fatal dependency or git errors cause immediate exit via `sys.exit(1)`.

## Loop-Control Rules

- Canonical output uses one `<loop-control>...</loop-control>` JSON block with schema ID `docloop.loop_control/v1`.
- Canonical `kind:"question"` and `kind:"promise"` are mutually exclusive; one block represents exactly one decision.
- Canonical output is the single source of truth. If canonical output is malformed, uses an unknown schema, appears more than once, or is mixed with legacy semantic control tags, Doc-Loop fails fast instead of guessing.
- Promise decisions are verifier-only. The writer must not emit canonical promise output or legacy `<promise>...</promise>` tags.
- Legacy `<question>...</question>` output remains recognized anywhere for compatibility.
- A legacy promise tag is only recognized when it is the last non-empty line of verifier stdout, exactly.
- Mentioning a legacy promise tag in ordinary prose does not count as a control signal.
- If no verifier promise tag is present, Doc-Loop treats that verifier pass as `INCOMPLETE` and appends a system warning to `.docloop/progress.txt`, which is part of the next cycle's working-set prompt.

## Notes

- The script only tracks the target markdown file and `.docloop/` content when creating commits.
- If `--input-text` or `--input-file` is provided, the resolved output document is overwritten with that seed content before the loop starts.
- Git commits are skipped when there is nothing to commit.
- Human clarifications are appended to `.docloop/context.md`; they do not overwrite prior context.
- The writer and verifier both read the same full workspace context; the verifier is not run on a reduced or clean-room context.
- Update mode uses the same full context plus `.docloop/update_request.md` and `.docloop/update_baseline.md`.


## Superloop (Strategy-to-Execution)

This repository also includes `superloop.py`, a Codex-native orchestrator for optional, chained producer/verifier loop pairs inspired by Doc-Loop control signals.

### Goals

- Turn broad product intent into shipped, reviewed, and tested changes.
- Preserve low-friction control through the same loop-control contract:
  - Canonical `<loop-control>...</loop-control>` JSON is the default
  - Legacy `<question>...</question>` and verifier final-line `<promise>COMPLETE|INCOMPLETE|BLOCKED</promise>` remain supported for compatibility

### Optional loop pairs

`superloop.py` supports three optional pairs (in fixed order):

1. `plan`: Plan ↔ Plan Verifier
2. `implement`: Implement ↔ Code Reviewer
3. `test`: Test Author ↔ Test Auditor

Use `--pairs` to choose any subset, for example only implementation review:

```bash
python3 superloop.py --pairs implement
```

Run all pairs (default):

```bash
python3 superloop.py --pairs plan,implement,test
```

### Common options

- `--workspace PATH`: Repository root to operate on (default `.`)
- `--max-iterations N`: Maximum verifier cycles per enabled pair (default `15`)
- `--model MODEL`: Codex model passed to `codex exec` (default `gpt-5.4`)
- `--intent TEXT`: Optional initial product intent seeded into `.superloop/context.md`
- `--task-id ID`: Task workspace slug under `.superloop/tasks/` (new runs require `--task-id` or `--intent`)
- `--intent-mode {replace,append,preserve}`: How `--intent` mutates task context (default `preserve`)
- `--resume`: Resume an existing task/run instead of creating a new run
- `--run-id RUN_ID`: Optional run ID to resume; requires `--resume`
- `--full-auto-answers`: Automatically answer `<question>` prompts through an extra Codex pass
- `--no-git`: Disable git initialization and checkpoint commits for this run (also auto-enabled with a warning when `git` is unavailable)

Resume selection rules:

- `--resume --task-id <id> --run-id <run>`: resume the explicit run under the explicit task.
- `--resume --task-id <id>`: resume the latest run under that task.
- `--resume --run-id <run>`: locate the task containing that run and resume it.
- `--resume` only: resume the latest task and then the latest run within that task.

`--pairs` validation notes:

- Each pair name must be from `plan`, `implement`, `test`.
- Duplicate pair names are rejected (for example `--pairs implement,implement` fails fast).

### Superloop workspace layout

`superloop.py` creates `.superloop/` under the workspace root:

```text
.superloop/
  context.md
  run_log.md
  plan/
    prompt.md
    verifier_prompt.md
    criteria.md
    feedback.md
    plan.md                      # includes milestones, interfaces, and risk register
  implement/
    prompt.md
    verifier_prompt.md
    criteria.md
    feedback.md
    implementation_notes.md
    review_findings.md
  test/
    prompt.md
    verifier_prompt.md
    criteria.md
    feedback.md
    test_strategy.md
    test_gaps.md
```

Like Doc-Loop, Superloop checkpoints progress with git commits throughout execution.

Superloop commit scope and verifier protections:

- Superloop always persists `.superloop/` run artifacts and also commits phase output deltas, so durable code/test artifacts can live anywhere in the repository.
- Question-path safety checks are phase-local and based on Git snapshot diffs (including newly created files), so pre-existing unrelated repo changes do not falsely trip `<question>` handling.
- Verifier write scope is checked per pair and reported as warnings in lax-guard mode (execution continues):
  - `plan` verifier may only edit `.superloop/plan/`
  - `implement` verifier may only edit `.superloop/implement/`
  - `test` verifier may only edit `.superloop/test/`
- Multiple canonical `<loop-control>` blocks, malformed canonical payloads, and canonical output mixed with legacy semantic control tags are treated as fatal protocol violations.
- If a verifier emits `COMPLETE` while criteria checkboxes remain unchecked, Superloop warns and downgrades that pass to `INCOMPLETE`.
- If a verifier omits any promise output, Superloop appends `No promise tag found, defaulted to <promise>INCOMPLETE</promise>.` to pair feedback and defaults that pass to `INCOMPLETE`.

## Reflow

`reflow.py` is an executable implementation of the Reflow v1.2 runtime specified in `refined_reflow_v1.2/SAD.md`.

### Requirements

- Python 3
- `PyYAML`
- Provider CLIs such as `codex` or `claude` available in `PATH`

Install Python dependencies with:

```bash
python3 -m pip install -r requirements.txt
```

### Usage

```bash
python3 reflow.py run <workflow> --workspace /path/to/workspace
python3 reflow.py status <run_id> --workspace /path/to/workspace
python3 reflow.py list --workspace /path/to/workspace
python3 reflow.py reply <run_id> --workspace /path/to/workspace
python3 reflow.py stop <run_id> --workspace /path/to/workspace
```

The workspace must contain:

```text
.reflow/
  config.yaml
  workflows/
    <workflow>/
      workflow.yaml
```

Per-run state, history, operator inputs, and iteration artifacts are written under `.reflow/runs/`.
