# implementation_notes.md

## Files changed

- `triage-stage1/requirements.lock`
- `triage-stage1/requirements.txt`
- `triage-stage1/README.md`
- `triage-stage1/app/routes_auth.py`
- `triage-stage1/worker/queue.py`
- `triage-stage1/worker/triage.py`
- `triage-stage1/worker/main.py`
- `triage-stage1/scripts/reap_stuck_runs.py`
- `triage-stage1/tests/test_phase2_auth_worker_hardening.py`
- `triage-stage1/tests/test_stuck_run_reaper.py`

## Checklist mapping

- Milestone 1 / AC-P1-1: Added `triage-stage1/requirements.lock` from a clean Python 3.12 resolved install with exact `==` pins for direct and transitive packages.
- Milestone 1 / AC-P1-2: Rewrote `triage-stage1/requirements.txt` with bounded direct dependencies derived from the resolved install and added explicit `markupsafe`.
- Milestone 1 / docs: Updated `triage-stage1/README.md` Local Setup guidance to mention `pip install -r requirements.lock` for reproducible installs.
- Milestone 1 / AC-P1-3: Validated the full Stage 1 pytest suite from a fresh `requirements.lock` install and from a separate fresh bounded-`requirements.txt` install, both under Python 3.12.
- Milestone 2 / AC-P2-1: Fixed login-page CSRF rendering by generating the login token before `TemplateResponse` creation and added focused browser-submit regression coverage for hidden-token login, tampered-token 403 handling, and requester/Dev-TI redirects.
- Milestone 3 / AC-P2-2: Hardened deferred requeue creation to tolerate helper-level `ActiveAIRunExistsError` and active-run unique `IntegrityError`, and added crossed-completion no-op guards so duplicate finalization paths cannot double-publish or enqueue duplicate runs.
- Milestone 4 / AC-P2-3: Added `reap_stuck_runs(...)`, invoked it from each worker polling cycle, added `triage-stage1/scripts/reap_stuck_runs.py`, documented the reaper in `triage-stage1/README.md`, and added the requested six reaper tests.
- Milestone 4 / AC-P2-4: Completed two full Stage 1 suite runs in the pinned environment on the phase-2 diff, both passing with `65 passed`.

## Assumptions

- Phase 1 scope remains limited to the `triage-stage1/` dependency and documentation files plus this implementation note.
- Phase 2 scope is limited to Stage 1 auth, queue, reaper, docs, and new regression test files; no schema or config changes were introduced.
- The direct dependency set is the Stage 1 list called out in the approved plan, with `markupsafe` added explicitly because it is imported directly in Stage 1 code.

## Expected side effects

- Fresh Stage 1 installs become reproducible with `requirements.lock`.
- Direct installs from `requirements.txt` remain flexible within the currently validated major or minor compatibility window, depending on package versioning.
- Browser login forms now render a concrete hidden CSRF token in the initial HTML response instead of relying on post-render context mutation.
- Worker completion paths now treat already-terminal runs as resolved and only clear requeue flags after queue state is safely established.
- Worker polling now automatically reaps stale `running` rows whose age exceeds twice `CODEX_TIMEOUT_SECONDS`, with an equivalent manual script for operators.
- Stuck-run reaping now claims candidates before publishing failure side effects so concurrent worker loops cannot double-reap the same run.

## Deduplication / centralization decisions

- Centralized login-form re-rendering in `triage-stage1/app/routes_auth.py` via a single `_login_template_response(...)` helper so the GET, 403, and invalid-credential branches all issue aligned CSRF token context plus cookie pairs.
- Reused `finalize_failure(...)` as the single stuck-run recovery path instead of duplicating failure routing logic in the reaper.
- Kept the reaper concurrency hardening inside `triage-stage1/worker/main.py` with a single claim helper that uses `FOR UPDATE SKIP LOCKED` on PostgreSQL and a compare-and-swap fallback on `AiRun.error_text` elsewhere, avoiding schema or config changes.
