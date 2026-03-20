# Hardened Dependency / Worker Plan

## Objective

Execute the hardened Stage 1 follow-up against the existing `triage-stage1/` subproject. The work is not a greenfield build: auth/session flows, requester and ops UIs, queue helpers, worker loop, scripts, and tests already exist. The remaining scope is to make the current implementation production-safe by:

1. Pinning Stage 1 dependencies reproducibly.
2. Fixing browser login CSRF robustness.
3. Making deferred AI-run requeue handling race-safe.
4. Adding automatic stuck-run reaping and the required operator entrypoint.

## Verified current state

- The implementation surface named in the request lives under `triage-stage1/`, not the repository root. Relevant files already exist at `triage-stage1/app/routes_auth.py`, `triage-stage1/worker/queue.py`, `triage-stage1/worker/main.py`, `triage-stage1/worker/triage.py`, `triage-stage1/scripts/`, and `triage-stage1/tests/`.
- `triage-stage1/app/routes_auth.py` currently creates the login `TemplateResponse` first and only then mutates `response.context["csrf_token"]` after calling `issue_login_csrf(...)`. That matches the reported symptom that browser-rendered hidden input can be empty even when the cookie is issued.
- `triage-stage1/tests/test_requester_app.py` and `triage-stage1/tests/test_ops_app.py` currently log in by copying the CSRF cookie directly, so existing coverage does not exercise the browser form path that reads the hidden input from HTML.
- `triage-stage1/worker/queue.py` currently performs a check-then-insert sequence in `enqueue_deferred_requeue(...)`: flush, read active run, create pending run, then clear `ticket.requeue_requested`. Under concurrent finalization this can still hit the partial unique index `uq_ai_runs_ticket_active`.
- `triage-stage1/shared/tickets.py::create_pending_ai_run(...)` also performs its own read-before-insert guard and raises `ActiveAIRunExistsError` when an active run is already visible, so race hardening must account for both helper-level duplicate detection and database-level uniqueness failure.
- `triage-stage1/worker/triage.py` finalizers immediately publish notes/status changes and call `enqueue_deferred_requeue(...)`; they are not currently guarded against crossed completion events such as reaper-finalize versus worker-finalize on the same `running` row.
- `triage-stage1/worker/main.py` updates heartbeat and then directly calls `process_next_run(...)`; there is no recovery path for `running` rows left behind after worker death.
- `triage-stage1/requirements.txt` is only partially constrained and omits `markupsafe`, while `triage-stage1/app/render.py` imports `Markup` from `markupsafe`.
- `triage-stage1/scripts/_common.py` already provides the expected `resolve_runtime(...)` and `print_json(...)` helpers, and existing scripts follow the `main(argv=None, *, settings=None, session_factory=None) -> int` pattern.

## Planning decisions

- All request-relative Stage 1 file references resolve under `triage-stage1/`. Concretely:
  - `requirements.txt` means `triage-stage1/requirements.txt`
  - `requirements.lock` means `triage-stage1/requirements.lock`
  - `README.md` means `triage-stage1/README.md`
  - `app/...`, `worker/...`, `scripts/...`, and `tests/...` mean the corresponding `triage-stage1/...` paths
- Validation must run from the Stage 1 subproject environment, not the repo-root environment. The full-suite command therefore becomes `cd /workspace/docloop/triage-stage1 && python -m pytest tests/ -v`.
- The snapshot’s final file list is incomplete for the full stated scope. The CSRF and requeue-race defects necessarily require changes in `triage-stage1/app/routes_auth.py` and `triage-stage1/worker/queue.py`, plus new focused regression test file(s), because existing tests must not be modified.
- No schema migration or new configuration is needed. The stuck-run threshold must derive from existing `Settings.codex_timeout_seconds`, exactly as requested.

## Request-to-repository reconciliation

- The immutable request is written as if the Stage 1 application is the repository root, but the live codebase keeps that implementation isolated under `triage-stage1/`.
- The only repository location that matches the requested auth, worker, script, and test surfaces is `triage-stage1/`; planning and later implementation must stay inside that subtree.
- The request’s final file list cannot be satisfied literally because it omits files that must change to deliver the confirmed defects without modifying existing tests:
  - `triage-stage1/app/routes_auth.py` for the login-page CSRF render-order fix
  - `triage-stage1/worker/queue.py` for deferred requeue race hardening
  - at least one new focused auth/race regression module under `triage-stage1/tests/`
- This is treated as a path-resolution and completeness correction, not a scope expansion, because those files implement the exact defects named in the request.

## Scope

### In scope

