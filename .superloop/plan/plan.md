# Priority 1 Plan: Canonical Loop-Control Contract

## Goal
Implement one shared machine-readable loop-control contract for `docloop.py` and `superloop.py`, preserve current legacy tag behavior through an adapter path, remove duplicated parsing code, and add fixture-backed parser tests.

## Codebase Findings
- `docloop.py` and `superloop.py` each define their own `PROMISE_*` constants, `PROMISE_LINE_RE`, `last_non_empty_line()`, `extract_control_tags()`, and `criteria_all_checked()`.
- Both orchestrators currently understand only legacy control outputs:
  - `<question>...</question>` anywhere in stdout
  - verifier final-line `<promise>COMPLETE|INCOMPLETE|BLOCKED</promise>`
- Current loop semantics are not identical to a simple “one tag only” model:
  - legacy `<question>` takes precedence because both orchestrators branch on question before promise
  - `docloop.py` treats writer promise output as fatal only if no question path already short-circuited
  - `superloop.py` ignores producer promises only if no question path already short-circuited
  - verifier missing promise defaults to `INCOMPLETE`
  - verifier `COMPLETE` still requires all criteria boxes checked
- `superloop.py` seeds prompt files only when absent, but this repository already checks in `.superloop/*/prompt.md` and `.superloop/*/verifier_prompt.md`. Updating only the in-code prompt templates would not change the active prompts in this repo.
- Existing automated coverage is limited to [`tests/test_superloop_git_tracking.py`](/workspace/CodexTest/docloop/tests/test_superloop_git_tracking.py). No parser contract tests exist today.

## Scope
- Add one shared `loop_control.py` module used by both orchestrators.
- Define one canonical `<loop-control>...</loop-control>` JSON contract with schema ID `docloop.loop_control/v1`.
- Preserve legacy compatibility through explicit adapter logic rather than duplicated inline regex parsing.
- Update runtime prompt templates and checked-in `.superloop` prompt artifacts to document the canonical contract as the default.
- Update [`README.md`](/workspace/CodexTest/docloop/README.md) to describe canonical behavior, legacy compatibility, and malformed canonical failure behavior.
- Add fixture-backed parser tests for canonical, legacy, malformed, missing, and mixed-output cases.

## Non-Goals
- Do not change git checkpointing, iteration limits, pair ordering, cooldown timing, verifier scope warnings, or criteria ownership rules.
- Do not remove legacy `<question>` / `<promise>` support in this priority.
- Do not add external schema-validation dependencies; use standard-library parsing and explicit validation.
- Do not broaden the change into a larger prompt-system redesign or agent output rendering helper unless implementation proves that necessary.

## Canonical Contract

### Format
Canonical control output becomes a dedicated tagged JSON block:

```text
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"question","question":"...","best_supposition":"..."}
</loop-control>
```

```text
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"COMPLETE"}
</loop-control>
```

### Schema Rules
- `schema` is required and must equal `docloop.loop_control/v1`.
- `kind` is required and must be exactly `question` or `promise`.
- `kind=question` requires `question` as a non-empty string after trimming.
- `kind=question` may include `best_supposition` as a non-empty string after trimming.
- `kind=promise` requires `promise` with enum `COMPLETE | INCOMPLETE | BLOCKED`.
- Unknown top-level fields are ignored for forward compatibility.
- One canonical payload represents exactly one decision. A canonical block that tries to encode both question and promise semantics is invalid.
- Stdout may contain at most one canonical `<loop-control>...</loop-control>` block. Multiple canonical blocks are invalid and must raise `LoopControlParseError`.

### Placement Rules
- Prompt text should instruct agents to emit the canonical block as the last non-empty logical block in stdout.
- Parser support should tolerate surrounding prose before the canonical block so existing debug text does not break the run.
- Legacy promise recognition keeps the current strict last-non-empty-line rule.

## Shared Module And Interface

### New module
- Add [`loop_control.py`](/workspace/CodexTest/docloop/loop_control.py).

### Public API
- `CONTROL_SCHEMA_ID = "docloop.loop_control/v1"`
- `PROMISE_COMPLETE`, `PROMISE_INCOMPLETE`, `PROMISE_BLOCKED`
- `class LoopControlParseError(ValueError)`
- `@dataclass(frozen=True) class LoopQuestion:`
  - `text: str`
  - `best_supposition: str | None = None`
