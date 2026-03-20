# implementation_notes.md

## Files changed

- `triage-stage1/.env.example`
- `triage-stage1/README.md`
- `triage-stage1/shared/security.py`
- `triage-stage1/shared/permissions.py`
- `triage-stage1/shared/models.py`
- `triage-stage1/shared/tickets.py`
- `triage-stage1/shared/bootstrap.py`
- `triage-stage1/shared/logging.py`
- `triage-stage1/shared/user_admin.py`
- `triage-stage1/shared/workspace_contract.py`
- `triage-stage1/app/auth.py`
- `triage-stage1/app/main.py`
- `triage-stage1/app/render.py`
- `triage-stage1/app/routes_auth.py`
- `triage-stage1/app/routes_ops.py`
- `triage-stage1/app/routes_requester.py`
- `triage-stage1/app/uploads.py`
- `triage-stage1/app/templates/base.html`
- `triage-stage1/app/templates/login.html`
- `triage-stage1/app/templates/ops/board.html`
- `triage-stage1/app/templates/ops/detail.html`
- `triage-stage1/app/templates/tickets/list.html`
- `triage-stage1/app/templates/tickets/new.html`
- `triage-stage1/app/templates/tickets/detail.html`
- `triage-stage1/app/static/styles.css`
- `triage-stage1/tests/test_models.py`
- `triage-stage1/tests/test_ops_app.py`
- `triage-stage1/tests/test_security.py`
- `triage-stage1/tests/test_requester_app.py`
- `triage-stage1/tests/test_uploads.py`
- `triage-stage1/requirements.txt`
- `triage-stage1/worker/codex_runner.py`
- `triage-stage1/worker/main.py`
- `triage-stage1/worker/queue.py`
- `triage-stage1/worker/ticket_loader.py`
- `triage-stage1/worker/triage.py`
- `triage-stage1/tests/test_worker_phase4.py`
- `triage-stage1/scripts/__init__.py`
- `triage-stage1/scripts/_common.py`
- `triage-stage1/scripts/bootstrap_workspace.py`
- `triage-stage1/scripts/create_admin.py`
- `triage-stage1/scripts/create_user.py`
- `triage-stage1/scripts/set_password.py`
- `triage-stage1/scripts/deactivate_user.py`
- `triage-stage1/scripts/run_web.py`
- `triage-stage1/scripts/run_worker.py`
- `triage-stage1/tests/test_phase5_operability.py`
- `triage-stage1/docs/acceptance_matrix.md`
- `triage-stage1/docs/manual_verification.md`

## Checklist mapping

- Phase-2 item: implement `shared/security.py` and `shared/permissions.py`
  - Completed in `shared/security.py` and `shared/permissions.py`.
- Phase-2 item: implement Argon2id password verification, opaque server-side sessions, remember-me expiry handling, and CSRF protection
  - Completed in `shared/security.py`, `app/auth.py`, and `app/routes_auth.py`.
- Phase-2 item: build `app/main.py`, auth routes, requester routes, templates, and forms
  - Completed in `app/main.py`, `app/routes_auth.py`, `app/routes_requester.py`, and the new template/static files.
- Phase-2 item: implement multipart parsing with explicit limits, image validation, SHA-256 hashing, and protected file serving
  - Completed in `app/uploads.py` and `app/routes_requester.py`.
- Phase-2 item: implement ticket creation and requester reply transactions, including queue row creation or requeue flag updates
  - Completed in `shared/tickets.py` and used by `app/routes_requester.py`.
- Deliverable: tests
  - Added focused security tests and requester integration tests in `tests/test_security.py` and `tests/test_requester_app.py`.
  - Added a reviewer-driven regression test proving requester detail renders only public attachments.
- Phase-3 item: implement `/ops`, `/ops/board`, and `/ops/tickets/{reference}` with grouped status columns and required filters
  - Completed in `app/routes_ops.py`, `app/templates/ops/board.html`, `app/templates/ops/detail.html`, and shared layout/style updates.
- Phase-3 item: implement Dev/TI public replies, internal notes, assignment changes, manual status changes, and manual rerun requests
  - Completed in `app/routes_ops.py` using the existing shared ticket mutation helpers in `shared/tickets.py`.
- Phase-3 item: implement AI draft approval/publish and rejection flows
  - Completed in `app/routes_ops.py` with state transitions enforced by `shared/tickets.py`.
- Phase-3 item: render AI analysis, relevant paths, and internal/public threads while preserving requester isolation
  - Completed in `app/routes_ops.py` and `app/templates/ops/detail.html`.
- Deliverable: phase-3 tests
  - Added `tests/test_ops_app.py` covering ops board filters, human actions, draft review flows, and ticket view timestamp rules.
  - Updated `shared/models.py` so SQLite test metadata honors the same active-run partial unique predicate as PostgreSQL.
- Phase-4 item: implement worker polling, oldest-pending acquisition, and safe active-run lifecycle transitions
  - Completed in `worker/main.py` and `worker/queue.py` with pending-run claiming, `FOR UPDATE SKIP LOCKED` on PostgreSQL, `running/skipped/succeeded/failed/superseded` transitions, and deferred requeue handling.
