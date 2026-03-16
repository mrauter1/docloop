# Superloop Raw Phase Log


---
pair=plan | phase=producer | process=codex-agent | iteration=1
---
[empty stdout]


---
pair=plan | phase=producer | process=codex-agent | iteration=1
---
Updated [plan.md](/workspace/CodexTest/docloop/.superloop/plan/plan.md) with an implementation-ready Priority 1 plan for a shared `loop_control.py` module, a canonical `<loop-control>` JSON contract, explicit legacy-adapter behavior, orchestrator integration steps, fixture-backed parser coverage, milestones, checklist, and risk register.

Appended a concise audit note to [feedback.md](/workspace/CodexTest/docloop/.superloop/plan/feedback.md). I did not modify verifier-owned [criteria.md](/workspace/CodexTest/docloop/.superloop/plan/criteria.md), and I did not run tests because this turn was planning-only.


---
pair=plan | phase=producer | process=codex-agent | iteration=1
---
<question>What specific feature, bug fix, or change should this plan cover in `/workspace/CodexTest/docloop`? Best suggestion/supposition: you intended to provide a concrete implementation request next, and once you do, I should analyze the relevant code paths and update `.superloop/plan/plan.md` and `.superloop/plan/feedback.md` accordingly.</question>


---
pair=plan | phase=producer | process=codex-agent | iteration=1
---
Updated [plan.md](/workspace/CodexTest/docloop/.superloop/plan/plan.md) and [feedback.md](/workspace/CodexTest/docloop/.superloop/plan/feedback.md).

The revised plan is now grounded in the actual repo behavior instead of a generic migration outline. It explicitly preserves current legacy question-first semantics, calls out that the checked-in `.superloop` prompt files must be updated alongside `superloop.py` template constants, defines the shared `loop_control.py` API and parse-failure behavior more concretely, and tightens the parser fixture matrix to cover the real regression surfaces.

I did not run tests, since this pass only updated planning artifacts.


---
pair=plan | phase=verifier | process=codex-agent | iteration=1
---
Updated [criteria.md](/workspace/CodexTest/docloop/.superloop/plan/criteria.md) and [feedback.md](/workspace/CodexTest/docloop/.superloop/plan/feedback.md).

Blocking findings:
- `PLAN-001`: the plan does not define what happens if stdout contains multiple canonical `<loop-control>` blocks, so the proposed “use the last block” rule can silently discard an earlier conflicting control signal.
- `PLAN-002`: the planned tests cover parser fixtures but not the preserved `docloop.py` / `superloop.py` branch semantics, so the refactor could regress runtime behavior without failing the proposed suite.

Non-blocking:
- `PLAN-003`: `prompt_guideline.md` will become stale if the canonical contract ships but that guidance file stays on the legacy protocol.

<promise>INCOMPLETE</promise>


---
pair=plan | phase=producer | process=codex-agent | iteration=2
---
<question>What implementation request should this plan cover? I do not have a feature/bug/task description to turn into milestones and interfaces. Best suggestion/supposition: send the specific change you want planned, and I will update `.superloop/plan/plan.md` and `.superloop/plan/feedback.md` for that scope only.</question>


---
pair=plan | phase=producer | process=codex-agent | iteration=2
---
Updated the planning artifacts.

`.superloop/plan/plan.md` now explicitly makes multiple canonical `<loop-control>` blocks a parse error, adds concrete regression coverage for the preserved `docloop.py` and `superloop.py` branch semantics, and includes `prompt_guideline.md` in the docs-migration scope so prompt guidance stays aligned with the runtime contract.

`.superloop/plan/feedback.md` has a new entry summarizing those corrections and why they were added. I did not edit `.superloop/plan/criteria.md`.


---
pair=plan | phase=verifier | process=codex-agent | iteration=2
---
Updated the verifier-owned artifacts only.

`.superloop/plan/criteria.md` now has all five boxes checked. `.superloop/plan/feedback.md` has a new verification note confirming the revised plan was checked against `docloop.py`, `superloop.py`, `README.md`, `prompt_guideline.md`, and the current test surface, with no remaining blocking or non-blocking findings in this pass.

<promise>COMPLETE</promise>


---
pair=implement | phase=producer | process=codex-agent | iteration=1
---
Implemented the shared canonical loop-control contract and removed the duplicated parser/checklist logic from both orchestrators.

