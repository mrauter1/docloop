# Test Strategy

## Behavior-to-test coverage map

| Changed behavior | Coverage | Test cases |
| --- | --- | --- |
| Pre-existing escape symlinks should not fail policy evaluation unless changed | Happy path, edge case | `test_evaluate_policy_ignores_unchanged_escape_symlink` proves identical before/after snapshots with an existing out-of-workspace symlink produce no violations. |
| Child writes under `.reflow/` outside the active iteration transport subtree must still trip write policy | Failure path | `test_shell_policy_detects_child_tampering_under_reflow` mutates `.reflow/config.yaml` from a shell step and asserts terminal failure with the expected `allow_write` violation. |
| Provider/runtime transport artifacts inside the reserved iteration directory must not trip restrictive write policy | Happy path, edge case | `test_agent_policy_ignores_reserved_iteration_transport_artifacts` proves the agent path still completes under restrictive `allow_write`; `test_shell_policy_ignores_reserved_iteration_transport_artifacts` proves the same exemption on the shell path while iteration-local `.reflow/runs/...` files are updated. |
| Controller-targeted `SIGTERM` should reconcile to the same stopped state as `KeyboardInterrupt` | Failure path | `test_sigterm_uses_the_same_stop_terminalization_path` forces provider invocation to self-signal `SIGTERM` and asserts `stopped` run state, interrupted iteration metadata, and cleared `active.json`. |
| Long explicit Superloop task IDs must remain resumable | Happy path | `test_resolve_task_id_preserves_long_explicit_task_ids` and `test_resume_accepts_long_explicit_task_id` preserve the full slug for explicit IDs and verify resume succeeds against an existing long task directory. |
| Intent-derived Superloop task IDs must be filesystem-safe while staying collision-resistant | Happy path, edge case | `test_derive_intent_task_id_truncates_long_slug_but_keeps_hash_uniqueness` checks bounded length plus hash uniqueness; `test_ensure_workspace_accepts_long_intent_derived_task_ids` verifies the bounded ID can actually create task workspace artifacts. |

## Determinism and flake control

- Reflow runtime coverage uses temporary workspaces, fake provider scripts, and local filesystem mutations only; no network or wall-clock assertions are involved.
- Signal-path coverage self-signals the current process synchronously during a monkeypatched provider call, avoiding races with background subprocess timing.
- Policy assertions compare exact persisted failure reasons or terminal states to keep ordering-sensitive diffs out of scope.