- Phase-4 item: compute the automatic-trigger/publication fingerprints and apply skip, superseded, and requeue behavior
  - Completed in `worker/ticket_loader.py` and `worker/main.py`; the worker compares the pre-run fingerprint for skip decisions and stores the post-`ai_triage` fingerprint for publication suppression so the run does not supersede itself on the worker-owned status transition.
- Phase-4 item: write exact workspace artifacts, prompt/schema files, and read-only Codex CLI invocation
  - Completed in `worker/codex_runner.py` with exact `AGENTS.md`, exact repo skill text, exact JSON schema text, prompt generation, per-run artifact directories, and the required Codex flags.
- Phase-4 item: publish exactly one internal AI note, apply one action path, and handle failures safely
  - Completed in `worker/triage.py` and `worker/main.py` with structured output validation, single-note publication, action-specific status/message/draft updates, and internal failure notes routed to `waiting_on_dev_ti`.
- Reviewer finding IMP-003: prevent automatic public replies from disclosing internal-only details
  - Completed in `worker/triage.py` and `worker/main.py` with a shared publication-time guard that makes any run containing internal notes ineligible for automatic requester-visible AI publication.
- Deliverable: phase-4 tests
  - Added `tests/test_worker_phase4.py` covering artifact generation, successful publication, stale-run suppression with deferred requeue, skip-on-hash, failure-note behavior, and automatic-publication downgrading when internal notes exist.
- Phase-5 item: implement workspace bootstrap, git initialization, empty initial commit creation, mount verification, and exact workspace guidance files
  - Completed in `shared/bootstrap.py`, `shared/workspace_contract.py`, `worker/codex_runner.py`, and `scripts/bootstrap_workspace.py`.
- Phase-5 item: implement CLI administration for admin creation, user creation, password reset, and deactivation
  - Completed in `shared/user_admin.py` plus `scripts/create_admin.py`, `scripts/create_user.py`, `scripts/set_password.py`, and `scripts/deactivate_user.py`.
- Phase-5 item: implement health/readiness, structured JSON logging, and runnable web/worker entrypoints
  - Completed in `shared/logging.py`, `app/main.py`, `worker/main.py`, `scripts/run_web.py`, and `scripts/run_worker.py`.
- Phase-5 item: document required environment/runtime defaults and add operability tests
  - Completed in `README.md`, `.env.example`, and `tests/test_phase5_operability.py`.
- Phase-6 item: add regression coverage for session behavior, upload limits, unread tracking, draft supersession, and manual-rerun worker behavior
  - Completed in `tests/test_requester_app.py`, `tests/test_uploads.py`, and `tests/test_worker_phase4.py`.
- Phase-6 item: trace AC1-AC19 to implementation and verification paths
  - Completed in `docs/acceptance_matrix.md` and linked from `README.md`.
- Phase-6 item: provide a concise operator bootstrap/run/manual acceptance checklist
  - Completed in `README.md` and `docs/manual_verification.md`.

## Assumptions

- Login CSRF uses a signed double-submit cookie because the PRD requires CSRF on all POST forms, while the schema only defines authenticated server-side sessions and does not include anonymous pre-login session records.
- SQLite is used only for automated tests; session expiry normalization in `app/auth.py` handles SQLite's naive datetime round-trip without changing the intended PostgreSQL runtime behavior.
- `app/main.py` now exposes only `create_app(...)` and no longer substitutes a blank fallback app on configuration errors; missing required settings are intentionally fail-fast again.
- The ops detail page opportunistically reads `ai_runs.final_output_path` when present to render `relevant_paths`; until phase 4 writes those artifacts, the UI shows an explicit empty state instead of inventing path data.
- The SQLite metadata path now declares the same active-run partial unique predicate as PostgreSQL so local tests match the one-active-run invariant instead of collapsing into a full unique-per-ticket constraint.
- The PRD’s fingerprint rules include `tickets.status`, while the worker also transitions tickets to `ai_triage` when execution starts. To avoid every fresh `new` ticket superseding itself, the worker uses the pre-start fingerprint only for skip detection and persists the post-transition fingerprint as `ai_runs.input_hash`, which is the value later compared during stale-run suppression.
- To satisfy AC-P4-3 reliably, the worker now treats internal-note context as incompatible with automatic requester-visible publication. Runs with internal notes may still produce internal summaries and pending drafts, but they no longer auto-send AI replies to requesters.
- The bootstrap version value is not prescribed by the PRD, so the bootstrap script defaults it to `1.2-custom-final` while still allowing an override via `--bootstrap-version`.
- Readiness now treats missing uploads/workspace paths or mismatched `AGENTS.md` / `SKILL.md` content as a hard not-ready state, which keeps operations aligned with the exact workspace contract rather than only checking for directory existence.
- The new upload helper tests instantiate Starlette `UploadFile` objects directly so the file-count and file-size limits are exercised deterministically without depending on framework exception formatting from oversized multipart requests.

## Expected side effects

