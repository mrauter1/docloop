# Remaining Deferrals Plan

## Scope

This planning pass covers only the roadmap items still deferred after the current repository baseline:

1. Additional first-party adapters:
   - Anthropic
   - Gemini
   - local OpenAI-compatible endpoints if they still fit cleanly after the Anthropic/Gemini work
2. Richer explicit pricing support:
   - a small first-party pricing catalog and helpers
   - no silent runtime price guessing
3. More publishable pack scaffolding:
   - stronger pack template and sample pack structure
   - better validation for package-shaped packs
   - no hosted registry or runtime plugin system

Out of scope for this run:

- any reimplementation of already-landed Release A/B/C or prior Phase 4/5 slices unless required for compatibility,
- new orchestration/runtime concepts,
- hosted services, registries, or plugin loading,
- multimodal expansion beyond what the existing message contract already supports.

## Baseline Summary

Relevant repository baseline already present:

- provider adapters for OpenAI Responses, Azure OpenAI Responses, and OpenRouter chat completions in `fuzzy/adapters.py`,
- `LLMOps.from_provider(...)` and provider-specific factory helpers in `fuzzy/ops.py`,
- runtime cost accounting primitives in `fuzzy/policy.py`,
- batch pricing integration in `fuzzy/batch.py`,
- initial in-repo pack scaffold plus validator in `domain_packs/*` and `fuzzy/packs.py`,
- portability and pack tests in `tests/test_portability.py` and `tests/test_packs.py`.

Observed remaining gaps from the baseline:

- no Anthropic adapter,
- no Gemini adapter,
- no explicit local OpenAI-compatible adapter entrypoint beyond manually overriding `OpenAIAdapter(base_url=...)`,
- pricing is caller-supplied only; there is no first-party inspectable catalog or helper API,
- pack validation only checks `compatibility.json`, eval suites, and `tests/`; it does not verify package metadata or publishable layout expectations,
- template/support pack scaffolding is too thin for a separately publishable package.

## Design Constraints

- Keep the narrow `LLMAdapter.complete(request) -> dict` contract unchanged.
- Preserve provider-neutral core behavior and local validation in `fuzzy/core.py`.
- Keep pricing explicit: catalog data must be opt-in and inspectable by callers, not fetched or inferred at runtime.
- Keep pack improvements focused on packaging metadata, layout, and validation. No dynamic plugin loading.
- Prefer adding provider-specific request builders and response parsers inside `fuzzy/adapters.py` rather than complicating core primitive logic.

## Milestones

### Milestone 1: Adapter Expansion

Goal:
Ship at least one additional first-party adapter, with Anthropic and Gemini planned as the coherent adapter slice, plus a clearer local-compatible OpenAI entrypoint if it can be done without duplicating the OpenAI adapter.

Implementation slice:

- Add `AnthropicAdapter` to `fuzzy/adapters.py`.
- Add `GeminiAdapter` to `fuzzy/adapters.py`.
- Add a small local-compatible adapter surface by either:
  - introducing `LocalOpenAIAdapter` as a thin alias/wrapper over `OpenAIAdapter`, or
  - adding `LLMOps.from_local_openai(...)` and `from_provider("local_openai", ...)` while reusing `OpenAIAdapter`.

Preferred interface definitions:

```python
class AnthropicAdapter(LLMAdapter):
    def __init__(
        self,
        *,
        api_key: str,
        model_api: str = "https://api.anthropic.com/v1/messages",
        anthropic_version: str = "2023-06-01",
        timeout: float = 60.0,
    ) -> None: ...

class GeminiAdapter(LLMAdapter):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta/models",
        timeout: float = 60.0,
    ) -> None: ...
```

Factory additions in `fuzzy/ops.py`:

```python
@classmethod
def from_anthropic(...): ...

@classmethod
def from_gemini(...): ...

@classmethod
def from_local_openai(...): ...
```

`from_provider(...)` additions:

- `"anthropic"`
- `"gemini"`
- `"local_openai"` if the local-compatible slice lands

Adapter contract details:

- Request input stays provider-neutral: `model`, `instructions`, `messages`, `output_schema`, `operation`.
- Each adapter must map provider responses back to:
  - `raw_text`
  - optional `provider_response_id`
  - optional `provider_metadata`
