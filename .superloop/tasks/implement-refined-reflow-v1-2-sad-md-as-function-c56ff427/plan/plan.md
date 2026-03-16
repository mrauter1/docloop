# Reflow v1.2 Implementation Plan

## Objective

Implement the normative behavior in [`refined_reflow_v1.2/SAD.md`](/workspace/CodexTest/docloop/refined_reflow_v1.2/SAD.md) as executable production code in this repository. The current repository has specification documents, `docloop.py`, `superloop.py`, and tests, but no Reflow runtime yet. The target is a new CLI and runtime that satisfy the v1.2 contracts for workflow loading, provider execution, shell steps, run persistence, operator-input handling, resume/reply/stop, and automated tests.

## Current-state findings

- The repository is small and currently Python-script oriented: [`docloop.py`](/workspace/CodexTest/docloop/docloop.py), [`superloop.py`](/workspace/CodexTest/docloop/superloop.py), and [`loop_control.py`](/workspace/CodexTest/docloop/loop_control.py) are the only implementation code.
- The existing [`reflow/`](/workspace/CodexTest/docloop/reflow) directory is documentation-only (`SAD.md`, `source.md`), so runtime code must not use `reflow` as a Python package name.
- Existing tests cover spec-document integrity and Superloop/Doc-Loop helpers, not Reflow runtime behavior.
- The SAD requires YAML workflow/config loading, JSON state files, provider subprocess wrappers, POSIX shell execution, and append-only run artifacts. None of that exists yet.

## Scope and constraints

### In scope

- New `reflow` CLI behavior for `run`, `resume`, `reply`, `status`, `stop`, and `list`
- YAML config/workflow loading and validation
- Agent and shell step execution
- Provider wrappers for Codex and Claude
- Run-state persistence under `.reflow/`
- Operator-input lifecycle, including `--full-auto`
- Policy enforcement, required-file checks, loop/cycle accounting, exit-code mapping
- Unit and integration tests for the runtime

### Explicit non-goals

- Refactoring `docloop.py` or `superloop.py` beyond trivial shared helper reuse proven necessary by tests
- Adding git checkpoint behavior to Reflow
- Cross-platform shell support beyond the SAD’s POSIX assumption
- New workflow DSL features beyond the v1.2 SAD

### Implementation assumptions to lock in

- Runtime code will live in a new package such as `reflow_runtime/`, with a top-level CLI script `reflow.py`, to avoid colliding with the existing docs directory [`reflow/`](/workspace/CodexTest/docloop/reflow).
- `PyYAML` will be added as the runtime YAML dependency; implementing YAML support from scratch is unnecessary complexity.
- `status` and `list` will use stable human-readable text output, not a new machine-format, because the SAD explicitly leaves machine-stable formatting undefined for v1.2.
- Interactive answer collection will use stdin/tty prompts when available; otherwise `run`/`resume` will leave the run in `awaiting_input`, and `reply` without usable stdin and without `--full-auto` will fail without mutating resolved input state.

## Target architecture

### New files and responsibilities

- [`reflow.py`](/workspace/CodexTest/docloop/reflow.py)
  - argparse entrypoint
  - exit-code mapping
  - command dispatch
- `reflow_runtime/__init__.py`
- `reflow_runtime/models.py`
  - normalized dataclasses / typed dict equivalents for config, workflow, run state, pending input, iteration meta
- `reflow_runtime/loaders.py`
  - config/workflow parsing, path normalization, schema validation
- `reflow_runtime/storage.py`
  - `.reflow/` path helpers
  - atomic JSON/text writes
  - `active.json` handling
  - run directory creation
  - interrupted-iteration reconciliation
- `reflow_runtime/protocol.py`
  - parse `<questions>` blocks
  - parse `<answers>` blocks
  - parse tagged decision lines
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

### Reuse guidance

- Reuse ideas from [`superloop.py`](/workspace/CodexTest/docloop/superloop.py) and [`docloop.py`](/workspace/CodexTest/docloop/docloop.py) for CLI style, subprocess capture, and path normalization only where the logic is directly compatible.
- Do not perform a speculative “shared orchestrator” refactor while introducing Reflow; keeping the new runtime isolated is the lower-risk path.

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

- `0`: completed, successful `status`/`list`/`stop`
- `20`: provider unavailable
- `21`: step failed
- `22`: max loops exceeded
- `23`: max cycles exceeded
- `24`: blocked
- `25`: internal/config/command-state error
- `26`: awaiting input
- `27`: stopped

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

The implementation must persist and round-trip these artifacts exactly enough to satisfy the SAD:

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

- All JSON/text/Markdown/YAML must be UTF-8.
- Persisted paths must be repo-relative with forward slashes.
- `run.json` and `active.json` writes must be atomic.
- History must be append-only JSONL.
- A reserved iteration must be persisted before child process launch.
- Full-auto answer passes must not create iteration directories or increment loop/cycle counters.

