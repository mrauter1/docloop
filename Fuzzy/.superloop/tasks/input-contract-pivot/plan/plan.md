# Input Contract Pivot Plan

## Scope
Implement Release A only:
- move the public evidence contract to `system_prompt` plus exactly one of `context` or `messages`,
- add provider-neutral message types with `text` and `json` parts,
- refactor adapters to consume ordered messages instead of public `context_json`,
- preserve typed outputs, local validation, and bounded retries,
- update tests and docs to match the new contract.

Out of scope:
- traces/evals,
- command/schema ergonomics beyond what the input pivot strictly needs,
- multimodal runtime support,
- new adapters,
- agentic/workflow features.

## Current State Summary
- All four primitives and `LLMOps` methods currently require `context` and do not accept `messages`.
- Core request assembly serializes `context` into a single `context_json` string and gives that to adapters.
- Adapters build provider payloads from `instructions` plus one user text blob, so ordered caller evidence is not representable.
- `drop` is currently re-exported from `fuzzy.__init__`, which conflicts with the new public direction.
- Tests cover retries, schema validation, dispatch behavior, and provider error mapping, but not the new evidence contract.

## Target Release A Contract

### Public primitive signatures
All async primitives become:

```python
async def eval_bool(
    *,
    adapter: LLMAdapter,
    model: str,
    expression: str,
    context: Any | None = None,
    messages: Sequence[Message] | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    system_prompt: str | None = None,
) -> bool: ...
```

`classify`, `extract`, and `dispatch` follow the same evidence pattern.

Rules:
- exactly one of `context` or `messages` is required,
- `context` remains the simple shorthand and stays backward compatible for existing callers,
- `messages` becomes the advanced ordered evidence surface,
- `system_prompt` remains separate and optional,
- invalid evidence combinations fail with `FrameworkError(category="invalid_configuration", attempt_count=0)`.

### `LLMOps` methods
Mirror the primitive contract:
- accept `context: Any | None = None`,
- accept `messages: Sequence[Message] | None = None`,
- preserve default override behavior for `model`, `max_attempts`, and `system_prompt`,
- preserve sync wrappers unchanged except for the new evidence parameters flowing through.

### Provider-neutral message model
Add canonical public types in `fuzzy.types`:

```python
MessageRole = Literal["user", "assistant"]
TextPart = TypedDict("TextPart", {"type": Literal["text"], "text": str})
JsonPart = TypedDict("JsonPart", {"type": Literal["json"], "data": Any})
MessagePart = TextPart | JsonPart
Message = TypedDict("Message", {"role": MessageRole, "parts": list[MessagePart]})
```

Implementation rules:
- only `user` and `assistant` roles are accepted,
- only `text` and `json` part types are accepted in Release A,
- `json` part data must be JSON-compatible,
- unsupported role/part shapes fail before provider calls,
- `context` is internally expanded into one provider-neutral `user` message containing one `json` part with the original context value,
- context expansion is internal only; public callers still choose between `context` and `messages`.

### Adapter request contract
Refactor the internal adapter request to:

```python
AdapterRequest = {
    "operation": str,
    "model": str,
    "instructions": str,
    "messages": list[Message],
    "output_schema": dict[str, Any],
    "attempt": int,
}
```

Rules:
- remove `context_json` from the core-to-adapter primary path,
- adapters receive ordered evidence messages after local validation/canonicalization,
- adapters remain responsible only for provider transport formatting,
- local output parsing and validation stay in core.

### Provider transport mapping
Implement minimal provider mapping for Release A:
- `system_prompt` stays embedded in framework-owned `instructions`, not in caller messages.
- `text` parts map to provider text content.
- `json` parts map losslessly as JSON text in provider payloads, with a stable serialization helper shared by adapters.
- caller message ordering is preserved.
- assistant messages are forwarded as assistant-role history where the provider supports it.

This is sufficient for Release A because the public contract is message-oriented even if providers still receive text-encoded JSON for `json` parts.

## Milestones

### Milestone 1: Evidence model and preflight validation
- Add public `Message` and `MessagePart` types in `fuzzy.types`.
- Add core validation helpers for:
  - exactly-one-of `context`/`messages`,
  - message list shape,
  - role validation,
  - part validation,
  - JSON-compatibility checks for `context` and `json` parts.
- Replace `_serialize_context(...)` with a canonical evidence-normalization helper that returns validated provider-neutral messages.

Exit condition:
- all primitives can obtain a validated `messages` list before building an adapter request,
- invalid evidence fails before any adapter call.

### Milestone 2: Primitive and wrapper signature migration
- Update `eval_bool`, `classify`, `extract`, and `dispatch` to accept optional `context` and `messages`.
- Update `_run_model_operation(...)` to consume normalized messages instead of `context_json`.
- Update `LLMOps` async and sync methods to mirror the new evidence contract.

