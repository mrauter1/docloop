# Reflow v1.2 Implementation Plan

## Objective

Implement the normative behavior in [`refined_reflow_v1.2/SAD.md`](/workspace/CodexTest/docloop/refined_reflow_v1.2/SAD.md) as executable production code in this repository. The current repository has specification documents, `docloop.py`, `superloop.py`, `loop_control.py`, and tests, but no Reflow runtime yet. The target is a new CLI and runtime that satisfy the v1.2 contracts for workflow loading, provider execution, shell steps, run persistence, operator-input handling, resume/reply/stop, policy enforcement, and automated tests.

## Current-state findings

- The repository is small and currently script-oriented: [`docloop.py`](/workspace/CodexTest/docloop/docloop.py), [`superloop.py`](/workspace/CodexTest/docloop/superloop.py), and [`loop_control.py`](/workspace/CodexTest/docloop/loop_control.py) are the only implementation code.
- The existing [`reflow/`](/workspace/CodexTest/docloop/reflow) directory is documentation-only (`SAD.md`, `source.md`), so runtime code must not use `reflow` as the import package name.
- Existing tests cover loop-control helpers, Superloop behavior, git tracking, and SAD document integrity, but not a Reflow runtime.
- The repository currently has no Python dependency manifest (`requirements*.txt`, `pyproject.toml`, `setup.py`, `setup.cfg` absent), so any new runtime dependency must be introduced intentionally and documented.
- The SAD requires YAML workflow/config loading, JSON state files, provider subprocess wrappers, POSIX shell execution, append-only run artifacts, and one-controller-per-workspace semantics. None of that exists yet.

## Scope and constraints

### In scope

- New `reflow` CLI behavior for `run`, `resume`, `reply`, `status`, `stop`, and `list`
- YAML config/workflow loading and validation
- Agent and shell step execution
- Provider wrappers for Codex and Claude
- Run-state persistence under `.reflow/`
- Operator-input lifecycle, including inline answers and `--full-auto`
- Policy enforcement, required-file checks, loop/cycle accounting, and exit-code mapping
- Unit and integration tests for the runtime
- Minimal repository reference updates needed to document the executable runtime and new dependency

### Explicit non-goals

- Refactoring `docloop.py` or `superloop.py` beyond trivial helper reuse proven necessary by tests
- Rewriting the SAD beyond minimal cross-references required to point to the runtime
- Adding git checkpoint behavior to Reflow
- Cross-platform shell support beyond the SAD’s POSIX assumption
- New workflow DSL features beyond the v1.2 SAD
- Service/daemon mode, background controllers, or web UI

### Locked implementation assumptions

- Runtime code will live in a new package `reflow_runtime/` with a top-level CLI entry script `reflow.py`, avoiding collision with the docs-only [`reflow/`](/workspace/CodexTest/docloop/reflow) directory.
- YAML parsing will use `PyYAML`; writing a bespoke YAML parser is unnecessary complexity. Because the repo lacks a dependency manifest, implementation should add a minimal `requirements.txt` containing `PyYAML` and document installation in [`README.md`](/workspace/CodexTest/docloop/README.md).
- `status` and `list` will use stable human-readable text output, not a new machine-readable format, because the SAD leaves that output format intentionally lightweight.
- Interactive answer collection will use stdin/tty prompts when available. Otherwise `run` and `resume` will leave the run in `awaiting_input`, and `reply` without usable stdin and without `--full-auto` will fail without mutating resolved input state.
- The implementation should treat the SAD as the behavioral source of truth and keep doc edits minimal; code and tests are the primary deliverables for this task.

## Target architecture

### New files and responsibilities

- [`reflow.py`](/workspace/CodexTest/docloop/reflow.py)
  - argparse entrypoint
  - exit-code mapping
  - command dispatch
- `reflow_runtime/__init__.py`
- `reflow_runtime/models.py`
  - normalized dataclasses or typed-dict style models for config, workflow, run state, pending input, history events, and iteration metadata
