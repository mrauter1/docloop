# Stage 1 Acceptance Matrix

This matrix maps PRD acceptance criteria AC1-AC19 to the primary implementation surfaces and their current verification path.

| AC | Requirement | Primary code paths | Automated verification | Manual verification |
| --- | --- | --- | --- | --- |
| AC1 | Local login with optional remember-me | `app/routes_auth.py`, `app/auth.py`, `shared/security.py` | `tests/test_requester_app.py`, `tests/test_security.py` | [manual_verification.md](/workspace/docloop/triage-stage1/docs/manual_verification.md) steps 1-2 |
| AC2 | PostgreSQL-backed opaque server-side sessions | `app/auth.py`, `shared/models.py`, `shared/security.py` | `tests/test_requester_app.py`, `tests/test_models.py` | steps 1-2 |
| AC3 | Requester can only see own tickets and public content | `app/routes_requester.py`, `shared/permissions.py` | `tests/test_requester_app.py` | steps 3-4 |
| AC4 | New ticket with optional title, urgency, and PNG/JPEG images | `app/routes_requester.py`, `app/uploads.py`, `shared/tickets.py` | `tests/test_requester_app.py`, `tests/test_uploads.py` | step 3 |
| AC5 | Vague ticket produces clarification questions and `waiting_on_user` | `worker/main.py`, `worker/triage.py` | `tests/test_worker_phase4.py` | step 7 |
| AC6 | Clear support/access ticket gets safe auto-reply | `worker/main.py`, `worker/triage.py` | `tests/test_worker_phase4.py` | step 7 |
| AC7 | Safe public confirm-and-route to Dev/TI | `worker/main.py`, `worker/triage.py` | `tests/test_worker_phase4.py` | step 7 |
| AC8 | Bug/feature route publishes one internal AI note and moves to Dev/TI | `worker/main.py`, `worker/triage.py` | `tests/test_worker_phase4.py` | step 7 |
| AC9 | AI drafts can be approved or rejected | `app/routes_ops.py`, `shared/tickets.py`, `worker/triage.py` | `tests/test_ops_app.py`, `tests/test_worker_phase4.py` | step 6 |
| AC10 | Requesters never see internal notes or internal AI analysis | `app/routes_requester.py`, `shared/permissions.py` | `tests/test_requester_app.py`, `tests/test_ops_app.py` | steps 4 and 6 |
| AC11 | Automatic public AI replies never leak internal-only facts | `worker/triage.py`, `worker/main.py` | `tests/test_worker_phase4.py`, `tests/test_ops_app.py` | steps 6-7 |
| AC12 | Repo-aware read-only Codex triage over `app/` and `manuals/` | `worker/codex_runner.py`, `shared/bootstrap.py` | `tests/test_worker_phase4.py`, `tests/test_phase5_operability.py` | steps 5 and 7 |
| AC13 | No repo modification, patching, branching, or SQL Server access | `worker/codex_runner.py`, `shared/workspace_contract.py` | `tests/test_worker_phase4.py`, `tests/test_phase5_operability.py` | steps 5 and 7 |
| AC14 | Resolved ticket reopens on requester reply and requeues AI | `shared/tickets.py`, `app/routes_requester.py` | `tests/test_requester_app.py` | step 4 |
| AC15 | One active AI run per ticket with requeue behavior | `shared/models.py`, `shared/tickets.py`, `worker/queue.py`, `worker/main.py` | `tests/test_models.py`, `tests/test_ticket_helpers.py`, `tests/test_worker_phase4.py` | step 7 |
| AC16 | Stale runs are suppressed and superseded | `worker/main.py`, `worker/queue.py`, `worker/ticket_loader.py` | `tests/test_worker_phase4.py` | step 7 |
| AC17 | Uploads enforce 3-image / 5 MiB limits | `app/routes_requester.py`, `app/uploads.py`, `shared/config.py` | `tests/test_requester_app.py`, `tests/test_uploads.py` | step 3 |
| AC18 | Unread markers only clear on ticket detail or successful same-ticket POST | `app/routes_requester.py`, `app/routes_ops.py`, `shared/tickets.py` | `tests/test_requester_app.py`, `tests/test_ops_app.py` | steps 4 and 6 |
| AC19 | No Kanboard, Slack, SMTP, or external notification dependency | `app/`, `worker/`, `scripts/`, `README.md` | `tests/test_phase5_operability.py` | step 8 |