### Provider wrapper contract

- Codex wrapper must build `codex exec --cd <workspace> ... --output-last-message <final.txt> "<request>"`.
- Claude wrapper must build `claude -p "<request>" ...` and mirror stdout into `final.txt`.
- Provider wrappers must execute argv directly without a shell.
- Reserved provider args from the SAD must be validation errors, not runtime best-effort warnings.

### Control parsing contract

- Agent iterations must check for a valid final `<questions>` block before decision parsing.
- If questions are present, no transition target is accepted.
- Tagged transitions must parse the last valid matching line only.
- Invalid mixed control output must be treated as protocol failure and routed through `step_failed` / retry semantics.
- Full-auto answer parsing must enforce one `<answer>` per pending question, in order.

## Milestones

### Milestone 1: Foundation, validation, and storage

Deliverables:

- Add `reflow.py` and `reflow_runtime/` package skeleton.
- Add YAML loading dependency and import-failure messaging.
- Implement config and workflow loaders with full v1.2 validation.
- Implement path normalization, workspace-root enforcement, and symlink-escape checks.
- Implement run ID generation, run directory creation, `operator_inputs.md` bootstrap, `run.json` creation, `active.json` creation/removal, and history append helpers.
- Implement read-only `status` and `list`.

Acceptance criteria:

- Invalid config/workflow fixtures fail before execution with exit `25`.
- `run`, `status`, and `list` can create and inspect a minimal run directory structure.
- Tests cover loader validation, lock staleness detection, atomic write helpers, and exit-code mapping.

### Milestone 2: Step execution and transitions

Deliverables:

- Implement agent-step instruction loading from file or `SKILL.md`.
- Implement request rendering with the required footer.
- Implement Codex and Claude wrapper command construction and subprocess capture.
- Implement shell-step execution through `/bin/sh -lc`.
- Implement iteration directory reservation, initial/final `meta.json`, stdout/stderr/final capture, decision parsing, `@retry`, and terminal transitions.
- Implement step-loop and cycle accounting.

Acceptance criteria:

- Fixture-based providers can drive happy-path multi-step workflows.
- Shell success/failure routing works through `on_success` / `on_failure`.
- Retry and budget exhaustion semantics match the SAD.

### Milestone 3: Operator-input lifecycle

Deliverables:

- Implement `<questions>` detection and `pending_input` persistence.
- Implement inline interactive answer collection for `run`/`resume` when stdin is available.
- Implement append-only `operator_inputs.md` formatting for `human` and `auto` modes.
- Implement `reply` and `resume` semantics, including lock reacquisition and interrupted-iteration reconciliation.
- Implement `--full-auto` answer flow, including auto-round incrementing, provider reuse, success path, and failure-to-`awaiting_input` behavior.

Acceptance criteria:

- Tests cover inline question resolution, deferred `reply`, auto-answer success, auto-answer failure, and no-counter-increment rules for full-auto passes.
- `reply_started`, `input_requested`, `input_auto_failed`, and `input_resolved` history entries appear with the required fields and ordering.

### Milestone 4: Policy enforcement, stop semantics, and hardening

Deliverables:

- Implement write-policy diffing for create/modify/delete/rename with normalized repo-relative paths.
- Enforce `allow_write`, `forbid_write`, and `required_files`.
- Treat out-of-workspace writes and symlink escapes as policy violations.
- Implement `stop`, controller-subprocess termination, interrupted iteration finalization, and idempotent terminalization.
- Harden failure classification for provider unavailable, malformed control, required-files missing, shell launch failure, and storage errors.

Acceptance criteria:

- Tests cover policy literal/glob matching, rename checks, required-file failure, write-policy violation, provider unavailable, malformed question/answer/decision output, `stop`, and interrupted resume recovery.

### Milestone 5: Repository polish and regression seal

Deliverables:

- Update [`README.md`](/workspace/CodexTest/docloop/README.md) with Reflow usage, dependency requirements, and fixture-based examples.
- Add end-to-end integration fixtures that model a Doc-Loop-like workflow from Section 23 of the SAD.
- Run the full test suite, including existing Doc-Loop/Superloop tests, to confirm isolation.

Acceptance criteria:

- Full `pytest` passes.
- Existing non-Reflow tests remain green.
- New tests demonstrate one complete workflow, one blocked workflow, and one failed workflow.

## Implementation checklist