- `reflow_runtime/loaders.py`
  - config/workflow parsing
  - path normalization
  - schema validation
- `reflow_runtime/storage.py`
  - `.reflow/` path helpers
  - atomic JSON/text writes
  - `active.json` handling
  - run directory creation
  - interrupted-iteration reconciliation
- `reflow_runtime/protocol.py`
  - parse `<questions>` blocks
  - parse `<answers>` blocks
  - parse tagged transition lines
  - render request footers and malformed-control retry warnings
- `reflow_runtime/providers.py`
  - provider-profile resolution
  - Codex and Claude argv builders
  - subprocess execution and capture
- `reflow_runtime/policy.py`
  - before/after workspace diffing
  - literal/glob policy checks
  - required-file validation
- `reflow_runtime/controller.py`
  - run loop
  - agent and shell iteration orchestration
  - input lifecycle
  - resume/reply/stop/list/status behaviors
- `tests/test_reflow_*.py`
  - unit and integration coverage
- [`requirements.txt`](/workspace/CodexTest/docloop/requirements.txt)
  - runtime dependency declaration for `PyYAML`

### Reuse guidance

- Reuse patterns from [`docloop.py`](/workspace/CodexTest/docloop/docloop.py) and [`superloop.py`](/workspace/CodexTest/docloop/superloop.py) only where directly compatible: CLI style, subprocess capture, path handling, and loop-control helper usage.
- Do not attempt a speculative “shared orchestrator” refactor while introducing Reflow. Isolating Reflow code in its own runtime package is the lower-risk path.
- Reuse [`loop_control.py`](/workspace/CodexTest/docloop/loop_control.py) only if a Reflow control path genuinely matches its contract; do not force-fit Reflow-specific `<questions>` / `<answers>` semantics into the Doc-Loop/Superloop loop-control schema.

## Interface definitions

### CLI surface

The new CLI must implement:

```text
python3 reflow.py run <workflow> [--workspace <path>] [--full-auto]
python3 reflow.py resume <run_id> [--workspace <path>] [--full-auto]
python3 reflow.py reply <run_id> [--workspace <path>] [--full-auto]
python3 reflow.py status <run_id> [--workspace <path>]
python3 reflow.py stop <run_id> [--workspace <path>]
python3 reflow.py list [--workspace <path>]
```

Required exit-code contract:

- `0`: completed, successful `status` / `list` / `stop`
- `20`: provider unavailable
- `21`: step failed
- `22`: max loops exceeded
- `23`: max cycles exceeded
- `24`: blocked
- `25`: internal/config/command-state error
- `26`: awaiting input
- `27`: stopped

Read-only command output minimums:

- `status` MUST report at least `run_id`, `workflow`, `status`, `current_step`, `cycle_count`, `started_at`, and `updated_at`.
- If the run is `awaiting_input`, `status` MUST also report the pending-input `step`, `loop`, question count, and current `auto_round`.
- If the run is `failed`, `status` MUST also report `failure_type` and `failure_reason`.
- `list` MUST enumerate runs from `.reflow/runs/` only.
- Each `list` row MUST include at least `run_id`, `workflow`, `status`, and `updated_at`.
- `list` output MUST be sorted by `started_at` descending.
- v1.2 does not require a machine-stable output format for either command, so implementation should centralize one human-readable formatter and test the required fields and sort order rather than brittle full-string snapshots.

### Core runtime interfaces

The implementation should converge on these internal entrypoints:

```python
def load_config(workspace: Path) -> ReflowConfig: ...
def load_workflow(workspace: Path, workflow_name: str, config: ReflowConfig) -> Workflow: ...
def run_new_workflow(workspace: Path, workflow_name: str, full_auto: bool) -> int: ...
def resume_run(workspace: Path, run_id: str, full_auto: bool) -> int: ...
def reply_to_run(workspace: Path, run_id: str, full_auto: bool) -> int: ...
def stop_run(workspace: Path, run_id: str) -> int: ...
def status_run(workspace: Path, run_id: str) -> int: ...
def list_runs(workspace: Path) -> int: ...
```