- `@dataclass(frozen=True) class LoopControl:`
  - `question: LoopQuestion | None`
  - `promise: str | None`
  - `source: Literal["canonical", "legacy", "none"]`
  - `raw_payload: str | None`
- `parse_loop_control(stdout: str) -> LoopControl`
- `criteria_all_checked(criteria_file: Path) -> bool`

### Parser Behavior
- Canonical detection runs first by scanning stdout for `<loop-control>...</loop-control>` blocks.
- Zero canonical blocks means the parser falls back to the legacy adapter path.
- Exactly one canonical block means JSON-decode and validate that block.
- More than one canonical block is a protocol violation and raises `LoopControlParseError`.
- If no canonical block exists, fall back to the current legacy rules.
- If a canonical block exists but is malformed, raise `LoopControlParseError` and do not silently fall back to legacy parsing.
- Legacy-only parsing must preserve current behavior:
  - `<question>` may appear anywhere in stdout
  - `<promise>` is recognized only from the last non-empty line
  - if both legacy question and legacy promise are present, return both so existing question-first call-site behavior stays unchanged
- Canonical output is the single source of truth. If canonical control output appears together with additional legacy semantic control tags, treat that as a parse error rather than guessing between double-signals.
- If no control signal exists, return `LoopControl(question=None, promise=None, source="none", raw_payload=None)`.

## Call-Site Integration

### `docloop.py`
- Replace local `PROMISE_*`, `PROMISE_LINE_RE`, `last_non_empty_line()`, `extract_control_tags()`, and `criteria_all_checked()` usage with imports from `loop_control.py`.
- Preserve current runtime behavior:
  - writer question still pauses for human input and restarts the cycle
  - writer promise remains fatal only on the existing no-question path
  - writer question still wins if legacy output contains both a question and a final-line promise
  - verifier question still pauses for human input and restarts the cycle
  - missing verifier promise still defaults to `INCOMPLETE`
  - verifier `COMPLETE` still hard-fails if criteria remain unchecked
- On `LoopControlParseError`, fail fast with a clear fatal message that names the phase and explains that canonical loop-control output was malformed or double-signaled.

### `superloop.py`
- Replace local parsing helpers and duplicated constants with imports from `loop_control.py`.
- Preserve current pair semantics:
  - producer question still pauses or auto-answers before any promise handling
  - producer promise is still ignored on the existing no-question path because verifier controls completion
  - producer question still wins if legacy output contains both a question and a final-line promise
  - verifier missing promise still appends the current warning to pair feedback and defaults to `INCOMPLETE`
  - verifier `COMPLETE` with unchecked criteria still downgrades to `INCOMPLETE` in current lax-guard mode
- On `LoopControlParseError`, fail fast instead of defaulting to `INCOMPLETE`.

## Prompt And Documentation Changes

### `docloop.py` embedded prompt templates
- Update `DEFAULT_PROMPT`, `DEFAULT_VERIFIER_PROMPT`, `DEFAULT_UPDATE_PROMPT`, and `DEFAULT_UPDATE_VERIFIER_PROMPT` to show canonical `<loop-control>` examples as the default contract.
- Keep the “do not emit promise from writer/update-writer” rules unchanged.
- Preserve current stricter update-mode question guidance by mapping it onto canonical question payloads with `best_supposition`.

### `superloop.py` embedded prompt templates
- Update `PAIR_PRODUCER_PROMPT` and `PAIR_VERIFIER_PROMPT` examples and completion instructions to use canonical `<loop-control>` JSON blocks.
- Keep verifier ownership rules unchanged.

### Checked-in `.superloop` prompt artifacts
- Update these existing prompt files because they are the active prompts in this repository:
  - [`/.superloop/plan/prompt.md`](/workspace/CodexTest/docloop/.superloop/plan/prompt.md)
  - [`/.superloop/plan/verifier_prompt.md`](/workspace/CodexTest/docloop/.superloop/plan/verifier_prompt.md)
  - [`/.superloop/implement/prompt.md`](/workspace/CodexTest/docloop/.superloop/implement/prompt.md)
  - [`/.superloop/implement/verifier_prompt.md`](/workspace/CodexTest/docloop/.superloop/implement/verifier_prompt.md)
  - [`/.superloop/test/prompt.md`](/workspace/CodexTest/docloop/.superloop/test/prompt.md)
  - [`/.superloop/test/verifier_prompt.md`](/workspace/CodexTest/docloop/.superloop/test/verifier_prompt.md)

