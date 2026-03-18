# Test Strategy

## Scope
Validate the Release A input-contract pivot only:
- exactly one of `context` or `messages`,
- provider-neutral `Message` handling with `text` and `json` parts,
- adapter request migration from `context_json` to ordered `messages`,
- unchanged retry, provider-error, extraction, and dispatch behavior that remains in scope,
- public-surface cleanup around `drop`.

## Behavior-To-Test Coverage Map

### 1. `context` shorthand still works
- Covered by `test_eval_bool_retries_malformed_json_then_succeeds`.
- Covered by `test_eval_bool_accepts_explicit_none_context_as_json_null`.
- Coverage intent:
  - happy path for standard JSON object context,
  - edge case for explicit `None` context so the sentinel-based exactly-one-of implementation remains correct,
  - regression assertion that adapter requests now use `messages` and no longer expose `context_json`.

### 2. `messages` advanced input surface works and preserves order
- Covered by `test_eval_bool_accepts_messages_and_preserves_order`.
- Covered by `test_llmops_accepts_messages`.
- Coverage intent:
  - happy path for direct primitive usage with mixed `text` and `json` parts,
  - wrapper path coverage for `LLMOps`,
  - role ordering preserved into adapter requests.

### 3. Exactly-one-of evidence contract is enforced before provider calls
- Covered by `test_eval_bool_rejects_both_context_and_messages_before_provider_call`.
- Covered by `test_eval_bool_rejects_missing_context_and_messages_before_provider_call`.
- Coverage intent:
  - failure path for both-present evidence,
  - failure path for both-missing evidence,
  - zero provider attempts on preflight failures.

### 4. Unsupported message shapes fail clearly before provider calls
- Covered by `test_eval_bool_rejects_invalid_message_role_before_provider_call`.
- Covered by `test_eval_bool_rejects_invalid_message_part_type_before_provider_call`.
- Covered by `test_eval_bool_rejects_non_json_message_data_before_provider_call`.
- Covered by `test_eval_bool_rejects_unexpected_message_fields_before_provider_call`.
- Covered by `test_eval_bool_rejects_unexpected_message_part_fields_before_provider_call`.
- Coverage intent:
  - invalid role failure path,
  - unsupported part type failure path,
  - non-JSON-compatible `json` part failure path,
  - unexpected message-level and part-level field rejection so no hidden normalization layer reappears.

### 5. Adapter boundary consumes ordered `messages`
- Covered by `test_openai_adapter_builds_payload_from_ordered_messages`.
- Covered by `test_openrouter_adapter_builds_payload_from_ordered_messages`.
- Coverage intent:
  - framework instructions remain separate from caller evidence,
  - ordered message roles are preserved,
  - `json` parts are serialized deterministically at transport time.

### 6. Existing in-scope behavior remains stable
- Retry and validation exhaustion:
  - `test_eval_bool_retries_malformed_json_then_succeeds`
  - `test_classify_exhausts_choice_validation`
- Extraction:
  - `test_extract_returns_model_instance`
  - existing schema validation tests in `tests/test_fuzzy.py`
- Dispatch:
  - existing command validation, execution, and label-mode tests in `tests/test_fuzzy.py`
- Provider error mapping:
  - existing adapter/provider contract tests in `tests/test_fuzzy.py`
- Public surface cleanup:
  - import path change in `tests/test_fuzzy.py` ensures `drop` is no longer consumed from top-level `fuzzy`.

## Determinism / Flake Risk
- Tests use `FakeAdapter` and patched adapter methods; no live network calls occur.
- Message-order assertions compare exact in-memory request payloads.
- JSON serialization assertions rely on `deterministic_json_dumps()` semantics already used in production code.
- No timing-based assertions or randomized inputs are used.

## Verification Commands
- `python3 -m compileall fuzzy tests`
- `pytest -q`
