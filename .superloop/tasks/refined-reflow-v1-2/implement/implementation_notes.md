# refined-reflow-v1-2 implementation notes

## Files changed

* `refined_reflow_v1.2/SAD.md`
* `reflow_SAD_v1.2.md`
* `tests/test_refined_reflow_sad.py`
* `.superloop/tasks/refined-reflow-v1-2/implement/implementation_notes.md`
* `.superloop/tasks/refined-reflow-v1-2/test/test_strategy.md`

## Checklist mapping

* Confirm the canonical-output rule for `refined_reflow_v1.2/SAD.md` and `reflow_SAD_v1.2.md`.
  Completed by making the refined SAD explicitly canonical in Section 1 and replacing `reflow_SAD_v1.2.md` with a non-normative pointer.
* Build a section-by-section delta list from the current refined draft versus source/duplicate references.
  Completed during implementation analysis against `reflow/source.md`, `reflow/SAD.md`, and the prior duplicate `reflow_SAD_v1.2.md`; the concrete fixes were limited to canonical-source ambiguity and input-lifecycle consistency defects.
* Fix all heading, numbering, and internal-reference defects.
  Completed by removing the duplicate Section 14.4 heading and finalizing the Section 14 subsection sequence.
* Reconcile workflow, persistence, full-auto, failure-model, and provider-wrapper contracts across the document.
  Completed by tightening `pending_input.auto_round` initialization, full-auto request creation, and `reply_started` timing/lock semantics to match Sections 11, 12, 14, and 17.
* Apply the duplicate-file handling rule.
  Completed with the preferred pointer-file end state.
* Add a lightweight SAD regression test.
  Completed in `tests/test_refined_reflow_sad.py`.
* Update task-local implementation and test notes required by later pairs.
  Completed in this file and `.superloop/tasks/refined-reflow-v1-2/test/test_strategy.md`.
* Run targeted validation and record results for reviewer/tester consumption.
  Completed with `pytest -q tests/test_refined_reflow_sad.py` passing on 2026-03-16 UTC.

## Assumptions

* The preferred duplicate-handling outcome from the plan is authoritative, so a pointer file is better than maintaining two normative copies.
* Reviewer feedback was effectively empty for this pass, so no additional reviewer-resolution entry was needed in `implement/feedback.md`.
* A structural regression test is sufficient for this task; no runtime code changes were required.

## Expected side effects

* Repository readers now have one unambiguous v1.2 normative source.
* Future accidental SAD drift between the refined path and the legacy root-level path should fail quickly via the new test.
* The refined SAD now states the `pending_input` initialization and `reply_started` ordering rules more explicitly, which gives later implementers/testers a tighter acceptance target.

## Deduplication and centralization decisions

* Centralized v1.2 SAD authority in `refined_reflow_v1.2/SAD.md`.
* Replaced the duplicate root-level SAD with a pointer instead of mirroring the full document to remove ongoing maintenance debt.
