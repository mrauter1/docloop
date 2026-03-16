# Implementation Notes

## Files changed
- `loop_control.py`
- `docloop.py`
- `superloop.py`
- `README.md`
- `prompt_guideline.md`
- `.superloop/plan/prompt.md`
- `.superloop/plan/verifier_prompt.md`
- `.superloop/implement/prompt.md`
- `.superloop/implement/verifier_prompt.md`
- `.superloop/test/prompt.md`
- `.superloop/test/verifier_prompt.md`
- `tests/conftest.py`
- `tests/test_loop_control.py`
- `tests/fixtures/loop_control/`

## Checklist mapping
- Milestone 1 / Shared parsing module: added `loop_control.py` with the canonical schema/parser, legacy adapter path, parse error type, dataclasses, and shared `criteria_all_checked()`.
- Milestone 2 / Orchestrator refactor: rewired `docloop.py` and `superloop.py` to consume `parse_loop_control()`, fail fast on malformed/conflicting canonical output, and preserve existing question-first and verifier-defaulting behavior through small decision helpers.
- Milestone 3 / Prompt and docs migration: updated embedded prompts, checked-in `.superloop` prompt artifacts, `README.md`, and `prompt_guideline.md` to document canonical `<loop-control>` output as the default while keeping legacy compatibility explicit.
- Milestone 4 / Fixture-backed regression coverage: added fixture-backed parser tests plus focused orchestrator-semantics tests, and kept the existing git-tracking regression test in the targeted run.
  - Follow-up reviewer fix: canonical parsing now rejects any non-whitespace trailing output after the single `<loop-control>` block, and the fixture suite covers that protocol violation explicitly.

## Assumptions
- Legacy `<question>...</question>` payloads should remain opaque text in the adapter path; only canonical questions normalize `best_supposition` into a structured field.
- The checked-in `.superloop/*/prompt.md` and `verifier_prompt.md` files are the active prompts for this repository and needed direct updates in addition to the embedded template strings.
- Existing modified `.superloop/context.md`, `.superloop/plan/plan.md`, `.superloop/plan/feedback.md`, `.superloop/plan/criteria.md`, `.superloop/run_log.md`, and `.superloop/raw_phase_log.md` were treated as pre-existing workspace state and left untouched.

## Expected side effects
- Canonical malformed output, multiple canonical blocks, and canonical-plus-legacy semantic output now terminate both orchestrators immediately with a phase-specific fatal message instead of silently defaulting.
- Canonical output with any trailing prose after the `<loop-control>` block now terminates immediately instead of being accepted as valid control output.
- Canonical question payloads can carry `best_supposition`; when present, the human prompt shown by the orchestrator includes that supposition.
- Test collection now works reliably in this repo layout because `tests/conftest.py` adds the repository root to `sys.path`.

## Deduplication / centralization
- Removed duplicated promise constants, regex parsing, and checklist parsing from `docloop.py` and `superloop.py` by centralizing them in `loop_control.py`.
- Kept orchestrator-specific branch-order semantics local via small pure decision helpers rather than pushing divergent runtime behavior into the shared parser module.

## Verification
- `python -m py_compile docloop.py superloop.py loop_control.py tests/test_loop_control.py tests/test_superloop_git_tracking.py tests/conftest.py`
- `pytest tests/test_loop_control.py tests/test_superloop_git_tracking.py`

## Deferred
- None.
