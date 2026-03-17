# Reflow v1.2 Implementation Plan

## Objective

Close the remaining conformance gaps between `refined_reflow_v1.2/SAD.md` and the existing runtime. This is a delta plan against the current codebase, not a greenfield design: `reflow.py`, `reflow_runtime/`, README guidance, and focused tests already exist. The remaining work is to fix the known correctness and safety blockers, tighten a few interface contracts, and add regression coverage that proves the runtime matches the SAD.

## Verified current state

- The runtime and CLI already exist in [reflow.py](/home/marcelo/code/docloop/reflow.py) and `reflow_runtime/`.
- Reflow-specific tests already exist in [tests/test_reflow_runtime.py](/home/marcelo/code/docloop/tests/test_reflow_runtime.py) and [tests/test_refined_reflow_sad.py](/home/marcelo/code/docloop/tests/test_refined_reflow_sad.py).
- The implementation task still has unresolved blocking findings in [implement/feedback.md](/home/marcelo/code/docloop/.superloop/tasks/implement-refined-reflow-v1-2-sad-md-as-function-d391842d/implement/feedback.md): `IMP-001` through `IMP-009`.
- The current hot spots are [reflow_runtime/controller.py](/home/marcelo/code/docloop/reflow_runtime/controller.py), [reflow_runtime/providers.py](/home/marcelo/code/docloop/reflow_runtime/providers.py), [reflow_runtime/policy.py](/home/marcelo/code/docloop/reflow_runtime/policy.py), [reflow_runtime/storage.py](/home/marcelo/code/docloop/reflow_runtime/storage.py), and protocol/request assembly in [reflow_runtime/protocol.py](/home/marcelo/code/docloop/reflow_runtime/protocol.py).

## Planning assumptions

- `refined_reflow_v1.2/SAD.md` remains the normative behavioral source. Doc edits are out of scope except minimal reference sync if runtime wording must be clarified.
- The repository structure is adequate. Fixes should refine current modules instead of introducing a new architecture.
- KISS and DRY apply: centralize child-process handling, stop handling, and policy filtering only where repetition is already causing drift.
- The implementation pair should treat `implement/feedback.md` blockers as first-class scope, not optional follow-up.

## Scope

### In scope

- Fixing the known blocking issues `IMP-001` through `IMP-009`.
- Tightening runtime invariants around `pending_input`, `active.json`, iteration numbering, and stop/interrupt behavior.
- Hardening provider and shell invocation so the actual subprocess behavior matches persisted artifacts and stop semantics.
- Fixing policy enforcement so unchanged escape symlinks do not fail runs, while child mutations under `.reflow/` remain visible and rejectable.
- Adding regression tests that exercise the above paths without depending on real external provider CLIs.
- Minimal README adjustments only if implementation changes reveal mismatched operator guidance.

### Out of scope

- Redesigning the workflow model, run layout, or CLI surface beyond conformance fixes.
- Feature expansion beyond the v1.2 SAD.
- Editing `.superloop/.../plan/criteria.md`.
- Broad repository refactors unrelated to Reflow runtime correctness.

## Code areas expected to change

- [reflow.py](/home/marcelo/code/docloop/reflow.py)
- [reflow_runtime/controller.py](/home/marcelo/code/docloop/reflow_runtime/controller.py)
- [reflow_runtime/providers.py](/home/marcelo/code/docloop/reflow_runtime/providers.py)
- [reflow_runtime/policy.py](/home/marcelo/code/docloop/reflow_runtime/policy.py)
- [reflow_runtime/storage.py](/home/marcelo/code/docloop/reflow_runtime/storage.py)
- [reflow_runtime/protocol.py](/home/marcelo/code/docloop/reflow_runtime/protocol.py)
- [tests/test_reflow_runtime.py](/home/marcelo/code/docloop/tests/test_reflow_runtime.py)
- [README.md](/home/marcelo/code/docloop/README.md) only if behavior or operational expectations change materially