- Creating `triage-stage1/requirements.lock` from a clean Python 3.12 environment.
- Rewriting direct dependencies in `triage-stage1/requirements.txt` to bounded ranges derived from the resolved install and adding explicit `markupsafe`.
- Updating `triage-stage1/README.md` for reproducible install guidance and manual reaper usage.
- Fixing login-page CSRF token rendering so the HTML hidden input and issued cookie are aligned in the same response cycle.
- Adding browser-submit login regression coverage that uses the hidden token from rendered HTML and preserves 403 behavior on CSRF mismatch.
- Hardening deferred requeue creation so active-run uniqueness races do not crash the worker or lose requeue intent.
- Keeping run finalization idempotent enough to tolerate crossed completion paths introduced by stuck-run reaping.
- Adding `reap_stuck_runs(...)`, integrating it into the worker loop, adding `scripts/reap_stuck_runs.py`, and adding the six requested reaper tests.
- Running the full Stage 1 test suite after dependency pinning, after the worker/auth hardening slice, and once more at the end.

### Out of scope

- Any repo-root dependency or README changes outside `triage-stage1/`.
- New configuration knobs, schema changes, or worker architecture refactors.
- Changes to existing tests. New regression coverage must be added in new test file(s) only.
- Unrelated dirty files elsewhere in the repository.

## Code areas expected to change

- `triage-stage1/requirements.txt`
- `triage-stage1/requirements.lock`
- `triage-stage1/README.md`
- `triage-stage1/app/routes_auth.py`
- `triage-stage1/worker/queue.py`
- `triage-stage1/worker/main.py`
- `triage-stage1/scripts/reap_stuck_runs.py`
- New Stage 1 regression test file(s):
  - one focused auth/race-hardening test file for the two confirmed defects
  - `triage-stage1/tests/test_stuck_run_reaper.py`

## Stable interfaces and behaviors to preserve

### Auth surface

- Route signatures remain unchanged:

```python
@router.get("/login")
def login_page(request: Request, auth: AuthContext | None = Depends(...))

@router.post("/login")
async def login_submit(
    request: Request,
    db: Session = Depends(...),
    auth: AuthContext | None = Depends(...),
)
```

- Successful login redirects remain role-based:
  - requester -> `/app`
  - dev_ti/admin -> `/ops`
- Invalid/tampered login CSRF remains a `403` with a fresh login form.
- Session-cookie behavior, remember-me semantics, and logout semantics stay unchanged.

### Queue / finalization surface

- Existing public helper signatures stay unchanged:

```python
def enqueue_deferred_requeue(
    session: Session,
    *,
    ticket: Ticket,
    created_at: datetime,
    requested_by_user_id: uuid.UUID | None = None,
) -> AiRun | None
```

```python
def finalize_success(...)
def finalize_failure(...)
def finalize_superseded(...)
def finalize_skipped(...)
```

- The partial unique index `uq_ai_runs_ticket_active` remains the only active-run uniqueness enforcement mechanism; the fix must work with it instead of weakening it.
- A terminalized run must not later publish duplicate notes, duplicate public actions, or clear requeue flags incorrectly if another completion path already resolved the row.
- Any idempotence guard may only short-circuit already-terminal runs or already-resolved requeue state; it must not change the first-completion behavior, helper signatures, or `PublicationResult` shape.

### New reaper interface

This new function is required exactly as requested:

```python
def reap_stuck_runs(
    session_factory: sessionmaker[Session],
    *,
    settings: Settings,
    max_age_seconds: int | None = None,
    reaped_at: datetime | None = None,
) -> int:
```

Required behavior to preserve/enforce:

- Default threshold is `settings.codex_timeout_seconds * 2`.
- Default `reaped_at` is `now_utc()`.
- Only `running` rows with non-null `started_at` older than the threshold are eligible.
- `finalize_failure(...)` in `worker/triage.py` is reused; no duplicated failure-routing logic.
- `run_worker_loop(...)` keeps its current signature and polling semantics, with reaping inserted after heartbeat and before `process_next_run(...)`.
- The manual script follows the existing script contract and prints JSON via `print_json(...)`.

## Milestones

### Milestone 1: Reproducible dependency baseline

Goal: make Stage 1 installs deterministic enough that the remaining hardening work is validated against a known environment.

Deliverables:

- `triage-stage1/requirements.lock` created from a clean Python 3.12 environment with exact `==` pins for the full resolved install.
- `triage-stage1/requirements.txt` rewritten so every direct dependency is bounded relative to the resolved version:
  - `>=installed,<next_major` for packages at `>=1.0`
  - `>=installed,<0.next_minor` for `0.x` packages
- `markupsafe` added as an explicit direct dependency.
- `triage-stage1/README.md` updated so Local Setup mentions `pip install -r requirements.lock` for reproducible installs.

Implementation notes:

- Work only inside `triage-stage1/`; do not introduce a repo-root lockfile.
- Treat the current direct dependency set as:
  - `fastapi`
  - `uvicorn`
  - `jinja2`
  - `sqlalchemy`
  - `alembic`
  - `psycopg[binary]`
  - `pydantic`
  - `pillow`
  - `markdown-it-py`
  - `bleach`
  - `argon2-cffi`
  - `httpx`
  - `python-multipart`
  - `pytest`
  - `markupsafe`
- The resolved install must be new enough to keep `request.form(max_files=..., max_part_size=...)` working, since the requester routes already depend on that support.

Acceptance criteria:

- A fresh Python 3.12 environment can install from `triage-stage1/requirements.lock` and run `cd /workspace/docloop/triage-stage1 && python -m pytest tests/ -v` successfully.
- A fresh Python 3.12 environment can install from the bounded `triage-stage1/requirements.txt` and run the same suite successfully.
- No Stage 1 application code changes are made in this milestone.

### Milestone 2: Browser login CSRF robustness

Goal: make the login page render a concrete hidden CSRF value that matches the issued cookie in the same request cycle.

Deliverables:

- `triage-stage1/app/routes_auth.py` updated so `login_page(...)` constructs the template context before `TemplateResponse(...)` creation and passes a concrete `csrf_token` into that initial context.
- The existing `issue_login_csrf(...)` helper remains the cookie issuer; the fix is to align context creation order, not to redesign the auth helpers.
- A new auth regression test file verifies:
  - `GET /login` renders a non-empty hidden `csrf_token`
  - `POST /login` succeeds when the token is taken from the HTML form, not from the cookie jar directly
  - tampered form token still returns `403`
  - requester and Dev/TI login redirects remain correct

Acceptance criteria:

- Browser-style login works with only the rendered hidden token.
- CSRF mismatch still fails with `403`.
- Existing login/session semantics and redirects remain unchanged.

### Milestone 3: Active-run requeue race safety

Goal: ensure deferred requeue handling tolerates concurrent finalization and requester activity without unhandled uniqueness failures or dropped requeue intent.

Deliverables:

- `triage-stage1/worker/queue.py` changed so `enqueue_deferred_requeue(...)` no longer relies on an unsafe check-then-insert outcome.
- Preferred minimal strategy:
  - attempt queue creation
  - treat `ActiveAIRunExistsError` or the specific active-run unique `IntegrityError` as a benign already-queued/already-running case
  - re-read active state before deciding whether requeue intent can be cleared
- `ticket.requeue_requested` and `ticket.requeue_trigger` are cleared only when queue resolution is known to be safe:
  - a new pending run was created, or
  - another active run already exists and therefore satisfies the requeue intent
- Crossed-completion idempotence is added before publish/finalize side effects so a run already finalized by another path is treated as resolved rather than republished.
- A new race-focused regression test file covers:
  - concurrent finalization crossover with requester reply / deferred requeue
  - benign handling of the one-active-run uniqueness race
  - preservation of at-most-one active run and eventual clearing of requeue flags when state is resolved

Acceptance criteria:

- No unhandled `IntegrityError` escapes the worker on the deferred requeue path.
- At most one `pending|running` run exists per ticket after the race.
- Requeue intent is not lost because flags were cleared before queue state was actually resolved.
- Duplicate/crossed finalization does not publish duplicate ticket mutations.

### Milestone 4: Stuck-run reaper and operator entrypoint

Goal: recover tickets whose worker died after moving a run to `running`.

Deliverables:

- `triage-stage1/worker/main.py` gains `reap_stuck_runs(...)` with the requested signature and threshold behavior.
- `run_worker_loop(...)` calls the reaper every polling cycle immediately after heartbeat update and before `process_next_run(...)`.
- `triage-stage1/scripts/reap_stuck_runs.py` follows the existing management-script pattern, accepts `--max-age-seconds`, and prints JSON via `print_json(...)`.
- `triage-stage1/tests/test_stuck_run_reaper.py` contains the six requested tests.
- `triage-stage1/README.md` documents automatic and manual reaping under Management commands.

Implementation notes:

- The reaper must query ordered oldest-first stuck runs and reuse `finalize_failure(...)` so failure notes, status routing, and deferred requeue behavior stay centralized.
- The reaper still runs every poll cycle even when heartbeat writes are skipped by the 60-second throttle already present in `run_worker_loop(...)`.
- The reaper must tolerate ticket disappearance by skipping orphaned runs without crashing.
- Because the reaper creates a new crossed-completion path, Milestone 3’s idempotence guard is a prerequisite for this milestone.

Acceptance criteria:

- Stuck `running` rows are reaped to `failed` and routed through the existing failure path.
- Tickets with deferred requeue intent still receive a new pending run after reaping when appropriate.
- The script returns `0` and prints `{"status": "ok", "reaped_count": <n>}`.
- The full Stage 1 test suite passes after this milestone.