### `README.md`
- Update the Doc-Loop and Superloop sections to document:
  - canonical `<loop-control>` JSON output as the default
  - continued legacy `<question>` / final-line `<promise>` support for compatibility
  - multiple canonical blocks being invalid protocol output
  - malformed or double-signaled canonical control output causing a hard failure
  - unchanged verifier-only promise semantics and missing-promise default behavior

### `prompt_guideline.md`
- Update the control-tag guidance so the repository’s prompt-design documentation matches the new canonical `<loop-control>` default plus legacy-compatibility adapter behavior.
- Keep the guidance explicit that runtime changes and prompt-contract changes must stay synchronized.

## Test Plan

### New tests
- Add [`tests/test_loop_control.py`](/workspace/CodexTest/docloop/tests/test_loop_control.py).
- Add fixtures under [`tests/fixtures/loop_control/`](/workspace/CodexTest/docloop/tests/fixtures/loop_control/).

### Required fixture matrix
- Canonical promise `COMPLETE`
- Canonical promise `INCOMPLETE`
- Canonical question without `best_supposition`
- Canonical question with `best_supposition`
- Canonical block with leading prose
- Multiple canonical blocks in one stdout payload
- Canonical malformed JSON
- Canonical unknown schema ID
- Canonical invalid `kind`
- Canonical invalid promise enum
- Canonical plus legacy mixed control output that should raise
- Legacy question only
- Legacy multiline question body
- Legacy promise only on final line
- Legacy promise mentioned in prose but not on final line
- Legacy question plus final-line promise in the same stdout payload to preserve current dual-return behavior
- No control payload present

### Assertions
- Canonical fixtures normalize into structured `LoopControl` values with `source="canonical"`.
- Legacy fixtures normalize into structured `LoopControl` values with `source="legacy"`.
- The legacy question-plus-promise fixture returns both fields populated so the orchestrators can preserve question-first semantics.
- Missing-control fixtures return `source="none"` without raising.
- Multiple-canonical, malformed-canonical, and mixed canonical/legacy semantic-output fixtures raise `LoopControlParseError`.
- Existing git-tracking tests in [`tests/test_superloop_git_tracking.py`](/workspace/CodexTest/docloop/tests/test_superloop_git_tracking.py) still pass.

### Orchestrator semantics coverage
- Add targeted tests for the preserved branch-order and defaulting behavior in both orchestrators, preferably by extracting small decision helpers if that is the lowest-friction way to test them without spawning Codex subprocesses.

### Required orchestrator behavior matrix
- `docloop.py`: writer promise without question is fatal.
- `docloop.py`: legacy writer question plus final-line promise still takes the question branch instead of the fatal writer-promise path.
- `docloop.py`: missing verifier promise defaults to `INCOMPLETE` and appends the current warning to progress.
- `docloop.py`: verifier `COMPLETE` with unchecked criteria still hard-fails.
- `superloop.py`: producer promise without question is ignored.
- `superloop.py`: legacy producer question plus final-line promise still takes the question branch instead of the ignore-promise path.
- `superloop.py`: missing verifier promise appends the current warning to pair feedback and defaults to `INCOMPLETE`.
- `superloop.py`: verifier `COMPLETE` with unchecked criteria is downgraded to `INCOMPLETE`.

## Milestones

### Milestone 1: Shared parsing module
- Create `loop_control.py` with constants, dataclasses, canonical parser, legacy adapter, parse error type, and `criteria_all_checked()`.
- Keep the module focused on parsing and checklist validation only; do not add prompt-rendering helpers.

### Milestone 2: Orchestrator refactor
- Wire both orchestrators to `parse_loop_control()`.
- Remove duplicated parsing helpers and constants once imports are in place.
- Preserve existing branch ordering so legacy question-first behavior does not regress.

