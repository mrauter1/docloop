# Test Author ↔ Test Auditor Feedback

## Historical finding verified fixed

- TST-001 was previously reported against `triage-stage1/tests/test_ops_app.py` for missing coverage of `POST /ops/tickets/{reference}/set-status`. Verified fixed in the current worktree: [test_ops_app.py](/workspace/docloop/triage-stage1/tests/test_ops_app.py) now covers both invalid status rejection and a successful resolve transition, including `resolved_at`, `ticket_status_history`, and `ticket_views.last_viewed_at` assertions.

## Current audit outcome

- No new blocking or non-blocking test-audit findings were identified in scoped phase-4 review.

## Phase 4 test additions

- Added `triage-stage1/tests/test_worker_phase4.py::test_worker_disables_automatic_publication_when_internal_notes_exist` to prove internal-note runs cannot auto-publish requester-visible AI replies.
- Added `triage-stage1/tests/test_worker_phase4.py::test_worker_routes_to_dev_ti_instead_of_asking_clarification_when_internal_notes_exist` to cover the stricter clarification-route downgrade when internal notes are present.
- Replaced the stale phase-3-only strategy doc with an explicit phase-4 behavior-to-test coverage map in `.superloop/tasks/autosac-prd-plan/test/test_strategy.md`.
