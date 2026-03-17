# Test Strategy

## Behavior-to-Test Coverage Map

| Changed behavior | Test coverage |
| --- | --- |
| `snapshot_workspace()` ignores controller-owned iteration paths passed through `ignored_paths`, including nested files and nested symlink escapes. | `tests/test_reflow_runtime.py::test_snapshot_workspace_ignores_configured_paths_and_nested_entries` validates only non-ignored workspace content is snapshotted and ignored escape symlinks do not surface as violations. |
| `evaluate_policy()` only reports escape-path violations for paths that actually changed between snapshots. | `tests/test_reflow_runtime.py::test_evaluate_policy_ignores_unchanged_escape_symlink` covers the no-op case; `tests/test_reflow_runtime.py::test_evaluate_policy_flags_changed_escape_symlink` covers the changed-path failure case. |
| Reserved iteration transport artifacts remain excluded from policy enforcement during real workflow execution. | Existing integration coverage in `tests/test_reflow_runtime.py::test_shell_policy_ignores_reserved_iteration_transport_artifacts` and `tests/test_reflow_runtime.py::test_agent_policy_ignores_reserved_iteration_transport_artifacts`. |
| Explicit Superloop task IDs are preserved even when long, while intent-derived IDs remain bounded and collision-resistant. | Existing coverage in `tests/test_superloop_observability.py::test_resolve_task_id_preserves_long_explicit_task_ids`, `::test_resume_accepts_long_explicit_task_id`, `::test_derive_intent_task_id_truncates_long_slug_but_keeps_hash_uniqueness`, and `::test_ensure_workspace_accepts_long_intent_derived_task_ids`. |
| Intent-derived task IDs trim any trailing hyphen introduced by truncation before appending the hash suffix. | `tests/test_superloop_observability.py::test_derive_intent_task_id_strips_trailing_hyphen_from_truncated_slug`. |

## Flake Risk

- These tests are deterministic and filesystem-local only. No network, sleeps, or timestamp ordering assertions were added.
- Symlink checks compare explicit before/after snapshots in a temporary workspace to avoid nondeterministic directory traversal effects.
