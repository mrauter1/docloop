# Remaining Roadmap Retry Test Strategy

## Scope

This test pass covers the request-relevant roadmap slices currently implemented in the repository:
- the new `assess_document_completeness(...)` flagship recipe
- its export and eval fixture wiring
- the new worker/queue-style example integration
- the new Phase 4 batch execution surface in `fuzzy.batch` and `LLMOps.run_batch(...)`
- regression safety for adjacent existing recipe, trace, eval, and primitive behavior

## Behavior-To-Test Coverage Map

### New document-completeness recipe

- Happy path, message evidence, and recipe trace bundling:
  - `tests/test_recipes.py::test_document_completeness_supports_message_evidence_and_recipe_traces`
- Happy path, structured context/dataclass input:
  - `tests/test_recipes.py::test_document_completeness_supports_structured_context`
- Failure path, extraction failure stops before dispatch:
  - `tests/test_recipes.py::test_document_completeness_stops_before_dispatch_when_extraction_fails`
- Edge/preflight path, package required when `messages` are absent:
  - `tests/test_recipes.py::test_document_completeness_requires_package_when_messages_are_not_supplied`

### Eval fixture/export coverage

- Document-completeness fixture runs against the exported schema alongside the existing recipe suites:
  - `tests/test_recipes.py::test_recipe_eval_fixtures_run_against_exported_schemas`

### Worker/queue reference integration

- Mixed text + JSON message evidence path through the queue example:
  - `tests/test_recipes.py::test_queue_document_worker_processes_mixed_evidence_job`

### Phase 4 batch execution

- Happy path, concurrent execution, ordered results, and optional trace collection:
  - `tests/test_batch.py::test_run_batch_collects_results_in_input_order_and_traces`
- Failure path, per-call runtime validation failure is isolated while sibling calls still succeed:
  - `tests/test_batch.py::test_run_batch_keeps_per_call_failures_without_stopping`
- Edge path, `stop_on_error=True` skips later queued calls before provider execution:
  - `tests/test_batch.py::test_run_batch_stop_on_error_marks_later_calls_as_skipped`
- Happy path, `LLMOps.run_batch(...)` uses instance defaults:
  - `tests/test_batch.py::test_llmops_run_batch_uses_instance_defaults`
- Failure/preflight path, invalid per-call configuration is reported without invoking the provider for that call:
  - `tests/test_batch.py::test_run_batch_reports_preflight_call_configuration_errors_without_hitting_provider`
- Edge path, per-call model override works without a batch-level default model:
  - `tests/test_batch.py::test_run_batch_accepts_per_call_model_when_batch_default_is_absent`
- Failure/preflight path, invalid batch concurrency is rejected before any execution:
  - `tests/test_batch.py::test_run_batch_rejects_invalid_concurrency_before_execution`

### Adjacent regression checks retained in touched files

- Support triage trace/result path:
  - `tests/test_recipes.py::test_support_triage_returns_typed_decision_and_recipe_traces`
- Lead qualification message-evidence preservation:
  - `tests/test_recipes.py::test_lead_qualification_supports_message_evidence`
- Approval routing happy path and dispatch evidence propagation:
  - `tests/test_recipes.py::test_approval_router_bundles_manual_review_path`
  - `tests/test_recipes.py::test_approval_router_preserves_structured_context_in_dispatch_step`
- Existing support-triage failure guard:
  - `tests/test_recipes.py::test_support_triage_stops_before_dispatch_when_extraction_fails`

## Determinism / Flake Controls

- All tests use a local `FakeAdapter`; no network calls or live provider SDKs are involved.
- Batch assertions rely on fixed responses and request-payload inspection, so ordering remains deterministic even when calls finish out of order.
- One batch test uses a short local `asyncio.sleep(...)` inside the fake adapter only to force completion-order inversion; the report assertion keys off preserved input order rather than timing thresholds.
- No wall-clock assertions, random inputs, or filesystem race conditions are used.
- The queue example test exercises a plain async function rather than a real worker runtime, avoiding process and scheduling flake.

## Verification Commands

- `pytest -q tests/test_batch.py`
- `pytest -q tests/test_recipes.py`
- `pytest -q tests/test_batch.py tests/test_fuzzy.py tests/test_trace.py tests/test_evals.py tests/test_recipes.py`