Supporting interfaces:

```python
def reserve_iteration(store: RunStore, run: RunState, step_name: str) -> IterationContext: ...
def reconcile_reserved_iteration(store: RunStore, run: RunState) -> None: ...
def render_agent_request(workflow: Workflow, run: RunState, step: AgentStep, warning: str | None) -> str: ...
def invoke_provider(profile: ProviderProfile, request: str, workspace: Path, iteration_dir: Path | None, final_path: Path | None) -> InvocationResult: ...
def invoke_shell(cmd: str, workspace: Path, env_overrides: dict[str, str]) -> InvocationResult: ...
def parse_agent_outcome(final_text: str, transitions: TransitionSpec) -> AgentOutcome: ...
def parse_full_auto_answers(stdout_text: str, expected_count: int) -> list[str]: ...
def evaluate_policy(before: WorkspaceSnapshot, after: WorkspaceSnapshot, policy: StepPolicy | None) -> PolicyResult: ...
```

### Persisted data contracts

The implementation must persist and round-trip these artifacts:

- `.reflow/config.yaml`
- `.reflow/workflows/<workflow>/workflow.yaml`
- `.reflow/active.json`
- `.reflow/runs/<run_id>/run.json`
- `.reflow/runs/<run_id>/history.jsonl`
- `.reflow/runs/<run_id>/operator_inputs.md`
- `.reflow/runs/<run_id>/steps/<step>/<loop>/request.txt` for agent steps
- `.reflow/runs/<run_id>/steps/<step>/<loop>/command.txt` for shell steps
- `.reflow/runs/<run_id>/steps/<step>/<loop>/stdout.txt`
- `.reflow/runs/<run_id>/steps/<step>/<loop>/stderr.txt`
- `.reflow/runs/<run_id>/steps/<step>/<loop>/final.txt`
- `.reflow/runs/<run_id>/steps/<step>/<loop>/meta.json`

Non-negotiable persistence rules:

- All JSON, text, Markdown, and YAML must be UTF-8.
- Persisted paths must be repo-relative with forward slashes.
- `run.json` and `active.json` writes must be atomic.
- `history.jsonl` must be append-only JSONL.
- A reserved iteration must be persisted before child-process launch.
- Full-auto answer passes must not create iteration directories or increment loop or cycle counters.

### Provider wrapper contract

- Codex wrapper must build `codex exec --cd <workspace> ... --output-last-message <final.txt> "<request>"`.
- Claude wrapper must build `claude -p "<request>" ...` and mirror stdout into `final.txt`.
- Provider wrappers must execute argv directly without a shell.
- Reserved provider args from the SAD must be validation errors, not runtime best-effort warnings.
- Provider resolution order must follow SAD Section 4.1 exactly: step override, workflow default, config default.
- Provider invocation must honor the resolved profile `timeout_sec`, defaulting to `1800` when omitted.
- Provider child processes must inherit the controller environment merged with provider `env`, with provider `env` overriding inherited keys.
- `meta.json.command_argv` for provider steps must record the exact argv passed to process creation, after wrapper construction and before launch.

### Shell-step runtime contract

- Shell steps must execute via exact argv `["/bin/sh", "-lc", "<cmd>"]`.
- The shell environment must include the inherited controller environment plus these mandatory runtime variables: `REFLOW_RUN_ID`, `REFLOW_WORKFLOW`, `REFLOW_STEP`, `REFLOW_LOOP`, `REFLOW_WORKSPACE`, and `REFLOW_ITERATION_DIR`.
- `command.txt` must contain the exact `cmd` string from the workflow.
- `meta.json.command_argv` for shell steps must be exactly `["/bin/sh", "-lc", "<cmd>"]`.
- `meta.json.command_text` must record the exact workflow command text.
- Shell-step acceptance and regression tests must assert both the exported runtime variables and the recorded command artifacts so fixture scripts can rely on the documented contract.