### Milestone 3: Prompt and docs migration
- Update embedded prompt templates in `docloop.py` and `superloop.py`.
- Update checked-in `.superloop` prompt files so the repo’s active prompts match the new default contract.
- Update `README.md` examples and behavioral descriptions.

### Milestone 4: Fixture-backed regression coverage
- Add parser fixtures and unit tests for canonical, legacy, malformed, missing, and mixed cases.
- Add focused tests for the preserved `docloop.py` and `superloop.py` call-site semantics that depend on question-first ordering, verifier defaulting, and unchecked-criteria handling.
- Run targeted tests for the new parser coverage, the orchestrator-semantics coverage, and the existing superloop git-tracking tests.

## Implementation Checklist
- [ ] Add `loop_control.py` with canonical schema constants, dataclasses, parser, adapter logic, parse error type, and `criteria_all_checked()`.
- [ ] Refactor `docloop.py` to consume the shared parser without changing non-canonical loop behavior.
- [ ] Refactor `superloop.py` to consume the shared parser without changing non-canonical pair behavior.
- [ ] Update `docloop.py` prompt constants to prefer canonical `<loop-control>` output.
- [ ] Update `superloop.py` prompt constants to prefer canonical `<loop-control>` output.
- [ ] Update checked-in `.superloop/*/prompt.md` and `.superloop/*/verifier_prompt.md` files to match the new contract.
- [ ] Update `README.md` documentation and examples.
- [ ] Update `prompt_guideline.md` so prompt-design guidance matches the new runtime contract.
- [ ] Add fixture-backed parser tests in `tests/test_loop_control.py`.
- [ ] Add focused orchestrator-semantics tests covering preserved branch-order/defaulting behavior in `docloop.py` and `superloop.py`.
- [ ] Verify the new parser tests and existing `tests/test_superloop_git_tracking.py` pass.

## Risk Register

### R-001: Legacy behavior regresses during deduplication
- Risk: centralizing parsing could accidentally remove current legacy quirks such as question-first precedence or missing-promise defaulting.
- Impact: hidden loop-flow regressions in both orchestrators.
- Mitigation: preserve legacy adapter behavior exactly, especially the legacy question-plus-promise return shape, and keep defaulting logic in the existing call sites.

### R-002: Prompt migration is incomplete because active checked-in prompts stay stale
- Risk: changing only in-code prompt templates leaves `.superloop/*/prompt.md` and verifier prompt files on the old contract.
- Impact: Superloop in this repository keeps emitting legacy tags despite the documented migration.
- Mitigation: update both template dictionaries in `superloop.py` and the checked-in prompt artifacts in `.superloop/`.

### R-003: Canonical and legacy double-signals create ambiguous orchestration
- Risk: an agent could emit canonical control plus legacy semantic tags in the same stdout.
- Impact: the orchestrator could choose the wrong branch or mask malformed agent output.
- Mitigation: treat canonical control as exclusive and raise `LoopControlParseError` when semantic mixed output is detected.

### R-004: Overly strict validation blocks safe forward evolution
- Risk: rejecting harmless unknown JSON fields would make small prompt/schema extensions unnecessarily breaking.
- Impact: future prompt tweaks would require runtime parser changes for no real benefit.
- Mitigation: validate required fields and enums only; ignore unknown top-level fields.

### R-005: Test coverage misses real stdout shapes
- Risk: parser tests may cover only minimal strings and miss multiline or prose-wrapped payloads.
- Impact: runtime failures despite green unit tests.
- Mitigation: use fixture files for realistic stdout payloads, including prose, multiline questions, malformed JSON, and mixed-format outputs.

### R-006: Shared parser refactor changes orchestrator branch semantics
- Risk: centralizing parsing without direct call-site regression tests could accidentally change question-first precedence, missing-promise defaults, or COMPLETE handling.
- Impact: green parser tests but broken loop behavior in live Doc-Loop or Superloop runs.
- Mitigation: add targeted `docloop.py` and `superloop.py` behavior tests that lock in the current branch ordering and defaulting semantics before or alongside the refactor.

## Rollout Notes
- This priority is a compatibility-preserving parser migration, not a flag day.
- Canonical `<loop-control>` JSON becomes the documented default immediately after merge.
- Legacy support remains until a later cleanup priority explicitly removes it.
