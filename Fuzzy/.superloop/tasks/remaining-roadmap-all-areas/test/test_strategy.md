# Test Strategy

## Scope

This test pass covers the remaining roadmap implementation areas shipped in the implementation loop:
- fallback model policies
- approval / audit / simulator / timeout command controls
- runtime cost controls and batch follow-through
- Azure OpenAI adapter wiring
- optional domain-pack validation scaffolding

## Behavior-to-test coverage map

### Fallback model policies

- Happy path:
  - [`tests/test_portability.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_portability.py) `test_eval_bool_uses_fallback_model_on_provider_error_and_records_attempt_models`
  - Verifies provider-side failure triggers fallback and trace attempts record the model sequence.
- Edge case:
  - [`tests/test_portability.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_portability.py) `test_eval_bool_does_not_use_fallback_model_for_validation_retries`
  - Verifies malformed JSON retries stay on the original model and do not fall through to fallback.
- Failure-path intent:
  - Existing provider error coverage remains in [`tests/test_fuzzy.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_fuzzy.py) for category mapping.

### Dispatch execution controls

- Command allow-list / deny-list gating:
  - [`tests/test_portability.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_portability.py) `test_dispatch_allow_list_rejects_blocked_command_before_approval_or_execution`
  - [`tests/test_portability.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_portability.py) `test_dispatch_deny_list_rejects_command_before_execution`
  - Verifies blocked commands fail before approval/execution and surface the expected policy boundary.
- Simulator mode:
  - [`tests/test_portability.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_portability.py) `test_dispatch_simulator_mode_skips_executor_and_emits_audit_record`
  - Verifies no side effect, canonical dispatch execution shape, and audit emission.
- Approval rejection:
  - [`tests/test_portability.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_portability.py) `test_dispatch_denied_by_approval_hook_raises_and_audits`
  - Verifies failure category/message and audit record shape.
- Async timeout path:
  - [`tests/test_portability.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_portability.py) `test_dispatch_timeout_raises_command_execution`
  - [`tests/test_portability.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_portability.py) `test_dispatch_async_timeout_cancels_executor_before_side_effect`
  - Verifies timeout failure plus cancellation before side effects.
- Sync timeout rejection:
  - [`tests/test_portability.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_portability.py) `test_dispatch_rejects_timeout_for_sync_executor_before_execution`
  - Verifies fail-fast rejection and zero side effects.
- No-timeout sync execution compatibility:
  - [`tests/test_portability.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_portability.py) `test_dispatch_sync_executor_stays_on_current_thread_without_timeout`
  - Verifies the pre-existing in-thread execution behavior is preserved.

### Batch runtime cost controls and follow-through

- Budget exhaustion:
  - [`tests/test_portability.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_portability.py) `test_run_batch_reports_cost_and_stops_after_budget_exhaustion`
  - Verifies request-count budget exhaustion, skipped later calls, and deterministic cost totals.
- Trace exposure contract:
  - [`tests/test_batch.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_batch.py) `test_run_batch_does_not_expose_success_traces_when_return_traces_is_false`
  - Verifies internal trace collection does not leak through the public batch result surface.
- Existing batch regressions:
  - Ordering, stop-on-error, per-call configuration, and failure capture remain covered in [`tests/test_batch.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_batch.py).

### Azure OpenAI adapter support

- Adapter request/response wiring:
  - [`tests/test_portability.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_portability.py) `test_azure_openai_adapter_builds_response_payload_without_sdk_calls`
  - Verifies payload assembly and metadata extraction without live network calls.
- Factory wiring:
  - [`tests/test_portability.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_portability.py) `test_llmops_from_provider_supports_azure_openai`
  - Verifies `from_provider("azure_openai", ...)` returns the new adapter path.

### Optional domain-pack scaffolding and contribution standards

- Happy path:
  - [`tests/test_packs.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_packs.py) `test_validate_pack_directory_accepts_sample_support_pack`
  - Verifies compatibility metadata and eval suite discovery for the sample support pack.
- Failure path:
  - [`tests/test_packs.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_packs.py) `test_validate_pack_directory_rejects_missing_eval_suite`
  - Verifies incomplete contribution scaffolding fails validation deterministically.

## Flake risks and stabilization

- Async timeout tests use `asyncio.sleep(0.05)` with `timeout_seconds=0.01`.
- Stabilization:
  - no network calls
  - no wall-clock assertions beyond clear timeout separation
  - cancellation is asserted via in-memory state, not timing races
- Batch tests use deterministic fake adapters and `concurrency=1` where budget/stop conditions matter.

## Suggested verification command

```bash
python3 -m pytest -q
```
