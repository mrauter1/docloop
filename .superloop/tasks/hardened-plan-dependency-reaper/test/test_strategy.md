# test_strategy.md

## Scope

Phase 1 covers the Stage 1 dependency baseline only:

- `triage-stage1/requirements.lock`
- `triage-stage1/requirements.txt`
- `triage-stage1/README.md`

No Stage 1 application code changed in this phase, and the phase contract explicitly keeps auth, worker, reaper, and existing test-file modifications out of scope.

## Behavior-to-test coverage map

| Behavior / acceptance target | Coverage approach | Evidence / command |
| --- | --- | --- |
| AC-P1-1: `triage-stage1/requirements.lock` contains exact resolved pins for the full install | Static artifact inspection of the generated lockfile shape and contents | Confirm every non-empty line in `triage-stage1/requirements.lock` is an exact `==` pin and that the file contains the resolved direct + transitive packages |
| AC-P1-2: `triage-stage1/requirements.txt` bounds every direct dependency from the resolved install and adds `markupsafe` | Static diff inspection against the resolved package versions | Confirm each direct dependency uses `>=installed,<next-major-or-next-0.x-minor` and that `markupsafe` is present explicitly |
| README Local Setup mentions reproducible installs | Static doc inspection | Confirm `triage-stage1/README.md` adds `pip install -r requirements.lock` directly after the default `requirements.txt` install flow |
| AC-P1-3 happy path: fresh install from `requirements.lock` passes the Stage 1 suite | Full regression suite in a clean Python 3.12 environment | `cd /workspace/docloop/triage-stage1 && /tmp/triage-stage1-locktest/bin/python -m pytest tests/ -v` |
| AC-P1-3 happy path: fresh install from bounded `requirements.txt` passes the Stage 1 suite | Full regression suite in a separate clean Python 3.12 environment | `cd /workspace/docloop/triage-stage1 && /tmp/triage-stage1-boundedtest/bin/python -m pytest tests/ -v` |
| Edge case: bounded direct requirements still resolve to a compatible environment instead of drifting to an incompatible floor/ceiling | Use a separate fresh environment rather than reusing the lockfile environment | Validate the bounded install independently so resolver behavior is exercised, not assumed |
| Failure-path guard: dependency baseline changes do not silently regress existing Stage 1 functionality | Rely on the existing Stage 1 regression suite rather than adding redundant dependency-specific app tests | Existing `triage-stage1/tests/` coverage remains the regression guard for auth, requester, ops, uploads, models, and worker flows under the newly resolved environments |

## Determinism / flake controls

- Use Python 3.12 explicitly for both fresh environments.
- Use separate clean virtual environments for lockfile and bounded-requirements validation to avoid cross-environment contamination.
- Run the same deterministic suite command from `triage-stage1/` for both validations: `python -m pytest tests/ -v`.
- No new timing-sensitive or network-dependent tests are introduced in this phase.

## Test additions

- No runtime test files were added or modified for phase 1 because the scoped changes are dependency and documentation updates only, and the phase contract forbids modifying existing tests.
- The test work for this phase is the explicit validation matrix above plus the recorded fresh-install full-suite executions.

## Phase 2 Scope

Phase 2 covers the Stage 1 auth and worker hardening slice:

- `triage-stage1/app/routes_auth.py`
- `triage-stage1/worker/queue.py`
- `triage-stage1/worker/triage.py`
- `triage-stage1/worker/main.py`
- `triage-stage1/scripts/reap_stuck_runs.py`
- `triage-stage1/tests/test_phase2_auth_worker_hardening.py`
- `triage-stage1/tests/test_stuck_run_reaper.py`
- `triage-stage1/README.md`

## Phase 2 Behavior-to-test coverage map

