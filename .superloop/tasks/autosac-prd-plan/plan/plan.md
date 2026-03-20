# Stage 1 AI Triage MVP Plan

## Scope and framing

This plan covers the current in-repository implementation of the Stage 1 custom Python triage system described in the immutable request snapshot at `.superloop/tasks/autosac-prd-plan/runs/run-20260319T231229Z-10748079/request.md`.

The plan assumes:
- the PRD is authoritative and already frozen
- no later clarification entries exist in the authoritative run raw log
- implementation happens inside this repository as the isolated `triage-stage1/` subproject plus the remaining missing Stage 1 surfaces
- PostgreSQL remains the single source of truth
- Codex integration is read-only and workspace-scoped only

Confirmed implementation assumptions already validated by the request and therefore treated as settled:
- FastAPI can serve Jinja2 templates for server-rendered HTML
- Starlette `SessionMiddleware` is signed-cookie based and therefore must not be used as the primary auth/session store
- `request.form()` supports explicit multipart limits and must be called with product-aligned `max_files` and `max_part_size`
- Codex CLI supports non-interactive `exec`, `CODEX_API_KEY`, `--output-schema`, `--output-last-message`, read-only sandboxing, and repo skills under `.agents/skills`

## Repository fit and dependency analysis

Relevant repository facts observed during planning:
- the current repository is a Python tooling repo centered on `docloop.py`, `superloop.py`, tests, and planning artifacts
- the root package currently depends only on `PyYAML` and does not already include FastAPI, SQLAlchemy, Alembic, PostgreSQL, HTMX, or the Stage 1 web/worker structure
- `triage-stage1/` now exists and already contains the Phase 1-style foundation: `requirements.txt`, `.env.example`, SQLAlchemy models, Alembic wiring, an initial migration, shared DB/config helpers, and baseline ticket helper tests
- the remaining web, auth, upload, permission, worker, script, template, and static surfaces are still absent or placeholders, so the repository is in a partial-build state rather than a blank slate
- the root environment still does not have Stage 1 dependencies installed, and `pytest -q triage-stage1/tests` currently fails at import time because `sqlalchemy` is unavailable outside the isolated Stage 1 dependency set

Planning consequence:
- keep Stage 1 isolated in `triage-stage1/` and treat the existing foundation there as the implementation baseline
- avoid coupling Stage 1 runtime dependencies into the existing root `docloop-tools` package unless a later explicit decision is made
- treat the existing repository as hosting the implementation, not as providing reusable ticketing, auth, or worker infrastructure
- require implement/test work to use `triage-stage1/requirements.txt` or an equivalent isolated environment before claiming validation on Stage 1 code paths

## Current baseline snapshot

Observed implemented foundation in `triage-stage1/`:
- `shared/config.py`, `shared/db.py`, `shared/models.py`, and `shared/tickets.py` exist and cover the core schema/config baseline
- `shared/migrations/` contains Alembic scaffolding plus `20260319_0001_initial.py`
- `.env.example`, `README.md`, `requirements.txt`, and baseline tests exist
- the one-active-run partial unique index, ticket view primary key, and several shared helper invariants are already represented in code/tests

Observed gaps still blocking Stage 1 completion:
- `app/main.py`, `app/auth.py`, `app/routes_auth.py`, `app/routes_requester.py`, `app/routes_ops.py`, `app/render.py`, and `app/uploads.py` are placeholders
- `shared/security.py` and `shared/permissions.py` are placeholders
- `worker/main.py`, `worker/queue.py`, `worker/triage.py`, `worker/codex_runner.py`, and `worker/ticket_loader.py` are placeholders
- required `scripts/`, `app/templates/`, and `app/static/` surfaces have not been created yet

Planning consequence:
- preserve the existing phase ids, but treat Phase 1 as a landed baseline that Phase 2 now builds on
- focus the active implementation slice on Phase 2 while keeping later phases explicit for Dev/TI UI, worker behavior, bootstrap, and hardening

## Delivery strategy

Use six explicit phases. The boundaries are chosen to keep each slice coherent, independently reviewable, and low-risk:

1. Shared foundation and persistence
2. Authentication, authorization, requester intake, and attachment pipeline
3. Dev/TI UI workflows, human message actions, and draft handling
4. AI worker queue, Codex orchestration, fingerprints, and publication rules
5. Bootstrap, workspace provisioning, operability, and management commands
6. Acceptance hardening, regression tests, and documentation pass