## Stable interfaces to preserve

### CLI entrypoints

The CLI surface remains:

```text
python3 reflow.py run <workflow> [--workspace <path>] [--full-auto]
python3 reflow.py resume <run_id> [--workspace <path>] [--full-auto]
python3 reflow.py reply <run_id> [--workspace <path>] [--full-auto]
python3 reflow.py status <run_id> [--workspace <path>]
python3 reflow.py stop <run_id> [--workspace <path>]
python3 reflow.py list [--workspace <path>]
```

Exit codes remain:

- `0`: success or completed action
- `20`: provider unavailable
- `21`: step failed
- `22`: max loops exceeded
- `23`: max cycles exceeded
- `24`: blocked
- `25`: config, command-state, or internal error
- `26`: awaiting input
- `27`: stopped

`status` must continue to print at least:

- `run_id`
- `workflow`
- `status`
- `current_step`
- `cycle_count`
- `started_at`
- `updated_at`
- when awaiting input: `pending_step`, `pending_loop`, `pending_question_count`, `pending_auto_round`
- when failed: `failure_type`, `failure_reason`

`list` must continue to enumerate `.reflow/runs/` only and sort rows by `started_at` descending.

### Runtime functions

These entrypoints stay stable:

```python
load_config(workspace: Path) -> ReflowConfig
load_workflow(workspace: Path, workflow_name: str, config: ReflowConfig) -> Workflow
run_new_workflow(workspace: Path, workflow_name: str, full_auto: bool) -> int
resume_run(workspace: Path, run_id: str, full_auto: bool) -> int
reply_to_run(workspace: Path, run_id: str, full_auto: bool) -> int
stop_run(workspace: Path, run_id: str) -> int
status_run(workspace: Path, run_id: str) -> int
list_runs(workspace: Path) -> int
```

Supporting contracts that should remain centralized after the fixes:

```python
render_agent_request(...)
parse_agent_outcome(...)
parse_full_auto_answers(...)
build_provider_argv(...)
build_shell_argv(...)
invoke_provider(...)
invoke_shell(...)
evaluate_policy(...)
RunStore.write_active(...)
RunStore.reserve_iteration(...)
RunStore.finalize_iteration(...)
RunStore.reconcile_reserved_iteration(...)
```

### Persistence and artifact contract

The runtime continues to own these artifacts:

- `.reflow/config.yaml`
- `.reflow/active.json`
- `.reflow/workflows/<workflow>/workflow.yaml`
- `.reflow/runs/<run_id>/run.json`
- `.reflow/runs/<run_id>/history.jsonl`
- `.reflow/runs/<run_id>/operator_inputs.md`
- `.reflow/runs/<run_id>/steps/<step>/<loop>/request.txt`
- `.reflow/runs/<run_id>/steps/<step>/<loop>/command.txt`
- `.reflow/runs/<run_id>/steps/<step>/<loop>/stdout.txt`
- `.reflow/runs/<run_id>/steps/<step>/<loop>/stderr.txt`
- `.reflow/runs/<run_id>/steps/<step>/<loop>/final.txt`
- `.reflow/runs/<run_id>/steps/<step>/<loop>/meta.json`

Required behavioral details to preserve or enforce:

- Shell steps must execute and persist the exact same argv: `["/bin/sh", "-lc", "<cmd>"]`.
- Shell-step child env must include `REFLOW_RUN_ID`, `REFLOW_WORKFLOW`, `REFLOW_STEP`, `REFLOW_LOOP`, `REFLOW_WORKSPACE`, and `REFLOW_ITERATION_DIR`.
- `meta.json.command_argv` and `meta.json.command_text` must match the actual shell invocation.
- `pending_input` may exist only when `run.status == "awaiting_input"`.
- Full-auto answer passes are not workflow iterations: they must not increment `step_loops`, must not increment `cycle_count`, and must not create a step iteration directory.
- `active.json` must represent the live controller-owned run and, while a provider or shell child is active, must carry the live child PID needed by `stop` and interrupt handling.
- Policy evaluation must inspect child-authored workspace mutations, including `.reflow/` writes, while avoiding false positives from unchanged pre-existing escape symlinks.

