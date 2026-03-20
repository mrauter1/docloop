# Hardened Implementation Plan

## Scope
This plan addresses the **two confirmed production-impact defects** from the audit:
1. Login CSRF browser-submit robustness.
2. Stuck AI run recovery race/operability.

It also embeds the required execution specification for dependency pinning and stuck-run reaper delivery.

---

## A) Real Defect Plan 1 — Browser Login CSRF Robustness

### Root Cause Summary
- Browser login submits are validated by comparing form `csrf_token` to cookie token.
- In live rendering, hidden input was observed empty in-browser despite cookie issuance path.
- Result: normal browser submit can 403 unless token is manually injected.

### Remediation Plan
1. In `app/routes_auth.py::login_page`, construct template context **before** response creation and include a concrete `csrf_token` value directly in context payload.
2. Keep cookie issuance via `issue_login_csrf(...)`, but ensure context + cookie always aligned in same request cycle.
3. Add regression test for real form submit path (`GET /login` then `POST /login` using hidden token from HTML, not out-of-band cookie substitution).
4. Preserve strict mismatch behavior (403) for tampered CSRF.
5. Validate requester + Dev/TI login flows still redirect correctly.

### Acceptance Criteria
- Browser form login works without automation-side token injection.
- CSRF mismatch still fails with 403.
- Existing auth/session tests remain green.

---

## B) Real Defect Plan 2 — Active-Run Requeue Race Safety

### Root Cause Summary
- `ai_runs` enforces one active (`pending|running`) run per ticket with a unique partial index.
- Under concurrent run-finalization + requester-reply activity, enqueue can race and violate uniqueness.
- Result: intermittent `IntegrityError` and unstable supersede/requeue behavior.

### Remediation Plan
1. Make deferred requeue creation race-safe in `worker/queue.py`:
   - Convert check-then-insert to atomic insert-or-ignore/upsert pattern where possible.
   - Or catch unique `IntegrityError` and treat as benign already-queued state.
2. Ensure `ticket.requeue_requested` and `ticket.requeue_trigger` are cleared only when queueing state is resolved correctly.
3. Keep `finalize_success/failure/superseded` idempotent under duplicate or crossed completion events.
4. Add concurrency-focused regression tests for run finalization crossover with requester reply.
5. Validate no duplicate active runs and no unhandled IntegrityError.

### Acceptance Criteria
- No worker crash from unique active-run conflict in supersede path.
- At most one active run per ticket after races.
- Requeue intent is preserved and eventually processed.

---

# Implementation Plan: Dependency Pinning & Stuck-Run Reaper

## Context
These are the two highest-priority production-readiness items identified during the codebase audit. Both must be completed before the first production deployment.

### Problem 1 — Unpinned dependencies
`requirements.txt` has zero version pins. A pip install today and next week will produce different environments. Breaking changes in FastAPI, Pydantic, SQLAlchemy, or Starlette will cause silent failures or crashes. The `request.form(max_files=..., max_part_size=...)` calls in `app/routes_requester.py` depend on recent Starlette/python-multipart support and will break on older versions. Additionally, `markupsafe` is imported in `app/render.py` but not listed as a direct dependency.

### Problem 2 — No stuck-run recovery
If the worker process is killed mid-execution (SIGTERM, OOM, node restart), the `ai_runs` row stays in `running` status permanently. The partial unique index `uq_ai_runs_ticket_active` allows only one active run per ticket, so no new run can ever be created for that ticket — it is permanently stuck.

## Ground rules
- Do not refactor or reorganise existing code.
- Do not modify any existing test.
- Run the full test suite (`python -m pytest tests/ -v`) after each task. All existing tests must continue to pass.

---

## Task 1 — Pin All Dependencies

### Deliverables
1. A new file `requirements.lock` containing exact `==` pinned versions of every installed package (direct and transitive).
2. An updated `requirements.txt` that pins direct dependencies to minimum compatible versions using `>=X.Y.Z,<NEXT_MAJOR` bounds, with `markupsafe` added explicitly.
3. The `README.md` updated to reference `requirements.lock` for reproducible installs.

### Steps
1. Create a clean Python 3.12 virtual environment and install the current `requirements.txt`.
2. Run `pip freeze > requirements.lock`.
3. Verify the full test suite passes against the frozen environment.
4. Rewrite `requirements.txt` with bounded ranges derived from the resolved versions. Use `>=INSTALLED,<NEXT_MAJOR` for packages at or above 1.0. Use `>=0.x.y,<0.NEXT_MINOR` for 0.x packages. Add `markupsafe` as a direct dependency.
5. Re-run the full test suite against the bounded `requirements.txt` to confirm it resolves correctly.
6. In the `README.md` "Local Setup" section, after `pip install -r requirements.txt`, add a note about `pip install -r requirements.lock` for reproducible installs.

### Acceptance criteria
- `requirements.lock` exists with pinned `==` versions for every package.
- `requirements.txt` contains bounded ranges for all direct dependencies including `markupsafe`.
- Full test suite passes on a fresh install from either file.
- No existing file other than `requirements.txt` and `README.md` is modified.

---

## Task 2 — Stuck-Run Reaper

### Deliverables
1. A new function `reap_stuck_runs()` in `worker/main.py`.
2. Integration into the existing `run_worker_loop()`.
3. A new management script `scripts/reap_stuck_runs.py`.
4. A new test file `tests/test_stuck_run_reaper.py`.
5. Updated `README.md` documenting the reaper.