This is intentionally not a one-shot build. The worker rules, stale-run protection, and server-side session model are the highest-risk areas and need explicit sequencing.

Current planning stance for this run:
- Phase ids remain `phase-1` through `phase-6` so the existing Superloop task state remains coherent
- the repository already contains the Phase 1 foundation baseline
- `phase-2` is the active implementation focus selected in the current run metadata and should absorb only the requester/auth/upload slice, not later-phase worker or Dev/TI scope

## Repository shape to complete

Primary target layout:

```text
triage-stage1/
  README.md
  .env.example
  requirements.txt
  app/
    main.py
    auth.py
    routes_auth.py
    routes_requester.py
    routes_ops.py
    render.py
    uploads.py
    templates/
    static/
  worker/
    main.py
    queue.py
    triage.py
    codex_runner.py
    ticket_loader.py
  shared/
    config.py
    db.py
    models.py
    permissions.py
    security.py
    migrations/
  scripts/
    bootstrap_workspace.py
    create_admin.py
    create_user.py
    set_password.py
    deactivate_user.py
    run_web.py
    run_worker.py
```

Minor filename variation is acceptable only if the same separation of concerns is preserved.

Integration boundary with the existing repository:
- the Stage 1 subproject may reuse repository conventions for documentation and tests, but it should not rely on current `docloop.py` or `superloop.py` runtime code
- root-level packaging for `docloop-tools` remains out of scope unless Stage 1 later needs an explicit top-level launcher
- Stage 1 dependency installation should come from `triage-stage1/requirements.txt`, not from expanding the current root package metadata

## Architectural decisions

### Application structure

- Keep one FastAPI app process and one worker process.
- Use server-rendered Jinja2 templates plus HTMX partials; do not introduce a SPA or websocket layer.
- Keep domain rules in `shared/` so both web and worker paths use identical persistence helpers and invariants.
- Treat `ai_runs` as both the queue and execution log; do not add a second queueing system.
- Keep Stage 1 code inside `triage-stage1/` so current `docloop` and `superloop` tooling remains operational and regression scope stays local to the new subproject.

### Persistence model

- Implement the PRD tables directly with SQLAlchemy 2.x declarative models and Alembic migrations.
- Enforce the one-active-run invariant with both application logic and the required partial unique index on `ai_runs(ticket_id)` for `pending` and `running`.
- Centralize status mutation in one helper that:
  - writes `tickets.status`
  - maintains `resolved_at`
  - bumps `updated_at`
  - inserts `ticket_status_history`
- Centralize `ticket_views` upsert logic in one helper used by both requester and Dev/TI flows.

### Authentication and security

- Use local accounts with Argon2id password hashes.
- Use a custom PostgreSQL-backed session store; the browser cookie contains only the opaque raw session token.
- Store only `sha256(raw_token)` in `sessions.token_hash`.
- Bind CSRF validation to the server-side session record and require it on every POST form.
- Do not use Starlette `SessionMiddleware` for primary auth state.

### Rendering and sanitization

- Store `body_markdown` and normalized `body_text` on every message.
- Render markdown to HTML with `markdown-it-py`, then sanitize with `bleach`.
- Never render raw HTML from users or from AI output.

### Attachments

- Support only PNG and JPEG uploads.
- Parse multipart forms with explicit product limits:
  - `max_files = MAX_IMAGES_PER_MESSAGE`
  - `max_part_size >= MAX_IMAGE_BYTES`
- Validate MIME type, Pillow openability, size, SHA-256, and dimensions before persistence.
- Store files under `UPLOADS_DIR` outside static assets and serve only through authenticated routes.

### AI execution

- The worker is the only Codex caller.
- Build prompt, schema, and run artifacts under `TRIAGE_WORKSPACE_DIR/runs/{ticket_id}/{run_id}/`.
- Use the exact PRD prompt skeleton and JSON schema as checked-in template artifacts or embedded constants written per run.
- The canonical AI result is the `--output-last-message` JSON file; JSONL output is diagnostics only.
- Disable web search explicitly on every run.

## Interfaces and contracts

### HTTP routes

Auth:
- `GET /login`
- `POST /login`
- `POST /logout`

Requester:
- `GET /app`
- `GET /app/tickets`
- `GET /app/tickets/new`
- `POST /app/tickets`
- `GET /app/tickets/{reference}`
- `POST /app/tickets/{reference}/reply`
- `POST /app/tickets/{reference}/resolve`
- `GET /attachments/{attachment_id}`

