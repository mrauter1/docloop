# Test Strategy

## Scope

This test pass covers the remaining-deferrals implementation slice only:

- additional first-party adapters and provider factories,
- explicit pricing catalog/helpers,
- publishable pack validation and scaffolding checks,
- the restored public `drop` export that was briefly regressed during the implementation pass.

## Behavior-to-test coverage map

### Adapter expansion

- OpenAI/Azure/OpenRouter adapter request shaping:
  - covered by `tests/test_fuzzy.py::test_openai_adapter_builds_payload_from_ordered_messages`
  - covered by `tests/test_fuzzy.py::test_openrouter_adapter_builds_payload_from_ordered_messages`
  - covered by `tests/test_portability.py::test_azure_openai_adapter_builds_response_payload_without_sdk_calls`
- Anthropic adapter happy path:
  - covered by `tests/test_fuzzy.py::test_anthropic_adapter_builds_payload_from_ordered_messages`
- Anthropic adapter provider-contract failure:
  - covered by `tests/test_fuzzy.py::test_anthropic_adapter_malformed_nested_output_maps_to_provider_contract`
- Gemini adapter happy path:
  - covered by `tests/test_fuzzy.py::test_gemini_adapter_builds_payload_from_ordered_messages`
- Gemini adapter provider-contract failure:
  - covered by `tests/test_fuzzy.py::test_gemini_adapter_malformed_nested_output_maps_to_provider_contract`
- Local OpenAI-compatible adapter header behavior:
  - covered by `tests/test_portability.py::test_local_openai_adapter_omits_authorization_header_when_api_key_is_missing`
  - covered by `tests/test_portability.py::test_local_openai_adapter_includes_authorization_header_when_api_key_is_set`
- Provider factory wiring:
  - covered by `tests/test_portability.py::test_llmops_from_provider_supports_azure_openai`
  - covered by `tests/test_portability.py::test_llmops_from_provider_supports_anthropic`
  - covered by `tests/test_portability.py::test_llmops_from_provider_supports_gemini`
  - covered by `tests/test_portability.py::test_llmops_from_provider_supports_local_openai_without_api_key`

### Pricing helpers

- Catalog happy path and strict lookup behavior:
  - covered by `tests/test_portability.py::test_pricing_catalog_helpers_are_explicit_and_strict`
- Unknown-model optional lookup path:
  - covered by `tests/test_portability.py::test_pricing_catalog_helpers_are_explicit_and_strict`
- Existing runtime cost integration:
  - covered by `tests/test_portability.py::test_run_batch_reports_cost_and_stops_after_budget_exhaustion`

### Pack validation and publishable scaffolding

- Sample support pack happy path:
  - covered by `tests/test_packs.py::test_validate_pack_directory_accepts_sample_support_pack`
- Missing eval suite failure:
  - covered by `tests/test_packs.py::test_validate_pack_directory_rejects_missing_eval_suite`
- Missing `pyproject.toml` failure:
  - covered by `tests/test_packs.py::test_validate_pack_directory_rejects_missing_pyproject`
- Missing export module failure:
  - covered by `tests/test_packs.py::test_validate_pack_directory_rejects_missing_export_module`
- Single-quoted `pyproject.toml` values with trailing comments:
  - covered by `tests/test_packs.py::test_validate_pack_directory_accepts_single_quoted_pyproject_values`
- `compatibility.json` name / `project.name` mismatch:
  - covered by `tests/test_packs.py::test_validate_pack_directory_rejects_name_mismatch_between_pyproject_and_compatibility`

### Public export compatibility

- Root-package `drop` export remained available:
  - covered by `tests/test_portability.py::test_drop_remains_publicly_exported`

## Determinism and flake control

- No network calls are made. Adapter transport tests monkeypatch `urllib.request.urlopen` or adapter post methods and assert on captured payloads/headers.
- No timing-sensitive sleeps were added in this test pass.
- Pack validation tests use `tmp_path` fixtures and checked-in sample packs only.
- Assertions avoid provider-generated ordering assumptions except where the implementation explicitly preserves order.

## Verification command set

- `pytest tests/test_fuzzy.py tests/test_portability.py tests/test_packs.py`
- `python3 -m compileall tests`