### Control parsing contract

- Agent iterations must check for a valid final `<questions>` block before transition parsing.
- If questions are present, no transition target is accepted.
- Tagged transitions must parse the last valid matching line only.
- Invalid mixed control output must be treated as protocol failure and routed through `step_failed` or retry semantics.
- Full-auto answer parsing must enforce one `<answer>` per pending question, in order.

## Milestones

### Milestone 1: Foundation, validation, and storage

Deliverables:

- Add `reflow.py` and `reflow_runtime/` package skeleton.
- Add `requirements.txt` with `PyYAML` and import-failure messaging.
- Implement config and workflow loaders with v1.2 validation.
- Implement path normalization, workspace-root enforcement, and symlink-escape checks.
- Implement run ID generation, run directory creation, `operator_inputs.md` bootstrap, `run.json` creation, `active.json` creation and removal, and history append helpers.
- Implement read-only `status` and `list`.

Acceptance criteria:

- Invalid config and workflow fixtures fail before execution with exit `25`.
- `run`, `status`, and `list` can create and inspect a minimal run directory structure.
- `status` reports the SAD-required minimum fields, plus the `awaiting_input` and `failed` conditional fields when applicable.
- `list` reads `.reflow/runs/` only and sorts runs by `started_at` descending.
- Tests cover loader validation, lock staleness detection, atomic write helpers, dependency-import failure, and exit-code mapping.

### Milestone 2: Step execution and transitions

Deliverables:

- Implement agent-step instruction loading from file or `SKILL.md` references defined by the workflow.
- Implement request rendering with the required footer and repository-resident memory references.
- Implement Codex and Claude wrapper command construction and subprocess capture.
- Implement shell-step execution through `/bin/sh -lc`.
- Implement iteration directory reservation, initial and final `meta.json`, stdout/stderr/final capture, decision parsing, `@retry`, and terminal transitions.
- Implement step-loop and cycle accounting.

Acceptance criteria:

- Fixture-based providers can drive happy-path multi-step workflows.
- Provider fixtures verify timeout propagation, inherited-env plus provider-env merge behavior, and exact recorded argv.
- Shell success and failure routing works through `on_success` and `on_failure`.
- Shell fixtures verify `REFLOW_RUN_ID`, `REFLOW_WORKFLOW`, `REFLOW_STEP`, `REFLOW_LOOP`, `REFLOW_WORKSPACE`, and `REFLOW_ITERATION_DIR`, plus `command.txt`, `meta.json.command_argv`, and `meta.json.command_text`.
- Retry and budget exhaustion semantics match the SAD.

### Milestone 3: Operator-input lifecycle

Deliverables:

- Implement `<questions>` detection and `pending_input` persistence.
- Implement inline interactive answer collection for `run` and `resume` when stdin is available.
- Implement append-only `operator_inputs.md` formatting for `human` and `auto` modes.
- Implement `reply` and `resume` semantics, including lock reacquisition and interrupted-iteration reconciliation.
- Implement `--full-auto` answer flow, including auto-round incrementing, provider reuse, success path, and failure-to-`awaiting_input` behavior.

Acceptance criteria:

- Tests cover inline question resolution, deferred `reply`, auto-answer success, auto-answer failure, and the no-counter-increment rule for full-auto passes.
- `reply_started`, `input_requested`, `input_auto_failed`, and `input_resolved` history entries appear with the required fields and ordering.

### Milestone 4: Policy enforcement, stop semantics, and hardening

Deliverables:

