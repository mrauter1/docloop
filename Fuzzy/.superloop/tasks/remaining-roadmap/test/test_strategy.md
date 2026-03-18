# test_strategy.md

## Scope

Focused on the new `fuzzy.recipes` slice and the cycle-2 fix that preserves original caller evidence across multi-step recipe execution.

## Behavior-To-Test Coverage Map

- Recipe happy path with trace bundling
  - Coverage: `tests/test_recipes.py::test_support_triage_returns_typed_decision_and_recipe_traces`
  - Verifies typed recipe output and per-step trace capture for a normal two-step support triage flow.

- Message-mode evidence propagation into the second recipe step
  - Coverage: `tests/test_recipes.py::test_lead_qualification_supports_message_evidence`
  - Verifies the first dispatch request still contains the original ordered messages, appends the extracted qualification summary as additional JSON evidence, and does not mutate the caller-supplied message list.

- Structured-context propagation into the second recipe step
  - Coverage: `tests/test_recipes.py::test_approval_router_preserves_structured_context_in_dispatch_step`
  - Verifies context-mode recipes preserve the original structured request and merge the extracted assessment into the dispatch step payload.

- Failure path: recipe stops after extraction failure
  - Coverage: `tests/test_recipes.py::test_support_triage_stops_before_dispatch_when_extraction_fails`
  - Verifies a validation-exhausted extraction error aborts the recipe before a second model call is attempted.

- Recipe eval fixture compatibility
  - Coverage: `tests/test_recipes.py::test_recipe_eval_fixtures_run_against_exported_schemas`
  - Verifies bundled recipe eval suites still execute successfully against the exported schemas.

- Existing broader regression surface
  - Coverage: full `pytest -q`
  - Confirms recipe additions did not break trace, eval, primitive, or adapter behavior elsewhere in the repository.

## Determinism / Flake Risk

- All tests use the local `FakeAdapter`; no network or real provider calls are involved.
- Assertions are based on exact in-memory request payloads and fixed fake responses, so ordering is deterministic.
- No time-based logic, random data, or filesystem race paths were introduced.
