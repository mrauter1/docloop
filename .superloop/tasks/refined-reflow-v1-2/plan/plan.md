# Refined Reflow v1.2 Plan

## Goal

Deliver `refined_reflow_v1.2/SAD.md` as the canonical, implementation-ready Reflow v1.2 architecture document for this task, close remaining internal consistency gaps, and give the `implement` and `test` pairs a concrete acceptance target that can converge to COMPLETE without speculative rework.

## Repository facts and current gaps

- `.superloop/tasks/refined-reflow-v1-2/context.md` scopes the task to completing `refined_reflow_v1.2/SAD.md` end-to-end with all pairs converged.
- `refined_reflow_v1.2/SAD.md` already contains the intended v1.2 section set, so this is a refinement/completion task, not a greenfield draft.
- `reflow_SAD_v1.2.md` is a divergent duplicate of the same subject matter; the task needs an explicit canonical-source decision to avoid future drift.
- The refined draft already exposes at least one structural inconsistency that should be corrected in the implementation pass: Section 14 contains both `### 14.4 Full-auto mode` and `### 14.5 Full-auto mode`, with the answer-contract subsection inserted between them. That kind of numbering/cross-reference defect is small but blocks a credible “complete and consistent” outcome.
- Task-local implementation and test artifacts are still stub headers, so the plan must tell later pairs exactly which repository files to touch and how to prove completion.

## Scope

In scope:

- finish and normalize the normative content in `refined_reflow_v1.2/SAD.md`
- resolve cross-section inconsistencies and ambiguous wording inside the v1.2 architecture
- define how the duplicate `reflow_SAD_v1.2.md` is handled so only one normative source remains
- add a lightweight regression check for the completed SAD structure/content contracts
- update task-local Superloop artifacts required by later pairs

Out of scope:

- implementing the Reflow runtime described by the SAD
- refactoring `docloop.py`, `superloop.py`, or `loop_control.py`
- rewriting the older v1 documents except where needed to point at or align with the chosen v1.2 canonical artifact

## Canonical artifact decision

Primary artifact:

- `refined_reflow_v1.2/SAD.md` is the canonical task deliverable and the file that must be made complete.

Duplicate handling rule:

- `reflow_SAD_v1.2.md` must not remain a silently divergent second normative source.
- Acceptable end states are:
  1. it becomes an exact mirror of `refined_reflow_v1.2/SAD.md`, or
  2. it is reduced to a short pointer that clearly names `refined_reflow_v1.2/SAD.md` as the canonical source.
- Preferred end state: a short pointer, because it preserves DRY and removes future drift risk.

## Milestones

### Milestone 1: Baseline and delta map

Objective:

- turn the current refined draft into a tracked checklist of concrete gaps instead of editing ad hoc.

Implementation work:

- inventory the current section outline in `refined_reflow_v1.2/SAD.md`
- compare it against the older source materials in `reflow/source.md`, `reflow/SAD.md`, and the current duplicate `reflow_SAD_v1.2.md`
- record every required change as one of:
  - structural fix
  - missing norm
  - contradictory norm
  - duplicate-file handling

Acceptance criteria:

- every planned edit maps to a specific section in `refined_reflow_v1.2/SAD.md`
- there is an explicit decision for `reflow_SAD_v1.2.md`
- no code changes are proposed unless they directly support document verification

### Milestone 2: Normative SAD completion pass

Objective:

- make `refined_reflow_v1.2/SAD.md` internally consistent, standalone, and implementation-ready.

Implementation work:

- fix heading/section sequencing issues in Section 14 and any other numbering or cross-reference defects found during Milestone 1
- normalize normative language so related sections agree on the same contract:
  - workflow schema vs transitions vs policy
  - run state vs history vs operator-input lifecycle
  - runtime algorithm vs failure model
  - provider wrappers vs reserved-flag and invocation rules
  - testing requirements vs newly specified behaviors
- remove or rewrite any text that creates hidden behavior changes or contradictions across sections
- preserve the existing v1.2 design direction; do not add new subsystems unless a missing detail is required to make an existing contract implementable

Acceptance criteria:

- the refined SAD reads as one coherent normative spec from Sections 1 through 24
- every section that introduces a persisted field, event, exit code, or runtime branch is matched by the section that consumes it
- no unresolved duplicate numbering or stale internal references remain

### Milestone 3: Repository DRY cleanup

Objective:

- eliminate ambiguity about which v1.2 SAD file should be trusted.

Implementation work:

- apply the chosen duplicate-handling rule to `reflow_SAD_v1.2.md`
- if using a pointer file, keep it minimal and explicit
- if using a mirror file, copy only after the refined SAD is finalized so the duplicate is not hand-edited in parallel

Acceptance criteria:

- a repository reader can identify the canonical v1.2 SAD in one step
- there is no divergent normative content spread across two files

### Milestone 4: Regression proof and pair handoff

Objective:

- make the documentation change auditable by later Superloop pairs.

Implementation work:

- add a deterministic pytest file, preferably `tests/test_refined_reflow_sad.py`, that validates the completed SAD at a structural/contract level without snapshotting the full prose
- cover at least:
  - required top-level section order
  - presence of the v1.2-only contracts added in the refined draft
  - absence of duplicate/manual numbering defects in the finalized heading outline
  - canonical-source handling for the duplicate v1.2 file
- update `.superloop/tasks/refined-reflow-v1-2/implement/implementation_notes.md` with touched files, assumptions, duplicate-handling decision, and checklist mapping
- update `.superloop/tasks/refined-reflow-v1-2/test/test_strategy.md` with a behavior-to-test map
- append concise entries to the task-local `implement/feedback.md` and `test/feedback.md` only if later pairs need them for findings/resolution history

Acceptance criteria:

- the document change has at least one automated regression guard
- later pairs can verify what changed, why it changed, and how it was validated

## Interface definitions

### Artifact interface

- Canonical SAD input set:
  - `refined_reflow_v1.2/SAD.md`
  - `reflow/source.md`
  - `reflow/SAD.md`
  - `reflow_SAD_v1.2.md`
- Canonical SAD output:
  - finalized `refined_reflow_v1.2/SAD.md`
- Duplicate-file output:
  - either mirrored `reflow_SAD_v1.2.md` or a pointer file naming `refined_reflow_v1.2/SAD.md`

### Cross-section contract interface

- Section 7 workflow fields must line up with Sections 8, 9, 15, and 20.
- Section 11 persisted run-state fields must line up with Sections 6, 12, 14, 15, 17, and 21.
- Section 14 full-auto/input-request rules must line up with:
  - `pending_input` in Section 11.3
  - history events in Section 12.1
  - the runtime algorithm in Section 15
  - failure classification in Section 16
  - `reply` semantics in Section 17.3
- Section 18 provider wrappers must line up with provider config constraints in Section 10 and execution steps in Section 15.
- Section 22 tests must explicitly cover the behavior introduced by Sections 8, 9, 14, 15, 16, 17, and 18.

### Verification interface

- Preferred automated check: `pytest -q tests/test_refined_reflow_sad.py`
- Broader verification if fast enough: `pytest -q`
- The SAD regression test should assert structural invariants and critical contract phrases only; it should not freeze the entire document verbatim.

## Implementation checklist

- [ ] Confirm the canonical-output rule for `refined_reflow_v1.2/SAD.md` and `reflow_SAD_v1.2.md`.
- [ ] Build a section-by-section delta list from the current refined draft versus source/duplicate references.
- [ ] Fix all heading, numbering, and internal-reference defects.
- [ ] Reconcile workflow, persistence, full-auto, failure-model, and provider-wrapper contracts across the document.
- [ ] Apply the duplicate-file handling rule.
- [ ] Add a lightweight SAD regression test.
- [ ] Update task-local implementation and test notes required by later pairs.
- [ ] Run targeted validation and record results for reviewer/tester consumption.

## Risk register

| ID | Risk | Impact | Mitigation | Owner |
| --- | --- | --- | --- | --- |
| R1 | `refined_reflow_v1.2/SAD.md` and `reflow_SAD_v1.2.md` continue to diverge. | Reviewers or future readers may implement against different norms. | Enforce one canonical file and make the duplicate either an explicit pointer or a post-finalization mirror. | Implement |
| R2 | The implementation pass fixes prose locally but leaves cross-section contradictions. | The SAD looks complete while still being non-implementable. | Use the cross-section contract interface above as a mandatory trace during editing and review. | Implement + Review |
| R3 | New tests snapshot wording too aggressively. | Small wording improvements create noisy failures and slow future doc edits. | Test for headings, section presence, and critical contract markers instead of exact paragraph text. | Test |
| R4 | The task expands into runtime code changes because the doc describes behavior not yet implemented in the repo. | Scope balloons and pair convergence slows. | Keep this task document-focused; only add code when it directly supports deterministic verification of the SAD artifact. | Implement |
| R5 | Pair-local artifacts stay too vague for verifier use. | `implement` or `test` may stall even if the SAD itself is improved. | Require implementation notes, a test strategy map, and concise feedback entries that explain duplicate handling and validation scope. | Implement + Test |

## Exit condition

The task is ready for `implement` when `refined_reflow_v1.2/SAD.md` is the unambiguous canonical v1.2 spec, the duplicate-file decision is applied, a lightweight regression test exists, and the task-local implementation/test artifacts explain the change set clearly enough for their verifiers to mark COMPLETE without requesting missing scope details.