- [ ] Add isolated `reflow.py` CLI and `reflow_runtime/` package.
- [ ] Add YAML dependency and documentation.
- [ ] Implement config/workflow validators matching SAD Section 20.
- [ ] Implement storage helpers for `.reflow/`, atomic writes, and history.
- [ ] Implement run-state models including `pending_input`.
- [ ] Implement provider resolution and Codex/Claude wrappers.
- [ ] Implement agent request rendering and protocol parsers.
- [ ] Implement shell-step runner and environment variables.
- [ ] Implement step-loop, cycle, retry, and terminal-state logic.
- [ ] Implement operator-input lifecycle, `resume`, `reply`, and `--full-auto`.
- [ ] Implement `stop`, `status`, and `list`.
- [ ] Implement policy and required-file enforcement.
- [ ] Add unit tests.
- [ ] Add integration tests with fixture provider CLIs.
- [ ] Update README and usage examples.

## Test strategy

### Unit coverage

- config validation, including reserved provider flags and unknown fields
- workflow validation for step kinds, transitions, budgets, policies, and instruction paths
- request/footer rendering
- `<questions>` parser, tagged decision parser, and `<answers>` parser
- operator-input markdown formatting
- provider argv construction
- policy matching for literals, globs, renames, and symlink escapes
- exit-code mapping and stale-lock detection

### Integration coverage

- happy-path agent -> agent workflow
- agent -> shell -> `@done`
- inline interactive question handling
- `awaiting_input` then `reply`
- `--full-auto` success and failure
- malformed control output causing retry/failure
- missing decision tag default behavior
- invalid decision tag value
- provider unavailable
- max loops exceeded
- max cycles exceeded
- write-policy violation
- required-file missing
- interrupted iteration reconciliation on `resume`
- `stop` marking a run `stopped`

### Test harness approach

- Use `pytest` temp workspaces.
- Add fake provider executables under test fixtures and prepend them to `PATH` so wrapper behavior is deterministic without network access.
- Use fixture workflows/configs that write predictable `final.txt`, stdout, stderr, and exit codes.
- Keep all new tests additive; existing tests for Doc-Loop/Superloop must remain untouched except for shared utility reuse proven necessary.

## Risk register

| ID | Risk | Impact | Mitigation / control | Rollback or containment |
| ---- | ---- | ---- | ---- | ---- |
| R1 | Python module name collides with existing docs directory `reflow/` | Import/runtime confusion; broken docs path assumptions | Use `reflow.py` + `reflow_runtime/`; leave [`reflow/`](/workspace/CodexTest/docloop/reflow) docs-only | If imports leak into docs dir, revert package naming before expanding functionality |
| R2 | YAML dependency is absent in runtime/test environments | CLI fails before useful validation | Add explicit dependency docs, import guard, and CI/test setup; keep YAML access centralized in `loaders.py` | Fail fast with exit `25` and actionable message |
| R3 | Lock/stale-PID logic misclassifies active vs stale controllers | Data corruption or false command refusal | Treat lock ownership conservatively, require both PID liveness and run-state consistency checks, and cover with tests | Prefer refusal over forced takeover; allow operator to retry after process exit |
| R4 | Policy diffing misses rename/symlink/escape cases | Workspace contamination beyond allowed paths | Normalize repo-relative and real paths, evaluate both sides of rename, treat outside-workspace resolutions as violations, add dedicated tests | Terminally fail affected run and preserve artifacts for inspection |
| R5 | Full-auto path accidentally increments step/cycle counters or creates iteration dirs | Run-state drift and spec violation | Implement full-auto as a separate code path from normal iteration execution and test counter invariants directly | Keep `pending_input` intact and return to `awaiting_input` on any full-auto anomaly |
| R6 | Stop/resume/reply mutate partially written iterations incorrectly | Corrupt `run.json` / history / step artifacts | Centralize reservation/finalization/reconciliation in `storage.py` + `controller.py`; atomic writes only | Preserve partial artifacts, mark interrupted, start fresh next loop |
| R7 | Provider CLI flag drift differs from current local Codex/Claude builds | Commands fail at runtime despite valid config | Centralize wrapper builders, validate reserved args, and assert exact argv in tests | Surface `provider_unavailable` or `step_failed` with captured stderr/stdout |
| R8 | Reflow implementation work accidentally regresses Doc-Loop/Superloop | Existing repository behavior breaks | Keep Reflow isolated; avoid opportunistic refactors; run full `pytest` before completion | Revert any shared-helper refactor and keep duplicated helper localized if needed |

## Order of execution for implementation pair

1. Land the isolated package skeleton, models, loaders, storage helpers, and read-only commands first.
2. Land agent/shell execution plus provider wrappers next, with unit tests before broad integration tests.
3. Add operator-input lifecycle, `resume`, and `reply`.
4. Add policy enforcement and `stop`.
5. Finish with README updates and full-suite verification.

This sequence keeps each checkpoint shippable, minimizes blast radius, and ensures the riskiest state-management features are added after the persistence and execution primitives are already test-backed.