## Milestones

### Milestone 1: Controller-state and stop-path correctness

Goal: make run state, lock state, and terminalization behavior trustworthy under interruption and input waits.

Deliverables:

- Fix `pending_input` lifecycle so `awaiting_input` is persisted before any new `pending_input` record is saved or `auto_round` is incremented.
- Route `KeyboardInterrupt` and SIGINT through the same stop reconciliation path used by `reflow stop`.
- Ensure `reply` is covered by the same stop guard during pre-drive input resolution, not only once `_drive_run()` starts.
- Keep `active.json` aligned with the live run status while waiting for input and while child processes are active.
- Verify iteration reconciliation records `interrupted` metadata and clears stale active locks when runs stop.

Acceptance criteria:

- Interrupting `run`, `resume`, or `reply` leaves the run terminalized as `stopped`, reconciles any reserved iteration to `interrupted`, and removes or updates `active.json` appropriately.
- No persisted `run.json` state exists where `pending_input` is present while status is `running`.
- `reply` interrupted during inline prompt collection or full-auto answer collection exits `27` and leaves the run `stopped`, not `awaiting_input`.
- Tests cover both controller-level stop flow and direct `reflow stop <run_id>` behavior against live controller and child PID state.

### Milestone 2: Iteration, protocol, and provider/shell conformance

Goal: eliminate runtime/spec drift in loop numbering, malformed control retries, and child-process execution.

Deliverables:

- Reserve or otherwise determine the next loop number before rendering the agent footer so `request.txt` and persisted iteration metadata agree.
- Implement malformed control-output retry behavior for agent steps: finalize the current iteration as failed, attach a warning to the next request, and only terminalize on actual loop-budget exhaustion.
- Centralize process launching so provider and shell invocations share consistent child PID publication, timeout handling, interrupt termination, and artifact recording.
- Verify provider wrapper behavior for both Codex and Claude command construction, merged env handling, and timeout propagation.
- Confirm full-auto answer parsing and retry/wait transitions keep step-loop accounting unchanged.

Acceptance criteria:

- The first request for a step advertises loop `1`, and every subsequent retry/restart request matches the reserved iteration directory number.
- One malformed `<questions>` or invalid decision tag does not immediately terminalize the run while retry budget remains.
- Provider and shell subprocesses are launched via one consistent path that publishes `child_pid` before waiting and clears it afterwards.
- `stop` and Ctrl+C terminate the actual live child process before the run is marked `stopped`.
- Tests assert exact argv for Codex, Claude, and shell paths, plus timeout/env behavior without requiring real provider CLIs.
- Full-auto tests prove no extra workflow iteration directory is created and no `step_loops` increment occurs during auto-answer passes.

### Milestone 3: Policy enforcement closure and verifier-facing regression coverage

Goal: close the remaining correctness and safety blockers in policy enforcement and prove the runtime is ready for re-review.

Deliverables:

- Fix `snapshot_workspace()` and policy diffing so unchanged escape symlinks do not fail no-op steps.
- Ensure child writes under `.reflow/` are visible to policy evaluation and can trigger `allow_write` / `forbid_write` failures.
- Preserve controller-owned writes as exempt only where the controller itself created or updated them as part of normal runtime bookkeeping.
- Add focused tests for the `IMP-008` and `IMP-009` cases, plus an integration-style path that combines workflow execution, policy enforcement, and terminal failure reporting.
- Re-run focused Reflow tests and, if practical, the broader repository suite after changes stabilize.

Acceptance criteria:

- A pre-existing symlink that resolves outside the workspace does not fail a no-op iteration unless the iteration changed that path or wrote through it.
- A child step that mutates `.reflow/config.yaml`, `.reflow/active.json`, or run artifacts is detected by policy enforcement and fails the step.
- Policy tests differentiate controller-authored bookkeeping from child-authored state tampering.
- The implementation task’s known blockers `IMP-008` and `IMP-009` are explicitly covered by regression tests.

## Test strategy

The implementation pair should add or adjust tests in [tests/test_reflow_runtime.py](/home/marcelo/code/docloop/tests/test_reflow_runtime.py) rather than creating a parallel suite.

Required coverage additions:

- Interrupt/stop tests for `run`, `resume`, and `reply`, including child subprocess termination and reserved-iteration reconciliation.
- Pending-input invariant tests covering interactive wait, full-auto success, full-auto failure, and interrupted reply flows.
- Malformed-control retry tests proving the run stays non-terminal until loop budget is exhausted and the next request carries a warning.
- Loop-number/request-footer tests proving `request.txt` loop values match iteration directory numbering.
- Provider-wrapper tests for Codex and Claude argv, merged `env`, `timeout_sec`, unavailable-command behavior, and shell argv consistency.
- Policy tests for unchanged escape symlinks, writes through escaping paths, and child-authored `.reflow/` mutations.
- End-to-end tests that cover a successful path, a blocked/awaiting-input path, a protocol-retry path, and a policy-failure path.

Suggested verification command sequence:

```text
pytest -q tests/test_reflow_runtime.py tests/test_refined_reflow_sad.py
pytest -q
```

The broader `pytest -q` run is desirable but secondary if unrelated repository failures already exist.

## Implementation order

1. Fix stop and state-invariant issues in `controller.py`, `providers.py`, and `storage.py` first, because they affect every other workflow path.
2. Add failing tests for interrupt handling, `pending_input` state order, and live child PID ownership before or alongside those fixes.
3. Fix iteration numbering and malformed-control retry behavior in `controller.py` and `protocol.py`.
4. Centralize provider/shell subprocess execution details and lock the exact shell/provider artifact contract with tests.
5. Patch `policy.py` so change-based escape detection and `.reflow/` child-write visibility are both correct.
6. Re-run focused tests, then broader tests if feasible, and sync README only if operator-facing behavior changed.

## Risks and controls

| ID | Risk | Impact | Control |
| --- | --- | --- | --- |
| R1 | Stop-path fixes leave stale `active.json` or half-finalized iterations | Resume/stop semantics become nondeterministic | Add interrupt-path tests first, route all stop paths through one reconciliation helper, and verify `active.json` after every terminal path |
| R2 | Child PID tracking is updated too late or cleared too early | `stop` marks runs stopped while children keep mutating the workspace | Publish `child_pid` immediately after `Popen`, clear it in `finally`, and assert actual child termination in tests |
| R3 | Malformed-control retry logic corrupts loop accounting | False `max_loops_exceeded` or mismatched request footer/iteration state | Reserve iteration once, finalize it once, and assert `request.txt` loop numbers and `step_loops` at each retry |
| R4 | Policy filtering over-corrects and hides real `.reflow/` tampering | Safety regression despite passing happy-path tests | Separate controller-authored bookkeeping from child diffs explicitly; add negative tests for `.reflow` mutations |
| R5 | Policy escape detection remains too broad | Benign repos with existing escape symlinks fail unexpectedly | Base escape violations on changed paths and add no-op symlink regression tests |
| R6 | README/doc sync becomes a side quest | Unnecessary churn and verifier noise | Limit docs edits to concrete operator-visible behavior changes after tests pass |

## Completion gate

This plan is complete when the implementation pair can execute it without reinterpretation:

- all currently documented blocking findings `IMP-001` through `IMP-009` are in scope
- milestones map directly to existing modules and tests
- CLI, runtime, persistence, and shell/provider contracts are explicit
- risk controls focus on the real regression surface
- the work remains incremental and does not require architectural redesign