### 2a. Add `reap_stuck_runs()` to `worker/main.py`

Signature:
```python
def reap_stuck_runs(
    session_factory: sessionmaker[Session],
    *,
    settings: Settings,
    max_age_seconds: int | None = None,
    reaped_at: datetime | None = None,
) -> int:
```

Logic:
1. Default `max_age_seconds` to `settings.codex_timeout_seconds * 2` if not provided.
2. Default `reaped_at` to `now_utc()`.
3. Open a `session_scope(session_factory)` context.
4. Query all `AiRun` rows where `status == 'running'` AND `started_at IS NOT NULL` AND `started_at < reaped_at - timedelta(seconds=max_age_seconds)`. Order by `started_at ASC`.
5. For each stuck run, load the ticket. If the ticket is None, skip. Otherwise call existing `finalize_failure()` with:
   - `error_text=f"Run stuck in running state for over {max_age_seconds} seconds (started at {run.started_at.isoformat()}). Reaped by worker."`
   - `completed_at=reaped_at`
6. Log each reap using `_log("ai_run_reaped", ...)`.
7. Return the count of reaped runs.

Key constraint: reuse `finalize_failure()` from `worker/triage.py`. Do not duplicate logic.

### 2b. Integrate into `run_worker_loop()`
- Add `reap_stuck_runs()` immediately after heartbeat update block and before `process_next_run()`.
- Reaper runs every polling cycle.
- No new config needed; timeout derives from existing `CODEX_TIMEOUT_SECONDS`.

### 2c. Create `scripts/reap_stuck_runs.py`
- Follow existing script pattern from `scripts/`.
- Accept optional `--max-age-seconds`.
- Output structured JSON via `print_json()`.
- Accept `settings` and `session_factory` kwargs for testability.

### 2d. Create `tests/test_stuck_run_reaper.py`
Use same infrastructure style as `tests/test_worker_phase4.py` (helpers: `build_session_factory`, `seed_user`, `create_ticket_fixture`).

Write these 6 tests:

1. `test_reaper_marks_stuck_running_run_as_failed_and_routes_ticket`
   - Setup: Run in running, started_at 200s ago
   - Assert: Run failed, error contains `stuck`, ticket `waiting_on_dev_ti`, internal system note exists, return count = 1

2. `test_reaper_ignores_running_run_within_age_threshold`
   - Setup: Run running, started_at 60s ago, `max_age_seconds=150`
   - Assert: Run still running, return count = 0

3. `test_reaper_ignores_pending_and_completed_runs`
   - Setup: One pending run (no started_at), one succeeded run (started_at 200s ago)
   - Assert: Neither modified, return count = 0

4. `test_reaper_enqueues_deferred_requeue_when_requested`
   - Setup: Run running 200s ago, `ticket.requeue_requested=True`, `ticket.requeue_trigger="requester_reply"`
   - Assert: Original run failed, new pending run with `triggered_by="requester_reply"`, `ticket.requeue_requested=False`

5. `test_reaper_uses_double_codex_timeout_as_default_threshold`
   - Setup: `CODEX_TIMEOUT_SECONDS=30`, run started_at 65s ago, call with `max_age_seconds=None`
   - Assert: Run reaped (failed), return count = 1

6. `test_reap_stuck_runs_script_outputs_json`
   - Setup: Stuck run; call `scripts.reap_stuck_runs.main()`
   - Assert: exit 0, stdout JSON `{"status": "ok", "reaped_count": 1}`

### 2e. Update `README.md`
Add under Management commands:

**Stuck-run reaper**

The worker automatically reaps AI runs stuck in `running` state for longer than
 twice the configured `CODEX_TIMEOUT_SECONDS`. This handles cases where the worker
 process was killed mid-execution. To run the reaper manually:

```bash
python scripts/reap_stuck_runs.py
python scripts/reap_stuck_runs.py --max-age-seconds 300
```

### Acceptance criteria
- `reap_stuck_runs()` exists in `worker/main.py` and reuses `finalize_failure()`.
- Worker loop calls reaper every cycle.
- `scripts/reap_stuck_runs.py` exists and follows established script pattern.
- All 6 new tests pass.
- Full existing test suite passes with zero failures/errors.
- No existing function signature or behavior is changed.
- No existing test is modified.

---

## Execution order
1. Complete Task 1 first (establish reproducible environment for Task 2).
2. Complete Task 2 against pinned environment.
3. Run full test suite one final time.

## Files created or modified

| File | Action |
|------|--------|
| `requirements.lock` | Created (Task 1) |
| `requirements.txt` | Modified (Task 1) |
| `README.md` | Modified (Task 1 + Task 2) |
| `worker/main.py` | Modified (Task 2) |
| `scripts/reap_stuck_runs.py` | Created (Task 2) |
| `tests/test_stuck_run_reaper.py` | Created (Task 2) |

No other files are created or modified.

## Run Intent (2026-03-20T20:23:27.593852+00:00)
Fix review issue: lock/claim stuck-run reaper candidates in triage-stage1/worker/main.py to prevent duplicate reaping side effects under multi-worker concurrency; include tests proving single-claimer behavior.

## Run Intent (2026-03-20T20:23:37.307470+00:00)
Fix review issue: lock/claim stuck-run reaper candidates in triage-stage1/worker/main.py to prevent duplicate reaping side effects under multi-worker concurrency; include tests proving single-claimer behavior.
