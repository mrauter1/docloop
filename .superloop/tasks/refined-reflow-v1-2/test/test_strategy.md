# refined-reflow-v1-2 test strategy

## Behavior-to-test map

* Canonical source selection and duplicate handling:
  Covered by `tests/test_refined_reflow_sad.py::test_canonical_v12_source_and_pointer_contract_are_unambiguous` and `tests/test_refined_reflow_sad.py::test_legacy_v12_sad_path_is_only_a_pointer`.
  Happy path: canonical SAD declares itself normative and canonical.
  Edge case: root-level duplicate is reduced to a short pointer file instead of a mirrored second spec.
  Failure path guarded: reintroducing normative section content into `reflow_SAD_v1.2.md` or removing the duplicate-file rule fails the assertions.
* Top-level document completeness and heading repair:
  Covered by `tests/test_refined_reflow_sad.py::test_refined_sad_has_expected_top_level_section_order` and `tests/test_refined_reflow_sad.py::test_refined_sad_has_finalized_section_14_structure`.
  Happy path: Section 1 through Section 24 remain in the expected order.
  Edge case: Section 14 preserves the finalized `14.1` to `14.5` sequence.
  Failure path guarded: duplicate or missing `14.4` headings fail the structure check.
* `pending_input` initialization and repository-resident answer storage:
  Covered by `tests/test_refined_reflow_sad.py::test_pending_input_contract_preserves_question_order_and_auto_round_rules`.
  Happy path: detected questions preserve order and initialize `auto_round` to `0`.
  Edge case: `auto_round` is explicitly modeled as control-plane state.
  Failure path guarded: moving resolved answers back into `run.json` or dropping the initialization rule fails the test.
* Full-auto input lifecycle semantics:
  Covered by `tests/test_refined_reflow_sad.py::test_full_auto_mode_documents_budget_edge_success_and_failure_paths`.
  Happy path: successful auto answers append `input_resolved` and restart the same step.
  Edge case: hitting `max_auto_rounds` yields `awaiting_input` without another auto pass.
  Failure path: startup failure, nonzero exit, timeout, malformed `<answers>`, or wrong answer count must append `input_auto_failed` and preserve `pending_input`.
* History and `reply` ordering semantics:
  Covered by `tests/test_refined_reflow_sad.py::test_history_and_reply_contracts_capture_auto_failures_and_reply_ordering`.
  Happy path: `reply` reacquires the workspace lock and appends `reply_started` before collecting or auto-generating answers.
  Edge case: `--full-auto` replies use the full-auto answer path after controller ownership is restored.
  Failure path: `reply` without `pending_input` must fail, and `input_auto_failed` history records must carry `step`, `loop`, `auto_round`, and `reason`.
* Request assembly memory boundaries:
  Covered by `tests/test_refined_reflow_sad.py::test_request_assembly_keeps_context_and_operator_inputs_as_repository_resident_memory`.
  Happy path: `.reflow/context.md` and `operator_inputs.md` remain repository-resident memory.
  Edge case: requests reference `operator_inputs.md` by path through the footer.
  Failure path guarded: inlining repository memory into the request body or relocating working memory into `run.json` fails the test.

## Automated coverage in this pass

* `tests/test_refined_reflow_sad.py`
  Covers canonical-source handling, required top-level section order, finalized Section 14 structure, `pending_input` initialization, full-auto success/failure semantics, repository-resident memory, and `reply` lock/order/history contracts.

## Validation commands

* Primary:
  `pytest -q tests/test_refined_reflow_sad.py`
* Result in this pass:
  Passed on 2026-03-16 UTC (`8 passed`).

## Flake risk and stabilization

* Flake risk is low because coverage is file-content and section-structure based with no timing, network, subprocess race, or nondeterministic ordering dependencies.
* Stabilization approach: assertions target exact headings and normative sentences in repository files only, using deterministic local reads.

## Residual gaps

* The new regression test is intentionally structural and phrase-based; it does not validate every cross-reference or all prose-level semantics.
* No broader `pytest -q` sweep is planned unless the targeted SAD regression fails or exposes shared-test impacts.