Dev/TI:
- `GET /ops`
- `GET /ops/board`
- `GET /ops/tickets/{reference}`
- `POST /ops/tickets/{reference}/assign`
- `POST /ops/tickets/{reference}/set-status`
- `POST /ops/tickets/{reference}/reply-public`
- `POST /ops/tickets/{reference}/note-internal`
- `POST /ops/tickets/{reference}/rerun-ai`
- `POST /ops/drafts/{draft_id}/approve-publish`
- `POST /ops/drafts/{draft_id}/reject`

Health:
- `GET /healthz`
- `GET /readyz`

### Web-layer service boundaries

`shared/config.py`
- typed settings loader from environment
- default values for non-secret product constants

`shared/db.py`
- engine and session factory
- transaction helper for web requests and worker loops

`shared/models.py`
- SQLAlchemy models for all PRD tables
- DB-level indexes and constraints

`shared/security.py`
- Argon2id password hashing
- random token generation
- SHA-256 token hashing
- CSRF token generation and comparison

`shared/permissions.py`
- role checks
- requester ownership checks
- attachment visibility checks

`app/auth.py`
- current-user resolution from opaque session cookie
- login/logout helpers
- CSRF helpers for templates and POST validation

`app/uploads.py`
- multipart parsing with limits
- image validation and storage
- attachment metadata persistence

`app/render.py`
- markdown-to-safe-HTML conversion
- body text normalization helpers

`worker/ticket_loader.py`
- load public messages, internal messages, attachments, drafts, and relevant ticket metadata

`worker/triage.py`
- automatic-trigger fingerprint calculation
- publication fingerprint calculation
- stale-run suppression check
- action application helpers for the five allowed action paths

`worker/codex_runner.py`
- run directory creation
- `AGENTS.md`, `SKILL.md`, schema, and prompt file writes
- Codex command assembly and subprocess execution
- final JSON load and validation

`worker/queue.py`
- `FOR UPDATE SKIP LOCKED` run acquisition
- heartbeat writes
- deferred requeue processing

`shared/tickets.py` or equivalent shared service module
- create-ticket transaction
- requester-reply transaction
- public-reply transaction
- internal-note transaction
- resolve/reopen transaction
- assignment and status transition helpers

### UI contract

Requester views:
- thread-first pages only
- only public messages and public attachments
- requester-visible status mapping:
  - `new`, `ai_triage` -> `Reviewing`
  - `waiting_on_user` -> `Waiting for your reply`
  - `waiting_on_dev_ti` -> `Waiting on team`
  - `resolved` -> `Resolved`

Dev/TI views:
- grouped board by internal status
- filters for status, class, assigned user, urgent, unassigned, created-by-me, needs-approval, and updated-since-last-view
- ticket detail page with public thread, internal thread, AI analysis, relevant paths, draft controls, assignment, status controls, and rerun action

HTMX use:
- board filter refreshes
- thread composer submissions
- assignment/status controls
- draft approval/rejection fragments

No drag-and-drop board is required in Stage 1.

### Worker output contract

The worker must validate the exact Stage 1 JSON schema and then apply these application-level rules:
- `ask_clarification` requires `needs_clarification = true` and non-empty `public_reply_markdown`
- `auto_public_reply` requires `auto_public_reply_allowed = true`, `evidence_found = true`, and non-empty `public_reply_markdown`
- `auto_confirm_and_route` requires `auto_public_reply_allowed = true` and non-empty `public_reply_markdown`
- `draft_public_reply` requires `auto_public_reply_allowed = false` and non-empty `public_reply_markdown`
- `route_dev_ti` may leave `public_reply_markdown` empty
- `ticket_class = unknown` cannot auto-public-reply

## Ordered implementation milestones

### Phase 1: Shared foundation and persistence

Goals:
- preserve the existing `triage-stage1/` foundation as the dependency base for every later slice
- keep the already-landed schema/config/migration baseline aligned with the frozen PRD
- avoid reopening root-package dependency scope while later phases build on the isolated subproject

Implemented baseline observed in repo:
- `requirements.txt`, `.env.example`, and package structure exist under `triage-stage1/`
- settings loading for PRD section 26 exists in `shared/config.py`
- Stage 1 dependency definitions remain local to `triage-stage1/`
- SQLAlchemy models for `users`, `sessions`, `tickets`, `ticket_messages`, `ticket_attachments`, `ticket_status_history`, `ticket_views`, `ai_runs`, `ai_drafts`, and `system_state` exist
- an Alembic migration for the full schema exists, including the partial unique index on active `ai_runs`
- shared helpers already exist for:
  - ticket reference generation and formatting
  - `updated_at` bumping
  - status history insertion
  - draft supersede behavior for newer pending drafts