The core change is the new shared parser module in [loop_control.py](/workspace/CodexTest/docloop/loop_control.py#L1), which defines the canonical `<loop-control>` JSON schema, legacy adapter behavior, and hard-failure cases for malformed or double-signaled canonical output. `docloop.py` now routes writer/verifier control handling through that module and preserves the old question-first and verifier-defaulting semantics via small decision helpers in [docloop.py](/workspace/CodexTest/docloop/docloop.py#L615). `superloop.py` does the same for producer/verifier pair behavior in [superloop.py](/workspace/CodexTest/docloop/superloop.py#L589).

I also updated the embedded prompts, checked-in `.superloop` prompt artifacts, and the docs to make canonical loop-control the default contract while documenting legacy compatibility and failure behavior in [README.md](/workspace/CodexTest/docloop/README.md#L13) and [prompt_guideline.md](/workspace/CodexTest/docloop/prompt_guideline.md#L1). Regression coverage is in [tests/test_loop_control.py](/workspace/CodexTest/docloop/tests/test_loop_control.py#L1) with fixture-backed cases under [tests/fixtures/loop_control](/workspace/CodexTest/docloop/tests/fixtures/loop_control), and the implementation summary is recorded in [.superloop/implement/implementation_notes.md](/workspace/CodexTest/docloop/.superloop/implement/implementation_notes.md#L1).

Verification: `python -m py_compile docloop.py superloop.py loop_control.py tests/test_loop_control.py tests/test_superloop_git_tracking.py tests/conftest.py` and `pytest tests/test_loop_control.py tests/test_superloop_git_tracking.py` both passed. Unrelated pre-existing `.superloop` workspace changes were left untouched.


---
pair=implement | phase=verifier | process=codex-agent | iteration=1
---
IMP-001 `blocking`: [loop_control.py](/workspace/CodexTest/docloop/loop_control.py#L53) accepts canonical `<loop-control>` blocks even when non-empty prose follows them. A verifier output like canonical `COMPLETE` plus trailing text is currently treated as success by both orchestrators, even though the new contract requires the canonical block to be the last non-empty logical block and to fail fast otherwise. Minimal fix: make `parse_loop_control()` reject trailing non-whitespace content outside the single canonical block, and add a regression fixture/test for that case.

Updated [.superloop/implement/criteria.md](/workspace/CodexTest/docloop/.superloop/implement/criteria.md) and [.superloop/implement/feedback.md](/workspace/CodexTest/docloop/.superloop/implement/feedback.md). I also ran `pytest -q` and the suite passed locally; this remains a review finding because the existing tests do not cover the trailing-prose protocol violation.

<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"INCOMPLETE"}
</loop-control>


---
pair=implement | phase=producer | process=codex-agent | iteration=2
---
Tightened canonical loop-control parsing so a `<loop-control>` block is only valid if it is the last non-empty output block. The parser now rejects any trailing prose after the canonical block, while still allowing leading prose and still rejecting legacy mixed-signals before the block. See [loop_control.py](/workspace/CodexTest/docloop/loop_control.py#L69).

Added the missing regression coverage for that reviewer finding by extending the invalid-canonical fixture set in [tests/test_loop_control.py](/workspace/CodexTest/docloop/tests/test_loop_control.py#L52) and adding `canonical_trailing_prose.txt` under [tests/fixtures/loop_control](/workspace/CodexTest/docloop/tests/fixtures/loop_control/canonical_trailing_prose.txt). I also updated the implementation record in [.superloop/implement/implementation_notes.md](/workspace/CodexTest/docloop/.superloop/implement/implementation_notes.md#L19).

Verification passed:
- `python -m py_compile docloop.py superloop.py loop_control.py tests/test_loop_control.py tests/test_superloop_git_tracking.py tests/conftest.py`
- `pytest tests/test_loop_control.py tests/test_superloop_git_tracking.py` with `30 passed`


---
pair=implement | phase=verifier | process=codex-agent | iteration=2
---
No blocking or non-blocking findings remain in the current implementation diff.

Updated [criteria.md](/workspace/CodexTest/docloop/.superloop/implement/criteria.md) to mark all review criteria complete, and appended a resolution note to [feedback.md](/workspace/CodexTest/docloop/.superloop/implement/feedback.md) recording that `IMP-001` is fixed. Verification passed with `pytest -q` (`30 passed`).

<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"COMPLETE"}
</loop-control>


---
pair=implement | phase=producer | process=codex-agent | iteration=3
---
The current diff already implements the approved plan and the reviewer’s `IMP-001` fix. I verified the shared parser in [loop_control.py](/workspace/CodexTest/docloop/loop_control.py), the orchestrator integrations in [docloop.py](/workspace/CodexTest/docloop/docloop.py) and [superloop.py](/workspace/CodexTest/docloop/superloop.py), the fixture-backed coverage in [tests/test_loop_control.py](/workspace/CodexTest/docloop/tests/test_loop_control.py), and the implementation record in [.superloop/implement/implementation_notes.md](/workspace/CodexTest/docloop/.superloop/implement/implementation_notes.md). No additional code edits were needed.

Verification passed:
- `python -m py_compile docloop.py superloop.py loop_control.py tests/test_loop_control.py tests/test_superloop_git_tracking.py tests/conftest.py`
- `pytest tests/test_loop_control.py tests/test_superloop_git_tracking.py`

Result: `30 passed in 0.53s`.


---
pair=implement | phase=verifier | process=codex-agent | iteration=3
---
No remaining blocking or non-blocking findings in the current implementation diff. I left all review criteria checked in [criteria.md](/workspace/CodexTest/docloop/.superloop/implement/criteria.md) and appended the clean review outcome to [feedback.md](/workspace/CodexTest/docloop/.superloop/implement/feedback.md).

Verification: `pytest -q tests/test_loop_control.py tests/test_superloop_git_tracking.py` passed (`30 passed`), and `python -m py_compile docloop.py superloop.py loop_control.py tests/test_loop_control.py tests/test_superloop_git_tracking.py tests/conftest.py` completed successfully. Residual risk is limited to live Codex CLI end-to-end behavior, which is not exercised by these tests.

<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"COMPLETE"}
</loop-control>
