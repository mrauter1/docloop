# test_strategy.md

## Phase 4 coverage map

Scope: worker queue execution, Codex artifact generation, stale-run suppression, terminal-state handling, and publication safety for requester-visible AI output.

### AC-P4-1: queue lifecycle, fingerprints, supersede, and deferred requeue

- Behavior: the worker claims the oldest pending run, writes the required Codex invocation artifacts, and succeeds on a public-only ticket.
  Coverage: `triage-stage1/tests/test_worker_phase4.py::test_worker_success_writes_workspace_artifacts_and_publishes_once`
- Behavior: if requester-visible input changes while a run is active, the stale run publishes nothing, is marked `superseded`, and exactly one fresh pending run is queued.
  Coverage: `triage-stage1/tests/test_worker_phase4.py::test_worker_marks_run_superseded_and_enqueues_single_requeue`
- Behavior: a non-manual run with an unchanged automatic-trigger fingerprint is skipped without publishing AI output.
  Coverage: `triage-stage1/tests/test_worker_phase4.py::test_worker_skips_non_manual_run_when_fingerprint_matches_last_processed_hash`

### AC-P4-2: successful publication paths and failure handling

- Behavior: a successful non-superseded run updates classification fields, emits exactly one internal AI note, writes final artifacts, and publishes exactly one automatic public reply when the context is public-only.
  Coverage: `triage-stage1/tests/test_worker_phase4.py::test_worker_success_writes_workspace_artifacts_and_publishes_once`
- Behavior: a failed Codex execution creates an internal failure note, sets the run to `failed`, and routes the ticket to `waiting_on_dev_ti` without requester-visible AI output.
  Coverage: `triage-stage1/tests/test_worker_phase4.py::test_worker_failure_routes_ticket_to_dev_ti_and_adds_internal_failure_note`

### AC-P4-3: internal/public separation for automatic publication

- Behavior: if internal notes exist and the model proposes an automatic public reply, the worker downgrades that result to a pending draft instead of auto-publishing it.
  Coverage: `triage-stage1/tests/test_worker_phase4.py::test_worker_disables_automatic_publication_when_internal_notes_exist`
- Behavior: if internal notes exist and the model proposes clarifying questions, the worker routes to Dev/TI instead of auto-publishing those requester-visible questions.
  Coverage: `triage-stage1/tests/test_worker_phase4.py::test_worker_routes_to_dev_ti_instead_of_asking_clarification_when_internal_notes_exist`

## Supporting regression coverage reused from earlier phases

- Dev/TI draft review, board filters, and ticket-view semantics:
  `triage-stage1/tests/test_ops_app.py`
- Requester isolation, reply/reopen semantics, and attachment authorization:
  `triage-stage1/tests/test_requester_app.py`
- Shared model/security invariants that phase-4 continues to rely on:
  `triage-stage1/tests/test_models.py`
  `triage-stage1/tests/test_security.py`
  `triage-stage1/tests/test_ticket_helpers.py`

## Determinism and flake control

- Worker tests use SQLite files inside per-test temporary directories; there is no shared DB state across tests.
- Codex execution is monkeypatched in worker tests, so there is no network dependency, no live CLI dependency, and no nondeterministic model output.
- Time-sensitive assertions use fixed UTC timestamps passed into `claim_next_run`, `finish_prepared_run`, or `process_next_run` rather than sleeps.
- Workspace artifact assertions read per-test temporary files only, which keeps filesystem effects isolated and deterministic.