Remaining Phase 1 validation to preserve while later work proceeds:
- do not regress the baseline migration or helper invariants while adding web and worker code
- keep new business logic layered on top of existing shared helpers rather than duplicating mutation logic

Acceptance target:
- schema can be applied cleanly to PostgreSQL 16
- one-active-run invariant exists in both code path design and DB index
- core helpers are reusable by both web and worker code

Phase boundary:
- no FastAPI route behavior yet
- no worker execution yet

### Phase 2: Authentication, requester flow, and attachments

Goals:
- deliver secure login/logout, remember-me sessions, requester-only routing, ticket creation, reply, resolve, unread tracking, and authenticated attachment access

Implementation details:
- implement `shared/security.py` and `shared/permissions.py` instead of leaving them as placeholders
- implement local auth and server-side session persistence in `app/auth.py` and `app/routes_auth.py`
- add CSRF protection to all POST forms
- build `app/main.py`, requester templates, and requester route handlers
- implement `app/render.py` and `app/uploads.py`
- implement title fallback from description first sentence
- implement ticket creation transaction that writes:
  - `tickets`
  - initial public `ticket_messages`
  - up to three public attachments
  - pending `ai_runs`
  - initial `ticket_status_history`
  - creator `ticket_views`
- implement requester reply and reopen semantics, including requeue behavior when an active run already exists
- implement requester attachment download authorization

Acceptance target:
- AC1, AC2, AC3, AC4, AC14, AC17, and requester half of AC18 are satisfiable from working code

Phase boundary:
- no Dev/TI board yet
- no worker processing beyond queued rows

### Phase 3: Dev/TI workflow and human-controlled actions

Goals:
- deliver operator-facing board/list/detail views and all human ticket actions outside AI execution

Implementation details:
- implement `/ops`, `/ops/board`, and `/ops/tickets/{reference}`
- implement grouped status board and required filters
- implement internal note creation, public reply creation, assignment/unassignment, manual status change, draft approve/publish, draft rejection, and manual rerun request
- implement ticket detail rendering with public thread, internal thread, AI analysis placeholders, draft panel, and relevant path display
- wire `ticket_views.last_viewed_at` updates only on allowed detail GET/POST paths
- ensure requesters never see internal notes, drafts, or internal AI analysis

Acceptance target:
- AC8, AC9, AC10, and Dev/TI half of AC18 become reachable once worker outputs exist

Phase boundary:
- worker may still be mocked or inactive
- no Codex subprocess integration yet

### Phase 4: Worker queue, Codex integration, and AI publication rules

Goals:
- make queued runs executable with repo-aware, read-only Codex triage and strict stale-run suppression

Implementation details:
- implement polling worker with `WORKER_POLL_SECONDS` cadence
- acquire oldest pending run using row-level locking and `FOR UPDATE SKIP LOCKED`
- compute and persist automatic-trigger fingerprint before run start
- implement skip path when non-manual input hash equals `tickets.last_processed_hash`
- write run artifacts under workspace `runs/`
- generate exact `AGENTS.md`, exact repo skill `SKILL.md`, exact schema, and exact prompt skeleton
- invoke Codex in read-only, approval-never, web-search-disabled mode with optional `--model`
- validate final JSON output and enforce application-level action rules
- reload ticket state before publication and apply stale-run suppression using publication fingerprint and `requeue_requested`
- publish exactly one internal AI note for every successful non-superseded run
- implement the five allowed action paths and deferred requeue processing
- implement failure path with one internal failure note, `waiting_on_dev_ti`, and deferred requeue handling

Acceptance target:
- AC5 through AC16 are fully implementable

Phase boundary:
- bootstrap and CLI polish may still be incomplete

### Phase 5: Bootstrap, workspace provisioning, and operability

Goals:
- make the system deployable and operable inside WSL using the mandated workspace layout and management commands

Implementation details:
- implement bootstrap script to:
  - ensure schema exists
  - ensure upload/workspace directories exist
  - initialize workspace git repo if missing
  - create empty initial commit if needed
  - verify repo and manuals mounts
  - write exact `AGENTS.md`
  - write exact `.agents/skills/stage1-triage/SKILL.md`