- Local validation remains authoritative even if provider-native schema enforcement is used.

Implementation notes:

- Anthropic should use a provider-native JSON/object response mode if supported cleanly, otherwise instruct JSON output and still rely on local validation.
- Gemini should prefer structured response schema support if the HTTP surface allows it without adding a dependency.
- Local OpenAI-compatible support should reuse the existing OpenAI request/response shape; do not create a second divergent protocol layer.

Tests:

- add adapter payload/response unit tests alongside current portability tests,
- add `LLMOps.from_provider(...)` coverage for each new provider,
- add failure-path tests for provider-contract parsing and auth/rate-limit classification where practical.

Definition of done:

- at least one new adapter is fully implemented with tests,
- if Anthropic and Gemini both land, local OpenAI-compatible support becomes a thin factory/wrapper instead of a separate protocol,
- no core primitive interface changes are required.

### Milestone 2: Explicit Pricing Catalog And Helpers

Goal:
Make pricing support more complete without hiding prices or introducing network lookups.

Implementation slice:

- Add a small first-party pricing module, likely `fuzzy/pricing.py`.
- Keep `ModelPricing` as the cost model input, but add helper APIs to make common usage explicit and inspectable.

Preferred interface definitions:

```python
@dataclass(frozen=True)
class PricingCatalog:
    entries: tuple[ModelPricing, ...]

def get_pricing_catalog(name: str = "default") -> PricingCatalog: ...
def list_pricing_models(name: str = "default") -> tuple[str, ...]: ...
def get_model_pricing(model: str, *, catalog: str = "default") -> ModelPricing | None: ...
def pricing_for_models(models: Sequence[str], *, catalog: str = "default") -> list[ModelPricing]: ...
```

Catalog content guidance:

- keep it intentionally small and first-party,
- include only models the repository already references in examples/tests or the new first-party adapter docs/tests,
- store catalog data in code or a checked-in JSON file under `fuzzy/`,
- include source/update comments or metadata so prices are inspectable and intentionally maintained,
- do not auto-select pricing unless the caller explicitly opts into catalog helpers.

Integration plan:

- preserve `run_batch(..., pricing=...)` and `LLMOps.run_batch(..., pricing=...)` unchanged,
- allow callers to pass `pricing=pricing_for_models([...])` or `pricing=[get_model_pricing(...)]` style results,
- optionally add a convenience helper for merging explicit overrides with catalog defaults if it stays simple.

Non-goals for pricing:

- no runtime HTTP fetches,
- no silent fallback to guessed pricing when a model is missing,
- no new budget semantics beyond the existing `RuntimeBudget` and `RuntimeCost`.

Tests:

- catalog lookup returns stable `ModelPricing` entries,
- unknown models return `None` or a clear lookup failure depending on helper,
- batch runtime cost integration continues to use only explicitly supplied `ModelPricing`,
- catalog helpers remain deterministic and local-only.

Definition of done:

- repository contains a small inspectable first-party pricing catalog,
- callers have a simple explicit path to use catalog pricing with existing runtime cost accounting,
- no code path estimates cost without an explicit `ModelPricing`.

### Milestone 3: Publishable Pack Scaffolding

Goal:
Make the template and sample support pack closer to separately publishable Python packages while keeping validation local and static.

Implementation slice:

- Expand `domain_packs/template/` into a real package skeleton.
- Bring `domain_packs/support/` closer to the same structure.
- Tighten `fuzzy/packs.py` validation to check publishable-pack expectations.

Preferred pack structure:

- `pyproject.toml`
- package module directory such as `src/fuzzy_support/` or package-at-root if the repository chooses not to use `src/`
- `README.md`
- `compatibility.json`
- `evals/...`
- `tests/...`

Preferred validator extensions:

`validate_pack_directory(...)` should additionally verify:

- `pyproject.toml` exists,
- package metadata name/version/requires-python exist in a minimally valid form,
- compatibility metadata name matches the project/package naming convention where practical,
- exported module paths declared in `compatibility.json` are syntactically valid and correspond to importable file locations within the pack directory,
- sample pack layout remains static and publishable without inventing an installation/runtime plugin layer.

Possible return-shape extension:

If needed, extend `PackValidationResult` with optional metadata paths rather than changing behavior radically:

```python
@dataclass(frozen=True)
class PackValidationResult:
    pack_name: str
    compatibility_path: Path
    pyproject_path: Path
    eval_suite_paths: tuple[Path, ...]
    export_paths: tuple[Path, ...]
```

Implementation notes:

- prefer stdlib parsing if available for `pyproject.toml`; otherwise keep validation minimal and text-based rather than adding heavy dependencies,
- do not validate built distributions or run packaging commands in the library layer,
- add just enough structure to support a future externalized pack without implying plugin discovery.

Tests:

- existing pack fixture still validates,
- missing `pyproject.toml` fails clearly,
- missing exported module file fails clearly,
- template and support pack both satisfy the stronger validator.

Definition of done:

- template pack is visibly closer to a standalone publishable package,
- support pack mirrors the stronger structure,
- validator enforces the new minimum bar.

## Sequencing

Recommended implementation order:

1. Adapter slice first.
   Reason: adapter work is the highest-value acceptance criterion and most likely to introduce compatibility issues.
2. Pricing catalog second.
   Reason: it is isolated, low-risk, and should align with whichever new provider model names land.
3. Pack scaffolding third.
   Reason: it is mostly static/repo-shape work and can consume the final naming/version assumptions cleanly.

## Interface And Compatibility Notes

- No changes are planned to primitive signatures in `fuzzy/core.py`.
- No changes are planned to `LLMAdapter.complete(...)`.
- `fuzzy/__init__.py` should export any new adapters and any new pricing helpers intended as public API.
- `LLMOps.from_provider(...)` must continue to fail with `FrameworkError(category="invalid_configuration")` for unknown providers.
- Existing batch cost accounting in `fuzzy/batch.py` and `fuzzy/policy.py` should remain the only place runtime costs are accumulated.

## Risk Register

### Risk 1: Provider API differences force core leakage

Risk:
Anthropic/Gemini may not align cleanly with the existing request shape, especially around schema enforcement and multimodal content encoding.

Control:

- keep provider-specific transformation inside adapters only,
- if a provider cannot strictly enforce schema server-side, rely on prompt instructions plus local validation instead of changing core semantics,
- constrain the first implementation to current `text` and `json` message parts.

### Risk 2: Local-compatible OpenAI support duplicates existing OpenAI adapter behavior

Risk:
Creating a new adapter class may just duplicate `OpenAIAdapter(base_url=...)`.

Control:

- prefer a factory/helper wrapper over a distinct transport implementation,
- only introduce a separate class if it materially clarifies public usage and stays a thin wrapper.

### Risk 3: Pricing catalog becomes stale or misleading

Risk:
Bundled prices can drift over time.

Control:

- keep the catalog explicitly small,
- document/update-source metadata in code or adjacent docs,
- never auto-apply catalog prices without caller opt-in,
- return `None` or require explicit selection for unknown models rather than guessing.

### Risk 4: Pack validation becomes too strict for the current sample packs

Risk:
New validator rules could fail the repository’s own scaffolds or require unnecessary packaging complexity.

Control:

- define a narrow minimum publishable bar,
- keep validation focused on files and metadata already expected in a simple Python package,
- update template/support pack in the same slice as validator changes.

### Risk 5: Dirty worktree overlap

Risk:
Many relevant files are already modified or newly added in the worktree.

Control:

- treat current contents as baseline rather than attempting cleanup,
- limit edits to files directly tied to remaining deferrals,
- avoid rewriting previously landed slices unless compatibility requires it.

## Verification Plan

- run targeted tests for portability/provider factories, batch pricing, and pack validation,
- add new provider-specific unit tests for request mapping and response parsing,
- run the smallest coherent pytest subset first, then broader relevant suites if the new slices stabilize,
- explicitly document any remaining deferred items only if there is a concrete technical blocker.

## Expected Outcome For The Implement Phase

The implement phase should aim to land:

- Anthropic adapter,
- Gemini adapter if feasible within the same narrow adapter surface,
- a thin local OpenAI-compatible factory/wrapper if still coherent,
- first-party explicit pricing catalog helpers,
- stronger package-shaped pack scaffolding and validator coverage.

If one of Anthropic, Gemini, or local-compatible support proves concretely blocked by HTTP contract or repository constraints, the implement phase must still land at least one additional first-party adapter and record the blocker explicitly.