| Behavior / acceptance target | Coverage approach | Evidence / command |
| --- | --- | --- |
| AC-P2-1 happy path: browser-style login succeeds using the hidden form token and preserves requester / Dev-TI redirects | New integration coverage against the real FastAPI app and rendered login HTML | `tests/test_phase2_auth_worker_hardening.py::test_login_browser_submit_uses_hidden_token_and_preserves_role_redirects` |
| AC-P2-1 failure path: tampered login CSRF still returns `403` and re-renders a usable login form | New integration coverage against the real `/login` POST path with a tampered hidden token | `tests/test_phase2_auth_worker_hardening.py::test_login_browser_submit_rejects_tampered_hidden_token_with_403` |
| AC-P2-2 edge case: deferred requeue resolves safely when another active run is already visible and the helper raises `ActiveAIRunExistsError` | New worker-queue regression coverage with deterministic monkeypatched helper error | `tests/test_phase2_auth_worker_hardening.py::test_enqueue_deferred_requeue_clears_flags_when_active_run_is_already_visible` |
| AC-P2-2 failure-path guard: deferred requeue tolerates the active-run unique `IntegrityError` without crashing and still leaves one active run | New worker-queue regression coverage with deterministic monkeypatched database-race error | `tests/test_phase2_auth_worker_hardening.py::test_enqueue_deferred_requeue_handles_active_run_integrity_race` |
| Crossed-completion idempotence: worker completion after reaper finalization is a no-op and does not double-publish or enqueue again | New integration-style worker test around `claim_next_run(...)`, `finalize_failure(...)`, and `finish_prepared_run(...)` | `tests/test_phase2_auth_worker_hardening.py::test_finish_prepared_run_is_noop_after_reaper_already_failed_the_run` |
| AC-P2-3 happy path: stuck running run is failed, routed to Dev/TI, and emits the expected internal system note | New reaper regression coverage using the requested fixture style | `tests/test_stuck_run_reaper.py::test_reaper_marks_stuck_running_run_as_failed_and_routes_ticket` |
| AC-P2-3 boundary case: running run inside the age threshold is ignored | New reaper threshold coverage | `tests/test_stuck_run_reaper.py::test_reaper_ignores_running_run_within_age_threshold` |
| AC-P2-3 negative case: pending and completed runs are ignored | New reaper status-filter coverage | `tests/test_stuck_run_reaper.py::test_reaper_ignores_pending_and_completed_runs` |
| AC-P2-3 requeue behavior: reaper failure path enqueues the deferred requeue and clears the ticket flag | New reaper + queue integration coverage | `tests/test_stuck_run_reaper.py::test_reaper_enqueues_deferred_requeue_when_requested` |
| AC-P2-3 default-threshold behavior: reaper uses `CODEX_TIMEOUT_SECONDS * 2` when `max_age_seconds` is omitted | New reaper default-threshold coverage | `tests/test_stuck_run_reaper.py::test_reaper_uses_double_codex_timeout_as_default_threshold` |
| AC-P2-3 script contract: manual reaper entrypoint returns exit `0` and structured JSON | New management-script coverage using `capsys` | `tests/test_stuck_run_reaper.py::test_reap_stuck_runs_script_outputs_json` |
| Reaper concurrency guard: only one caller can claim and reap the same stuck run while the other call becomes a no-op | New threaded regression around two concurrent `reap_stuck_runs(...)` calls against one stale `running` row | `tests/test_stuck_run_reaper.py::test_reaper_claims_each_stuck_run_once_under_concurrent_calls` |
| AC-P2-4 regression shield: the full Stage 1 suite remains green in the pinned environment after the hardening slice and on the final diff | Full pinned-environment suite runs | `cd /workspace/docloop/triage-stage1 && /tmp/triage-stage1-locktest/bin/python -m pytest tests/ -v` |

## Phase 2 Determinism / flake controls

- Auth browser-submit coverage uses `TestClient` cookie persistence from `GET /login` to `POST /login` instead of synthetic token injection, matching browser behavior without network nondeterminism.
- Worker queue race coverage uses deterministic monkeypatched `ActiveAIRunExistsError` and `IntegrityError` paths instead of trying to create real timing-sensitive concurrent writers.
- Reaper coverage uses explicit UTC timestamps and local SQLite fixture databases, so age-threshold and ordering assertions are time-stable.
- The concurrent reaper regression coordinates its two threads with `threading.Event` gates instead of fixed sleeps, so the single-claimer assertion does not depend on scheduler timing.
- Script coverage calls `main(..., settings=..., session_factory=...)` directly and captures stdout with `capsys`, avoiding subprocess timing and environment drift.
- The pinned-environment validation stays on `/tmp/triage-stage1-locktest/bin/python`, matching the locked dependency baseline established in phase 1.

## Phase 2 Test additions

- Added `triage-stage1/tests/test_phase2_auth_worker_hardening.py` for browser-submit login CSRF, deferred requeue race handling, and crossed-completion idempotence.
- Added `triage-stage1/tests/test_stuck_run_reaper.py` with the six requested reaper and manual-script regression tests plus a concurrent single-claimer regression for the reaper claim hardening.
- Verified the two new modules first (`13 passed`) before running the full pinned-environment Stage 1 suite on the final phase-2 diff (`66 passed`).