## Test strategy

Required validation sequence:

1. After Milestone 1:
   - create clean Python 3.12 environment
   - install from `triage-stage1/requirements.lock`
   - run `cd /workspace/docloop/triage-stage1 && python -m pytest tests/ -v`
   - create or refresh clean environment from bounded `triage-stage1/requirements.txt`
   - rerun the same suite
2. After Milestones 2 through 4 are implemented together in the pinned environment:
   - run `cd /workspace/docloop/triage-stage1 && python -m pytest tests/ -v`
3. Final gate:
   - rerun `cd /workspace/docloop/triage-stage1 && python -m pytest tests/ -v`

New regression coverage must be added without editing existing tests:

- One new auth/race-hardening test module for:
  - hidden-token login submit path
  - tampered login CSRF failure
  - role redirect preservation
  - requeue race handling / finalization idempotence coverage, including deterministic simulation of helper-level or DB-level duplicate-active-run resolution
- One new `triage-stage1/tests/test_stuck_run_reaper.py` file with the six requested cases.

Test authoring constraints:

- Reuse the existing Stage 1 fixture style instead of inventing new harnesses:
  - auth/requester flows should follow `triage-stage1/tests/test_requester_app.py` and `triage-stage1/tests/test_ops_app.py`
  - worker/reaper flows should reuse helper patterns from `triage-stage1/tests/test_worker_phase4.py`
  - script entrypoint coverage should mirror `triage-stage1/tests/test_phase5_operability.py`
- Do not rely on true database-level concurrency in SQLite alone to prove the requeue race fix. The implementation phase should combine persisted-state assertions with targeted `IntegrityError` simulation or equivalent deterministic crossover coverage because the production-sensitive uniqueness behavior is defined by the partial active-run index and PostgreSQL semantics.

## Implementation order

1. Pin Stage 1 dependencies and document reproducible installation in `triage-stage1/README.md`.
2. Revalidate the full Stage 1 suite from the pinned environment before touching application logic.
3. Fix login-page CSRF rendering and add new browser-path auth regression coverage.
4. Harden deferred requeue handling and crossed-completion idempotence before adding the reaper.
5. Add `reap_stuck_runs(...)`, wire it into the worker loop, add the manual script, and add the six reaper tests.
6. Run the full Stage 1 suite again and only then declare the hardening slice complete.

## Risks and controls

| ID | Risk | Impact | Control |
| --- | --- | --- | --- |
| R1 | Request-relative paths are interpreted at repo root instead of `triage-stage1/` | Wrong files are changed and validation becomes meaningless | Lock the plan to `triage-stage1/` paths and run all validation from that subproject directory |
| R2 | Bounded `requirements.txt` ranges are generated from an unclean or wrong Python version environment | Lockfile and bounds stop matching runtime behavior | Require a clean Python 3.12 environment for both freeze and verification |
| R3 | The CSRF fix mutates cookie issuance but still leaves template rendering order nondeterministic | Browser login still intermittently 403s | Keep `issue_login_csrf(...)` as-is and move the fix to context construction order with HTML-based regression coverage |
| R4 | Requeue flags are cleared before queue resolution is known | Requester reply or manual rerun intent is silently lost | Only clear `ticket.requeue_requested` / `ticket.requeue_trigger` after successful queue creation or confirmed already-active replacement |
| R5 | Reaper and worker-finalize paths both complete the same run | Duplicate notes, duplicate actions, or status flapping | Add a terminal-status/idempotence guard before publish/finalize work and cover crossover tests explicitly |
| R6 | Duplicate-active-run handling catches the wrong exception path or swallows unrelated DB errors | Real persistence bugs are masked or benign races still crash | Treat only `ActiveAIRunExistsError` and the specific active-run unique `IntegrityError` as benign, then re-raise everything else |
| R7 | README/documentation changes drift outside Stage 1 | Unnecessary repo churn | Limit doc edits to `triage-stage1/README.md` sections for Local Setup and Management commands only |
| R8 | SQLite-based tests do not naturally reproduce the PostgreSQL partial-index race | The fix appears covered while the production uniqueness crossover still fails | Make concurrency regression tests deterministic at the function boundary by simulating the conflicting insert/finalization path and asserting final state, not just relying on simultaneous SQLite writes |

## Completion gate

This plan is complete when the implementation pair can execute it without reinterpretation:

- all work is scoped to `triage-stage1/`
- dependency pinning is validated before application/worker hardening
- the login CSRF fix, requeue race fix, and stuck-run reaper all have concrete file targets and test expectations
- idempotence and requeue-state controls are explicit enough to avoid duplicate publication or lost requeue intent
- final validation is the full Stage 1 suite: `cd /workspace/docloop/triage-stage1 && python -m pytest tests/ -v`