- `triage-stage1/requirements.txt` now requires `httpx` and `python-multipart` in addition to the existing Phase 1 dependencies.
- Requester GET `/app/tickets/{reference}` now updates `ticket_views.last_viewed_at` and commits that change immediately.
- Ticket creation and requester reply paths now create/persist `ai_runs`, `ticket_status_history`, `ticket_views`, and `ticket_attachments` rows as part of the phase-2 requester workflow.
- Protected attachments are stored under the configured `UPLOADS_DIR` and are only served through authenticated requester ownership checks.
- Requester ticket detail now filters rendered attachments to `visibility='public'` instead of assuming all attachments linked to public messages are safe to show.
- Dev/TI users now have `/ops` and `/ops/board` surfaces with grouped status columns, required filters, and a ticket detail page that separates public and internal threads.
- Dev/TI mutation routes now update `ticket_views.last_viewed_at` through shared helpers on successful assignment, status, reply, note, rerun, and draft review actions.
- SQLite-backed automated tests can now create multiple historical `ai_runs` rows for a ticket as long as only one is `pending` or `running`, matching the intended PostgreSQL invariant.
- Worker runs now materialize prompt/schema/final-output/stdout/stderr artifacts under `TRIAGE_WORKSPACE_DIR/runs/{ticket_id}/{run_id}/` and keep exact `AGENTS.md` plus `.agents/skills/stage1-triage/SKILL.md` synchronized in the workspace root.
- The worker now updates ticket classification fields, persists canonical internal AI notes, creates safe public AI messages or pending drafts, and routes failed runs to internal review without publishing requester-visible AI output.
- Automatic public AI actions are now disabled whenever the run includes internal note context; those runs are downgraded to a pending draft or internal-only routing path before any requester-visible publication.
- `worker/main.py` now exposes a real loop entrypoint with heartbeat updates in `system_state.worker_heartbeat` and a `once` mode that tests can exercise without spawning background processes.
- The workspace bootstrap path now creates the upload directory, validates the repo/manual mounts, initializes the workspace Git repository, creates an empty initial commit when needed, writes the exact agent guidance files, and records `system_state.bootstrap_version`.
- The web app now exposes `/healthz` and `/readyz`; readiness fails closed when the database is unreachable or required uploads/workspace artifacts are missing.
- Web and worker service logs now emit JSON payloads through a shared formatter, and the web app records per-request method/path/status/duration entries through middleware.
- Dedicated CLI scripts now provide the required local user-management operations without adding any web-based admin surface.
- The Stage 1 README now documents a clean local bootstrap flow: virtualenv setup, dependency install, Alembic migration, workspace bootstrap, user creation, and separate web/worker startup commands.
- Acceptance traceability now lives in versioned repository docs instead of relying on ad hoc phase-log prose.

## Deduplication / centralization decisions

- Session/token/password/CSRF behavior is centralized in `shared/security.py` and `app/auth.py` rather than duplicated across routes.
- Ticket mutation logic for create/reply/resolve behavior is centralized in `shared/tickets.py`, so requester routes stay thin and later phases can reuse the same invariants.
- Dev/TI mutation routes reuse the same `shared/tickets.py` helpers for assignment, status history, view tracking, rerun queuing, and draft state transitions rather than open-coding those invariants per endpoint.
- Multipart/image validation and attachment persistence are centralized in `app/uploads.py` rather than embedded in individual POST handlers.
- Markdown-to-safe-HTML and markdown-to-plain-text normalization are centralized in `app/render.py`.
- Worker prompt/schema/artifact generation is centralized in `worker/codex_runner.py` rather than being split between queue, runner, and publication code.
- Ticket loading plus fingerprint computation is centralized in `worker/ticket_loader.py`, so skip and superseded decisions use one canonical serialization path.
- AI output validation and action-specific publication logic is centralized in `worker/triage.py`, keeping `worker/main.py` focused on orchestration and terminal-state handling.
- Internal/public leak detection for requester-visible AI messages is centralized in `worker/triage.py` instead of being duplicated across each action path.
- Workspace bootstrap, readiness checks, exact agent artifact paths, and bootstrap-version persistence are centralized in `shared/bootstrap.py` instead of being partially duplicated between scripts and the worker.
- JSON log formatting is centralized in `shared/logging.py`, and account-management mutations are centralized in `shared/user_admin.py`.
- Acceptance traceability and manual smoke verification are centralized in `docs/acceptance_matrix.md` and `docs/manual_verification.md` so the PRD acceptance set has one auditable operator-facing home.

## Intentionally deferred

- None within the scoped phase-5 contract.

## Verification status

- Verified the scoped Stage 1 suite in a local `triage-stage1/.venv` using:
  - `.venv/bin/pytest -q tests/test_phase5_operability.py tests/test_config.py tests/test_worker_phase4.py tests/test_ops_app.py tests/test_requester_app.py tests/test_security.py tests/test_models.py tests/test_ticket_helpers.py tests/test_uploads.py`
- Result after the phase-6 hardening edits: `53 passed in 32.54s`.
- Also verified module syntax with:
  - `python -m compileall triage-stage1`
- Phase-6 focused verification target:
  - `pytest -q triage-stage1/tests`
- The temporary `triage-stage1/.venv` used for validation was removed after the run so it is not part of the deliverable worktree.
