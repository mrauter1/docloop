# test_strategy.md

## Phase 6 coverage map

Scope: acceptance hardening for AC1-AC19, with emphasis on session behavior, requester isolation, upload limits, unread tracking, worker queue invariants, draft flows, non-leak safeguards, and operator-facing acceptance documentation.

### AC-P6-1: all PRD acceptance criteria are traceable to implementation and verification

- Behavior: AC1-AC19 are explicitly mapped to code paths plus automated or manual verification steps instead of relying on phase-log prose.
  Coverage:
  `triage-stage1/docs/acceptance_matrix.md`
  `triage-stage1/docs/manual_verification.md`
  `triage-stage1/README.md`

### AC-P6-2: regression coverage spans the highest-risk Stage 1 acceptance behaviors

- Behavior: login creates opaque server-side sessions, remember-me persistence differs from normal sessions, and expired sessions no longer authorize requester routes.
  Coverage:
  `triage-stage1/tests/test_requester_app.py::test_login_creates_server_side_session_with_opaque_cookie`
  `triage-stage1/tests/test_requester_app.py::test_login_cookie_persistence_matches_remember_me_choice`
  `triage-stage1/tests/test_requester_app.py::test_expired_session_redirects_requester_back_to_login`
  `triage-stage1/tests/test_security.py::test_session_max_age_only_for_remember_me`

- Behavior: requesters remain isolated to their own tickets and attachments, and requester unread markers clear only after the detail view is opened.
  Coverage:
  `triage-stage1/tests/test_requester_app.py::test_requester_cannot_access_another_users_ticket_or_attachment`
  `triage-stage1/tests/test_requester_app.py::test_requester_list_marks_ticket_updated_until_ticket_is_opened`
  `triage-stage1/tests/test_ops_app.py::test_ops_view_tracking_only_updates_on_detail_and_successful_mutations`

- Behavior: uploads enforce file-type, file-count, and file-size constraints deterministically.
  Coverage:
  `triage-stage1/tests/test_requester_app.py::test_invalid_attachment_type_is_rejected`
  `triage-stage1/tests/test_uploads.py::test_validate_public_image_uploads_rejects_more_than_max_files`
  `triage-stage1/tests/test_uploads.py::test_validate_public_image_uploads_rejects_files_over_size_limit`

- Behavior: requester replies on resolved tickets reopen the ticket and requeue correctly.
  Coverage:
  `triage-stage1/tests/test_requester_app.py::test_requester_reply_on_resolved_ticket_sets_reopen_requeue_when_run_active`

- Behavior: worker queue invariants hold for skip-on-hash, manual rerun bypass, stale-run supersession, deferred requeue, and failure routing.
  Coverage:
  `triage-stage1/tests/test_worker_phase4.py::test_worker_skips_non_manual_run_when_fingerprint_matches_last_processed_hash`
  `triage-stage1/tests/test_worker_phase4.py::test_worker_processes_manual_rerun_even_when_fingerprint_matches_last_processed_hash`
  `triage-stage1/tests/test_worker_phase4.py::test_worker_marks_run_superseded_and_enqueues_single_requeue`
  `triage-stage1/tests/test_worker_phase4.py::test_worker_failure_routes_ticket_to_dev_ti_and_adds_internal_failure_note`
  `triage-stage1/tests/test_ticket_helpers.py::test_create_pending_ai_run_rejects_second_active_run`

- Behavior: draft flows cover worker supersession of older drafts plus ops publish/reject review paths.
  Coverage:
  `triage-stage1/tests/test_worker_phase4.py::test_worker_new_draft_supersedes_older_pending_draft`
  `triage-stage1/tests/test_ops_app.py::test_ops_can_publish_ai_draft_without_exposing_internal_note_to_requester`
  `triage-stage1/tests/test_ops_app.py::test_ops_can_reject_pending_draft_without_publishing_message`
  `triage-stage1/tests/test_ticket_helpers.py::test_supersede_pending_drafts_only_touches_pending_approval`

- Behavior: non-leak safeguards prevent requester-visible AI output from exposing internal-note-only context.
  Coverage:
  `triage-stage1/tests/test_worker_phase4.py::test_worker_disables_automatic_publication_when_internal_notes_exist`
  `triage-stage1/tests/test_worker_phase4.py::test_worker_routes_to_dev_ti_instead_of_asking_clarification_when_internal_notes_exist`
  `triage-stage1/tests/test_ops_app.py::test_ops_can_publish_ai_draft_without_exposing_internal_note_to_requester`

- Behavior: CLI/bootstrap/readiness coverage from phase 5 remains the active regression net for clean local bootstrap and operator setup.
  Coverage:
  `triage-stage1/tests/test_phase5_operability.py::test_bootstrap_workspace_script_creates_git_artifacts_and_bootstrap_state`
  `triage-stage1/tests/test_phase5_operability.py::test_user_management_scripts_create_reset_and_deactivate_accounts`
  `triage-stage1/tests/test_phase5_operability.py::test_health_and_readiness_routes_report_bootstrap_state`
  `triage-stage1/tests/test_phase5_operability.py::test_run_web_script_passes_configured_app_to_uvicorn`
  `triage-stage1/tests/test_phase5_operability.py::test_run_worker_script_passes_once_flag_to_worker_loop`

### AC-P6-3: final documentation is sufficient for clean bootstrap and local run

- Behavior: the repository documents isolated environment setup, migrations, workspace bootstrap, management commands, service startup, and acceptance verification artifacts.
  Coverage:
  `triage-stage1/README.md`
  `triage-stage1/docs/acceptance_matrix.md`
  `triage-stage1/docs/manual_verification.md`

## Determinism and flake control

- The added requester, worker, and upload tests use per-test temporary SQLite databases, uploads directories, and workspace roots, so state is isolated across runs.
- Worker tests avoid live Codex CLI execution by monkeypatching `worker.main.run_codex` and writing deterministic JSON payloads directly into the prepared artifact path.
- Upload-limit helper tests instantiate in-memory `UploadFile` objects directly and avoid dependence on framework-specific multipart exception formatting or transport behavior.
- Unread-marker tests force timestamps into a stable relative ordering by writing the synthetic last-viewed time explicitly before simulating the later Dev/TI reply.
- The broad regression command for this phase is `pytest -q triage-stage1/tests`; producer and reviewer both confirmed it passes with 53 tests.