- Implement write-policy diffing for create/modify/delete/rename with normalized repo-relative paths.
- Enforce `allow_write`, `forbid_write`, and `required_files`.
- Treat out-of-workspace writes and symlink escapes as policy violations.
- Implement `stop`, controller-subprocess termination, interrupted iteration finalization, and idempotent terminalization.
- Harden failure classification for provider unavailable, malformed control, required-files missing, shell launch failure, and storage errors.

Acceptance criteria:

- Tests cover policy literal and glob matching, rename checks, required-file failure, write-policy violation, provider unavailable, malformed question/answer/decision output, `stop`, and interrupted resume recovery.

### Milestone 5: Repository polish and regression seal

Deliverables:

- Update [`README.md`](/workspace/CodexTest/docloop/README.md) with Reflow usage, dependency requirements, and fixture-based examples.
- Add end-to-end integration fixtures that model a Doc-Loop-like workflow from Section 23 of the SAD.
- Run the full test suite, including existing Doc-Loop and Superloop tests, to confirm isolation.
- Limit SAD or pointer-doc edits to minimal references needed to mention the executable runtime, if any such references are required at all.

Acceptance criteria:

- Full `pytest` passes.
- Existing non-Reflow tests remain green.
- New tests demonstrate one complete workflow, one blocked workflow, and one failed workflow.

## Implementation checklist

- [ ] Add isolated `reflow.py` CLI and `reflow_runtime/` package.
- [ ] Add `requirements.txt` and README dependency instructions for `PyYAML`.
- [ ] Implement config and workflow validators matching SAD Section 20.
- [ ] Implement storage helpers for `.reflow/`, atomic writes, and history.
- [ ] Implement run-state models including `pending_input`.
- [ ] Implement provider resolution and Codex/Claude wrappers.
- [ ] Implement agent request rendering and protocol parsers.
- [ ] Implement shell-step runner with exact `REFLOW_*` runtime variables and command artifact persistence.
- [ ] Implement exact `status` / `list` field minimums and `started_at` descending ordering.
- [ ] Implement step-loop, cycle, retry, and terminal-state logic.
- [ ] Implement operator-input lifecycle, `resume`, `reply`, and `--full-auto`.
- [ ] Implement `stop`.
- [ ] Implement policy and required-file enforcement.
- [ ] Add unit tests.
- [ ] Add integration tests with fixture provider CLIs.
- [ ] Update README and any minimal runtime-reference docs.

## Test strategy

### Unit coverage

- config validation, including reserved provider flags and unknown fields
- workflow validation for step kinds, transitions, budgets, policies, and instruction paths
- request and footer rendering
- `<questions>` parser, tagged decision parser, and `<answers>` parser
- operator-input markdown formatting
- provider argv construction
- provider timeout and merged environment behavior
- policy matching for literals, globs, renames, and symlink escapes
- `status` conditional fields and `list` `started_at` descending ordering
- exit-code mapping and stale-lock detection
- atomic write and interrupted-iteration reconciliation helpers
- shell command artifact persistence and mandatory runtime environment variables

### Integration coverage

- happy-path agent -> agent workflow
- agent -> shell -> `@done`
- `status` for running, awaiting-input, and failed runs includes the required field set
- `list` ordering uses `started_at` descending and ignores non-run files
- inline interactive question handling
- `awaiting_input` then `reply`
- `--full-auto` success and failure
- malformed control output causing retry or failure
- missing decision tag default behavior where the SAD allows it
- invalid decision tag value
- provider unavailable
- provider timeout and provider `env` override behavior
- max loops exceeded
- max cycles exceeded
- write-policy violation
- required-file missing
- shell fixture observes required `REFLOW_*` variables and exact command artifacts
- interrupted iteration reconciliation on `resume`
- `stop` marking a run `stopped`

### Test harness approach

- Use `pytest` temp workspaces.
- Add fake provider executables under test fixtures and prepend them to `PATH` so wrapper behavior is deterministic without network access.
- Use fixture workflows and configs that write predictable `final.txt`, stdout, stderr, and exit codes.
- Keep all new tests additive; existing tests for Doc-Loop and Superloop must remain untouched except for shared utility reuse proven necessary.

