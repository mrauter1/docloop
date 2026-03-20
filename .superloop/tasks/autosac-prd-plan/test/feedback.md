# Test Author ↔ Test Auditor Feedback

## Historical finding verified fixed

- TST-001 was previously reported against `triage-stage1/tests/test_ops_app.py` for missing coverage of `POST /ops/tickets/{reference}/set-status`. Verified fixed in the current worktree: [test_ops_app.py](/workspace/docloop/triage-stage1/tests/test_ops_app.py) now covers both invalid status rejection and a successful resolve transition, including `resolved_at`, `ticket_status_history`, and `ticket_views.last_viewed_at` assertions.

## Current audit outcome

- No new blocking or non-blocking test-audit findings were identified in scoped phase-4 review.

## Phase 4 test additions

- Added `triage-stage1/tests/test_worker_phase4.py::test_worker_disables_automatic_publication_when_internal_notes_exist` to prove internal-note runs cannot auto-publish requester-visible AI replies.
- Added `triage-stage1/tests/test_worker_phase4.py::test_worker_routes_to_dev_ti_instead_of_asking_clarification_when_internal_notes_exist` to cover the stricter clarification-route downgrade when internal notes are present.
- Replaced the stale phase-3-only strategy doc with an explicit phase-4 behavior-to-test coverage map in `.superloop/tasks/autosac-prd-plan/test/test_strategy.md`.

## Phase 5 test additions

- Added focused operability coverage in `triage-stage1/tests/test_phase5_operability.py` for bootstrap success and missing-mount failure, CLI happy/error paths, readiness before/after bootstrap, readiness DB failure reporting, worker heartbeat persistence, and `run_web.py` / `run_worker.py` argument delegation.
- Replaced the phase-4 strategy section with an explicit phase-5 behavior-to-test coverage map in `.superloop/tasks/autosac-prd-plan/test/test_strategy.md`.

## Phase 5 audit outcome

- No new blocking or non-blocking test-audit findings were identified in scoped phase-5 review. The added tests provide deterministic coverage for the changed operability contract and the updated strategy doc matches the implemented assertions.

## Phase 6 test additions

- Added requester-session and unread-tracking coverage in `triage-stage1/tests/test_requester_app.py` for remember-me cookie persistence, expired-session rejection, and requester unread-marker clearing after the detail view is opened.
- Added helper-level upload-limit coverage in `triage-stage1/tests/test_uploads.py` for max-file and max-size enforcement without relying on multipart transport edge behavior.
- Added worker queue and draft-regression coverage in `triage-stage1/tests/test_worker_phase4.py` for manual rerun bypassing hash-based skip and for superseding older pending drafts when a newer AI draft is created.
- Replaced the phase-5 strategy section with an explicit phase-6 behavior-to-test coverage map in `.superloop/tasks/autosac-prd-plan/test/test_strategy.md`, including stabilization notes and reused CLI/bootstrap coverage.

## Phase 6 audit outcome

- No new blocking or non-blocking test-audit findings were identified in scoped phase-6 review. The updated strategy matches the phase-6 acceptance scope, the new tests add deterministic coverage for the requested high-risk behaviors, and the referenced Stage 1 suite result remains green at `53 passed`.