Exit condition:
- existing `context=` callers still work,
- new `messages=` callers are supported across direct primitives and wrapper methods,
- both/both-missing evidence cases are rejected consistently.

### Milestone 3: Adapter boundary refactor
- Change `LLMAdapter.complete()` request expectations from `context_json` to `messages`.
- Update `OpenAIAdapter` and `OpenRouterAdapter` payload builders to:
  - keep framework instructions separate,
  - preserve caller message ordering and roles,
  - encode `json` parts deterministically.
- Keep provider response parsing and error mapping behavior unchanged.

Exit condition:
- adapters consume the normalized request shape from the SAD,
- no public API still depends on `context_json`.

### Milestone 4: Public surface cleanup
- Stop exporting `drop` from `fuzzy.__init__`.
- Keep the function internal for now if it still helps implementation or compatibility work, but remove it from the first-class documented surface.
- Do not introduce `to_json` or any equivalent public primitive.

Exit condition:
- top-level public exports align with the requested semantic core.

### Milestone 5: Tests and docs
- Update tests to cover:
  - `context` success path remains supported,
  - `messages` success path for all primitives or representative primitive plus wrapper coverage,
  - both `context` and `messages` rejected,
  - neither `context` nor `messages` rejected,
  - invalid role rejected,
  - invalid part type rejected,
  - non-JSON-compatible `json` part rejected,
  - adapter requests contain ordered normalized messages,
  - retries/provider errors/typed extraction/dispatch behaviors still hold after refactor.
- Update roadmap-adjacent docs or package docs/examples that still describe `context_json` or `drop` as public direction.

Exit condition:
- docs and tests describe one coherent Release A contract.

## Implementation Notes

### Suggested file touch list
- `fuzzy/types.py`
- `fuzzy/core.py`
- `fuzzy/ops.py`
- `fuzzy/adapters.py`
- `fuzzy/__init__.py`
- `tests/test_fuzzy.py`
- docs/examples only where they contradict the Release A contract

### Keep/reuse decisions
- Keep existing `FrameworkError`, `ProviderError`, and `SchemaValidationError` contracts.
- Keep existing retry loop and repair messaging structure.
- Keep existing schema/model-type handling for `extract` and `dispatch`.
- Reuse `deterministic_json_dumps()` for JSON part serialization to avoid divergent adapter formatting.

### Deliberate non-work
- Do not add multimodal part transport yet.
- Do not add new trace objects or telemetry schemas in this run.
- Do not redesign dispatch result types or command ergonomics beyond evidence input changes.
- Do not add hidden coercion for arbitrary Python objects in messages or context.

## Regression Risks And Controls

### Risk R1: Breaking existing `context` callers
- Risk: signature refactor accidentally makes `context` non-optional in some places or changes semantics.
- Control: keep `context` supported everywhere, add representative regression tests for direct primitives and `LLMOps`.
- Rollback: adapter/core changes are isolated enough to revert to context-only request building if needed.

### Risk R2: Evidence validation drift between primitives
- Risk: each primitive validates `context`/`messages` differently.
- Control: one shared normalization helper in `core.py`; primitives only consume its result.

### Risk R3: Adapter/provider payload mismatch
- Risk: provider payload assembly for assistant history or JSON parts breaks transport assumptions.
- Control: keep provider mapping minimal, deterministic, and covered by unit tests against adapter request contents and helper outputs.

### Risk R4: Public surface contradiction around `drop`
- Risk: Release A lands while `drop` remains top-level, weakening the contract pivot.
- Control: remove top-level export in the same slice and update tests/docs that import it from `fuzzy`.

### Risk R5: Hidden normalization creep
- Risk: implementation adds lossy conversions or implicit coercions that contradict the docs.
- Control: fail fast on unsupported message shapes and non-JSON-compatible values; keep normalization lossless and explicit.

## Verification Plan
- Run the existing test suite after updating it for the new contract.
- Add focused tests that inspect the normalized adapter request shape.
- Confirm no remaining production code paths reference `context_json` except possibly temporary internal compatibility helpers scheduled for removal within the same change.
- Confirm package exports and docs no longer present `drop` as part of the first-class public surface.

## Delivery Sequence
1. Introduce message types and shared evidence normalization.
2. Migrate core primitives and `LLMOps` to the new evidence contract.
3. Refactor adapters to consume normalized messages.
4. Remove top-level `drop` export.
5. Update tests and docs, then run verification.

## Plan Quality Check
- Correctness: aligned with roadmap/spec/SAD Release A and avoids later-phase scope.
- Completeness: names the concrete interfaces, files, milestones, risks, and verification steps needed for implementation.
- DRY/KISS: one shared evidence-normalization path, no speculative runtime layers.
- Feasibility: small repo, two adapters, one test file, and narrowly scoped public-surface changes make this achievable in one coherent implementation pass.