- implement CLI commands:
  - `create-admin`
  - `create-user`
  - `set-password`
  - `deactivate-user`
- implement `run_web.py` and `run_worker.py`
- add structured JSON logging, `/healthz`, `/readyz`, and worker heartbeat

Acceptance target:
- AC12, AC13, and AC19 are operationally enforced, not just code-commented

Phase boundary:
- no new product features beyond deployment completeness

### Phase 6: Acceptance hardening and regression coverage

Goals:
- close gaps between implemented behavior and the PRD acceptance criteria, especially around edge cases and non-leak invariants

Implementation details:
- add automated tests for:
  - auth/session lifecycle and remember-me expiry handling
  - requester isolation and attachment authorization
  - unread marker semantics
  - multipart upload limits and MIME validation
  - one-active-run DB constraint behavior
  - requeue-on-change and stale-run suppression
  - draft superseding and publish/reject flows
  - internal-note non-leak rules
  - worker failure, skip, superseded, and deferred requeue paths
- complete README setup and operator instructions
- run an acceptance checklist sweep against AC1-AC19

Acceptance target:
- all PRD acceptance criteria are mapped to code or tests

## Data and state transition rules to preserve

### Ticket mutation invariants

- Any mutation that materially affects UI or worker logic must bump `tickets.updated_at`.
- Every status change must insert `ticket_status_history`.
- Requester replies on resolved tickets clear `resolved_at` and use `reopen` semantics for enqueue/requeue trigger selection.
- Internal notes do not automatically supersede active runs; manual rerun is required for new internal-only context.

### AI run invariants

- At most one active `ai_runs` row per ticket may exist in `pending` or `running`.
- New requester-visible input during an active run must set `requeue_requested = true` and update `requeue_trigger`.
- Before publishing output, the worker must recompute the publication fingerprint and suppress stale runs when the fingerprint changed or `requeue_requested = true`.
- Exactly one internal AI note must be published for every successful non-skipped, non-superseded run.
- Action-specific logic must not emit a second internal AI note.

### Visibility invariants

- Public replies may use only public ticket content, public attachments, manuals, app code, and general reasoning.
- Internal messages may inform internal summaries and routing only.
- Automatic public replies must never reveal information present only in internal notes.

## Cross-phase dependency map

- Phase 2 depends on the existing Phase 1 baseline in `triage-stage1/`, plus isolated installation of Stage 1 dependencies from `triage-stage1/requirements.txt`.
- Phase 3 depends on Phase 1 models plus Phase 2 auth/session/permission plumbing.
- Phase 4 depends on Phases 1 through 3 because it publishes messages, drafts, and state transitions used by both UIs.
- Phase 5 depends on Phase 4 for final workspace artifact contract and on Phases 1-2 for shared models and password/session-related helpers used by CLI/admin flows.
- Phase 6 depends on all earlier phases.
- All phases assume Stage 1 stays isolated inside `triage-stage1/` so the existing repository root package and tests remain unaffected except where new documentation or top-level references are intentionally added.

Explicit deferment ownership:
- Work excluded from Phase 1 is intentionally picked up by later phases as follows:
  - FastAPI route handling, auth pages, and session login/logout flows -> Phase 2
  - Dev/TI board/detail UI -> Phase 3
  - worker polling and Codex execution -> Phase 4
- Work excluded from Phase 2 is intentionally picked up by later phases as follows:
  - Dev/TI board and operator actions -> Phase 3
  - actual execution of queued AI runs -> Phase 4
- Work excluded from Phase 3 is intentionally picked up by later phases as follows:
  - Codex execution and automatic publication logic -> Phase 4
  - bootstrap scripts and workspace provisioning -> Phase 5
- Work excluded from Phase 4 is intentionally picked up by later phases as follows:
  - bootstrap, operability, and admin CLI polish -> Phase 5
- Work excluded from Phase 5 is intentionally not deferred within Stage 1:
  - external notifications, SSO, and web admin remain out of scope for the product
- Work excluded from Phase 6 is intentionally not deferred within Stage 1:
  - roadmap items beyond the frozen PRD and non-essential performance tuning remain out of scope

External dependencies to validate early:
- PostgreSQL 16 reachable from WSL
- Codex binary path and API key available
- read-only mounts for `app/` and `manuals/` available at configured paths

## Testing strategy

