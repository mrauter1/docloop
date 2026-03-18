# Implementation Notes

## Files changed

- `fuzzy/adapters.py`
- `fuzzy/ops.py`
- `fuzzy/__init__.py`
- `fuzzy/pricing.py`
- `fuzzy/packs.py`
- `tests/test_fuzzy.py`
- `tests/test_portability.py`
- `tests/test_packs.py`
- `domain_packs/support/pyproject.toml`
- `domain_packs/support/README.md`
- `domain_packs/support/src/fuzzy_support/__init__.py`
- `domain_packs/support/src/fuzzy_support/recipes.py`
- `domain_packs/template/README.md`

## Checklist mapping

- Milestone 1 adapter expansion:
  - landed `AnthropicAdapter`
  - landed `GeminiAdapter`
  - landed `LocalOpenAIAdapter`
  - added `LLMOps.from_anthropic(...)`, `from_gemini(...)`, `from_local_openai(...)`
  - added `from_provider(...)` support for `anthropic`, `gemini`, and `local_openai`
  - added adapter payload/response tests and factory coverage
- Milestone 2 explicit pricing catalog and helpers:
  - added `fuzzy/pricing.py`
  - added `PricingCatalog`, `get_pricing_catalog`, `list_pricing_models`, `find_model_pricing`, `get_model_pricing`, and `pricing_for_models`
  - resolved plan feedback `PLAN-001` by making `get_model_pricing(...)` and `pricing_for_models(...)` strict on unknown models instead of returning `None` into runtime pricing lists
- Milestone 3 publishable pack scaffolding:
  - extended `PackValidationResult` with `pyproject_path` and `export_paths`
  - strengthened `validate_pack_directory(...)` to require `pyproject.toml`, verify minimal project metadata, and resolve exported module paths
  - broadened the minimal `pyproject.toml` parser to accept both single-quoted and double-quoted string values with trailing comments
  - added `domain_packs/support/pyproject.toml`
  - added `domain_packs/support/src/fuzzy_support/recipes.py` and exported it from `__init__.py`
  - updated pack tests for stronger validation expectations

## Assumptions

- Local OpenAI-compatible support should stay aligned with the existing Responses-style adapter contract, not add a second chat-completions-specific runtime path.
- Anthropic and Gemini adapters should preserve the narrow `LLMAdapter.complete(...)` contract even when provider-native structured output differs; local validation remains authoritative.
- The checked-in pricing catalog is intentionally small and explicit. It is not an exhaustive or auto-refreshed pricing source.
- Minimal `pyproject.toml` validation is sufficient for this slice; full TOML dependency or packaging-build validation would be unnecessary scope expansion.

## Expected side effects

- Public API now exposes additional first-party adapters and pricing helpers via `fuzzy.__init__`.
- Existing `from fuzzy import drop` imports continue to work.
- `validate_pack_directory(...)` is stricter and now rejects pack directories missing `pyproject.toml` or missing exported modules.
- Local cost accounting remains explicit: runtime cost estimation only happens when callers pass concrete `ModelPricing` entries, including ones obtained from the new helpers.

## Deduplication / centralization decisions

- Centralized message rendering and schema-instruction assembly in `fuzzy/adapters.py` so Anthropic, Gemini, OpenRouter, and OpenAI-compatible transports reuse the same text/json-to-provider transformation patterns.
- Kept pricing helpers separate in `fuzzy/pricing.py` rather than expanding `fuzzy/policy.py`, because the existing policy module is runtime-accounting focused while the new module is catalog/discovery focused.

## Verification

- `pytest tests/test_fuzzy.py tests/test_portability.py tests/test_packs.py`
- `python3 -m compileall fuzzy tests domain_packs/support/src domain_packs/template/src`
- reviewer follow-up regression checks passed after restoring the public `drop` export and widening accepted `pyproject.toml` string syntax

## Intentionally deferred

- No chat-completions-specific local OpenAI adapter path was added. The implemented local support is deliberately scoped to OpenAI-compatible Responses-style endpoints to stay coherent with the existing adapter contract.
