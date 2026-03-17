# implementation_notes.md

## Files changed

- `reflow_runtime/controller.py`
- `reflow_runtime/policy.py`
- `superloop.py`
- `tests/test_reflow_runtime.py`
- `tests/test_superloop_observability.py`
- `.superloop/tasks/implement-refined-reflow-v1-2-sad-md-as-function-d391842d/implement/implementation_notes.md`

## Checklist mapping

- Added isolated `reflow.py` CLI and `reflow_runtime/` package: previously complete, unchanged in this pass
- Added `requirements.txt` and README dependency instructions for `PyYAML`: previously complete, unchanged in this pass
- Implemented config and workflow validators matching the v1.2 schema surface used by runtime/tests: previously complete, unchanged in this pass
- Implemented storage helpers for `.reflow/`, atomic writes, run creation, history, operator inputs, and interrupted-iteration reconciliation: previously complete, unchanged in this pass
- Implemented run-state models including `pending_input`: completed with an additional invariant fix so terminalized runs now clear `pending_input`
- Implemented provider resolution and Codex/Claude wrapper argv construction and invocation: previously complete, unchanged in this pass
- Implemented agent request rendering and protocol parsers for tagged transitions, `<questions>`, and `<answers>`: previously complete, unchanged in this pass
- Implemented shell-step runner with required `REFLOW_*` variables and command artifact persistence: completed with policy snapshot filtering that exempts only the active iteration transport subtree while keeping other child-authored `.reflow/` mutations visible
- Implemented `status` / `list` minimum fields and `started_at` descending ordering: previously complete, unchanged in this pass
- Implemented step-loop, cycle, retry, and terminal-state logic: complete, with stop handling now trapping both `SIGINT` and `SIGTERM` through the same terminalization path
- Implemented operator-input lifecycle, `resume`, `reply`, and `--full-auto`: complete, with pre-`_drive_run` `reply` interruptions now stop-guarded
- Implemented `stop`: complete, with controller signal handling aligned to the same reconciliation path as explicit stop requests
- Implemented policy and required-file enforcement: complete, with unchanged escape symlinks ignored, active iteration transport artifacts exempted from diffs, and other child-authored `.reflow/` writes exposed to `allow_write` / `forbid_write`
- Added unit and integration-style tests with fake provider CLIs and shell fixtures: complete, with new regression coverage for unchanged escape symlinks, active iteration artifact filtering, `.reflow` tampering, and `SIGTERM` stop handling
- Restored filesystem-safe intent-derived Superloop task IDs while preserving long explicit task IDs for resume compatibility: complete, with bounded intent slugs plus hash-based uniqueness coverage
- Updated README with runtime usage and dependency requirements: previously complete, unchanged in this pass
- Minimal runtime-reference doc changes only: complete via README only
- Deferred checklist items: none

## Assumptions

- JSON-formatted `.yaml` files are accepted as a fallback when `PyYAML` is unavailable, because JSON is valid YAML 1.2 and the execution environment here does not have `PyYAML` preinstalled.
- `status` and `list` remain human-readable text, not a machine-stable format, per the SAD.
- Inline answer collection is gated by `sys.stdin.isatty()`; otherwise runs fall back to persisted `awaiting_input`.
- `stop` finalizes the run from persisted state and best-effort SIGTERM delivery instead of requiring in-process controller cooperation.
- `KeyboardInterrupt`, `SIGINT`, and controller-targeted `SIGTERM` during `run`/`resume`/`reply` are treated as operator stop requests and terminalize the run through the same reconciliation path as `reflow stop`, including interruptions that happen in `reply` before `_drive_run(...)` begins.
- Policy enforcement should ignore controller-authored reservation bookkeeping by snapshotting after iteration reservation but before the child process runs, rather than by globally excluding `.reflow/`.
- Provider-owned transport files inside the currently reserved iteration directory are treated as controller/runtime artifacts for policy purposes; writes elsewhere under `.reflow/` remain subject to policy enforcement.
- Intent-derived task IDs may be truncated because uniqueness comes from the appended content hash; explicit `--task-id` values remain unbounded aside from normal slug normalization.

## Expected side effects

- `reply` now stops and reconciles the run if the operator hits Ctrl+C during inline prompting or during the pre-`_drive_run` full-auto answer pass.
- Terminal run states clear `pending_input`, preserving the invariant that pending input only exists while `status == awaiting_input`.
- Long-running controllers now convert either terminal keyboard signals into the same stopped-state reconciliation path used by explicit `reflow stop`.
- No-op runs in repositories that already contain escape symlinks no longer fail solely because the symlink exists.
- Child steps that mutate `.reflow/` outside controller-authored bookkeeping now fail policy evaluation instead of slipping past snapshots.
- Agent and shell steps with restrictive `allow_write` policies no longer fail solely because the provider updated `stdout.txt`, `stderr.txt`, `final.txt`, or `meta.json` inside the active iteration directory.
- Very long `--intent` values now produce bounded task directory names that stay under common filesystem filename limits, while long explicit `--task-id` values still resolve to their full normalized slug.

## Deduplication and centralization decisions

- Kept interrupt handling centralized in `reflow_runtime/controller.py` by extending the existing stop-guard wrapper to install temporary `SIGINT` / `SIGTERM` handlers around controller-owned execution phases, rather than duplicating terminalization logic in each command path.
- Centralized policy filtering in `snapshot_workspace(...)` using an explicit ignored-path set, and the controller now supplies only the active iteration directory. That keeps iteration transport artifacts out of policy diffs without hiding unrelated `.reflow/` tampering.
- Kept explicit and intent-derived task-ID behavior separated in `superloop.py`: `slugify_task(...)` still normalizes caller-supplied IDs without truncation, while `derive_intent_task_id(...)` now applies the filesystem-safety bound before appending the hash.