Primary automated coverage:
- model and helper unit tests for status history, reference formatting, and fingerprint calculation
- route/integration tests for auth, requester flow, Dev/TI actions, and attachment authorization
- worker tests for queue acquisition, skip path, stale suppression, action application, and deferred requeue behavior
- bootstrap/CLI smoke tests
- one repo-level smoke check that the existing `docloop-tools` packaging and import paths are not implicitly broken by introducing the new subproject
- environment setup step before Stage 1 validation: install `triage-stage1/requirements.txt` or equivalent isolated dependencies, because the root repository environment does not include SQLAlchemy/FastAPI by default

Minimum manual validation before freezing implementation:
- create ticket with and without title
- reply with 0 to 3 images near size limits
- verify requester cannot see internal content
- verify Dev/TI board filters and draft controls
- verify manual rerun behavior during active run
- simulate stale run and confirm no publication occurs
- verify workspace bootstrap writes exact `AGENTS.md` and `SKILL.md`

## Risk register

### R1: Session implementation drifts back to signed-cookie middleware

Impact:
- violates AC2 and server-side session requirement

Controls:
- implement dedicated `sessions` table and auth helper before any route work
- add explicit tests that cookie contains opaque token only and logout deletes DB row

### R2: Multipart defaults silently exceed or undercut product limits

Impact:
- upload behavior diverges from AC17 and may allow oversized files or unexpected failures

Controls:
- always call `request.form()` with explicit limits
- add tests for file count and size rejection paths

### R3: Stale-run suppression publishes obsolete AI output

Impact:
- incorrect public or internal messages, broken audit trail, and user confusion

Controls:
- keep fingerprint helpers centralized
- enforce publication-time reload and comparison
- test requester-reply-during-run and manual-rerun-during-run scenarios

### R4: Internal/public separation leaks internal-only information

Impact:
- privacy and trust failure

Controls:
- keep internal messages out of publication fingerprints
- use separate prompt sections for public and internal messages
- add tests asserting public output generation never uses internal-only text unless already public

### R5: Cross-cutting `updated_at` or status history omissions

Impact:
- unread markers and audit history become unreliable

Controls:
- centralize ticket mutation helpers
- add integration tests for each mutation class listed in PRD section 11.5

### R6: Worker queue concurrency allows duplicate active runs

Impact:
- broken AC15 and duplicate publications

Controls:
- enforce partial unique index
- use row locking on pending acquisition
- handle integrity errors by reloading ticket and processing deferred requeue rules

### R7: Exact workspace artifacts drift from PRD text

Impact:
- Codex prompt behavior and safety instructions diverge from the approved product contract

Controls:
- keep exact `AGENTS.md`, exact `SKILL.md`, exact schema, and prompt skeleton as literal checked-in templates or constants
- test bootstrap output byte-for-byte where practical

### R8: New Stage 1 dependencies bleed into the existing repository runtime

Impact:
- unrelated regressions in current `docloop` and `superloop` tooling or confusing install paths for implement/test phases

Controls:
- keep Stage 1 in `triage-stage1/` with its own dependency manifest
- avoid changing the root `pyproject.toml` unless a later explicit integration decision requires it
- add one smoke check that existing repository entrypoints still import cleanly after the new subproject lands

### R9: Validation is claimed from the wrong Python environment

Impact:
- implement/test passes may be reported inaccurately because the root repo environment lacks Stage 1 dependencies and currently cannot even import `sqlalchemy`

Controls:
- treat `triage-stage1/requirements.txt` as mandatory test setup for Stage 1 code paths
- record clearly whether checks ran in the isolated Stage 1 environment or failed before execution due to missing dependencies
- do not treat root-environment import failures as Stage 1 behavioral failures without first installing the declared subproject dependencies

## Deferments and explicit non-goals

Remain out of scope for Stage 1 and must not be added opportunistically:
- Kanboard, Slack, SMTP, or any external notification path
- OAuth, LDAP, SSO, or email password reset
- OCR or non-image attachments
- DDL/schema-dump inspection, SQL Server access, or Delphi MCP
- repository modification, patch generation, branch creation, or Codex write mode
- websocket infrastructure or SPA frontend

## Definition of done

The implementation is ready to hand to the implement/test phases when:
- `phase_plan.yaml` matches the runtime schema and encodes this ordered decomposition
- the plan gives concrete module boundaries and route/service responsibilities
- all AC1-AC19 are traceable to one or more planned phases
- the highest-risk invariants have explicit controls and tests