## Risk register

| ID | Risk | Impact | Mitigation / control | Rollback or containment |
| ---- | ---- | ---- | ---- | ---- |
| R1 | Python module naming collides with docs directory `reflow/` | Import confusion; broken docs-path assumptions | Use `reflow.py` plus `reflow_runtime/`; keep [`reflow/`](/workspace/CodexTest/docloop/reflow) docs-only | Rename the runtime package before expanding functionality further |
| R2 | `PyYAML` is missing or inconsistently installed | CLI fails before useful validation | Add `requirements.txt`, centralized import guard, and README install instructions | Fail fast with exit `25` and actionable error text |
| R3 | Lock and stale-PID logic misclassifies active vs stale controllers | Data corruption or false command refusal | Require both PID-liveness and run-state consistency checks; cover stale and live locks in tests | Prefer refusal over forced takeover and allow operator retry after the process exits |
| R4 | Policy diffing misses rename, symlink, or workspace-escape cases | Workspace contamination beyond allowed paths | Normalize repo-relative and real paths, evaluate both sides of a rename, and treat outside-workspace resolutions as violations | Terminally fail the affected run and preserve artifacts for inspection |
| R5 | Full-auto answer flow increments loop or cycle counters or creates iteration dirs | Run-state drift and spec violation | Implement full-auto as a separate code path from normal step iteration and assert counter invariants in tests | Keep `pending_input` intact and return to `awaiting_input` on anomaly |
| R6 | Stop, resume, or reply mutates partially written iterations incorrectly | Corrupt `run.json`, history, or step artifacts | Centralize reservation, finalization, and reconciliation in storage and controller layers; use atomic writes only | Preserve partial artifacts, mark interrupted, and start a fresh next loop |
| R7 | Provider CLI flags drift from current local Codex or Claude builds | Commands fail at runtime despite valid config | Centralize wrapper builders, validate reserved args, and assert exact argv in tests | Surface `provider_unavailable` or `step_failed` with captured stdout and stderr |
| R7a | `status` / `list` output omits required fields or sorts runs incorrectly | CLI appears usable but violates SAD observability guarantees and fails review/tests | Centralize read-only formatters around explicit field minimums and sort helpers; cover running, awaiting-input, and failed cases in tests | Patch the formatter without changing persisted run state |
| R7b | Shell workflows cannot rely on required runtime variables or command artifacts | Fixture scripts and real shell steps fail unpredictably and are harder to debug | Centralize shell launch preparation, export the mandatory `REFLOW_*` variables, and assert `command.txt` plus `meta.json` contents in tests | Fail visibly, preserve the iteration directory, and fix the launch helper without broader runtime rewrites |
| R8 | Reflow implementation accidentally regresses Doc-Loop or Superloop | Existing repository behavior breaks | Keep Reflow isolated; avoid opportunistic refactors; run full `pytest` before completion | Revert shared-helper reuse and localize logic back into Reflow if needed |
| R9 | SAD-only phrases are interpreted too literally when code hits unspecified edges | Implementation churn or verifier disagreement | Use the SAD as the source of truth, but record any truly ambiguous behavior in task-local implementation notes and keep doc edits minimal and explicit | Escalate only the narrow ambiguity instead of broad doc rewrites |

## Order of execution for implementation pair

1. Land the isolated package skeleton, dependency declaration, models, loaders, storage helpers, and read-only commands first.
2. Land agent and shell execution plus provider wrappers next, with unit tests before broad integration tests.
3. Add operator-input lifecycle, `resume`, and `reply`.
4. Add policy enforcement and `stop`.
5. Finish with README updates, minimal runtime references, and full-suite verification.

This order keeps each checkpoint shippable, minimizes blast radius, and defers the riskiest state-management features until persistence and execution primitives are already test-backed.
