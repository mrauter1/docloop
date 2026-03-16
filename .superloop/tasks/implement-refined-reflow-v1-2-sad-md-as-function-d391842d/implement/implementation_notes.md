# implementation_notes.md

## Files changed

- `reflow_runtime/controller.py`
- `tests/test_reflow_runtime.py`
- `.superloop/tasks/implement-refined-reflow-v1-2-sad-md-as-function-d391842d/implement/implementation_notes.md`

## Checklist mapping

- Added isolated `reflow.py` CLI and `reflow_runtime/` package: previously complete, unchanged in this pass
- Added `requirements.txt` and README dependency instructions for `PyYAML`: previously complete, unchanged in this pass
- Implemented config and workflow validators matching the v1.2 schema surface used by runtime/tests: previously complete, unchanged in this pass
- Implemented storage helpers for `.reflow/`, atomic writes, run creation, history, operator inputs, and interrupted-iteration reconciliation: previously complete, unchanged in this pass
- Implemented run-state models including `pending_input`: completed with an additional invariant fix so terminalized runs now clear `pending_input`
- Implemented provider resolution and Codex/Claude wrapper argv construction and invocation: previously complete, unchanged in this pass
- Implemented agent request rendering and protocol parsers for tagged transitions, `<questions>`, and `<answers>`: previously complete, unchanged in this pass
- Implemented shell-step runner with required `REFLOW_*` variables and command artifact persistence: previously complete, unchanged in this pass
- Implemented `status` / `list` minimum fields and `started_at` descending ordering: previously complete, unchanged in this pass
- Implemented step-loop, cycle, retry, and terminal-state logic: complete, with reply-time interrupt handling now routed through stop terminalization
- Implemented operator-input lifecycle, `resume`, `reply`, and `--full-auto`: complete, with pre-`_drive_run` `reply` interruptions now stop-guarded
- Implemented `stop`: complete, with terminal stop state now clearing any lingering `pending_input`
- Implemented policy and required-file enforcement: previously complete, unchanged in this pass
- Added unit and integration-style tests with fake provider CLIs and shell fixtures: complete, with new regression coverage for interactive and full-auto `reply` interrupts
- Updated README with runtime usage and dependency requirements: previously complete, unchanged in this pass
- Minimal runtime-reference doc changes only: complete via README only
- Deferred checklist items: none

## Assumptions

- JSON-formatted `.yaml` files are accepted as a fallback when `PyYAML` is unavailable, because JSON is valid YAML 1.2 and the execution environment here does not have `PyYAML` preinstalled.
- `status` and `list` remain human-readable text, not a machine-stable format, per the SAD.
- Inline answer collection is gated by `sys.stdin.isatty()`; otherwise runs fall back to persisted `awaiting_input`.
- `stop` finalizes the run from persisted state and best-effort SIGTERM delivery instead of requiring in-process controller cooperation.
- `KeyboardInterrupt` during `run`/`resume`/`reply` is treated as an operator stop request and terminalizes the run through the same reconciliation path as `reflow stop`, including interruptions that happen in `reply` before `_drive_run(...)` begins.

## Expected side effects

- `reply` now stops and reconciles the run if the operator hits Ctrl+C during inline prompting or during the pre-`_drive_run` full-auto answer pass.
- Terminal run states clear `pending_input`, preserving the invariant that pending input only exists while `status == awaiting_input`.
- Existing Reflow behavior outside the stop/interrupt path is unchanged.

## Deduplication and centralization decisions

- Kept interrupt handling centralized in `reflow_runtime/controller.py` by adding a single stop-guard wrapper around controller-owned execution phases, rather than duplicating `KeyboardInterrupt` terminalization logic in each command path.
