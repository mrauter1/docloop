# Implementation Notes

## Files Changed
- `fuzzy/types.py`
- `fuzzy/core.py`
- `fuzzy/ops.py`
- `fuzzy/adapters.py`
- `fuzzy/__init__.py`
- `tests/test_fuzzy.py`

## Checklist Mapping
- Milestone 1 `Evidence model and preflight validation`: completed via new provider-neutral `Message`/`MessagePart` types and shared evidence normalization in `fuzzy/core.py`.
- Milestone 2 `Primitive and wrapper signature migration`: completed for all four primitives and all `LLMOps` async/sync entrypoints using the shared `context` or `messages` path.
- Milestone 3 `Adapter boundary refactor`: completed by replacing adapter consumption of `context_json` with ordered normalized `messages` in both shipped adapters.
- Milestone 4 `Public surface cleanup`: completed by removing top-level `drop` export from `fuzzy.__init__.py` while keeping the internal helper for existing internal/test use.
- Milestone 5 `Tests and docs`: test coverage completed in `tests/test_fuzzy.py`; no separate product-doc edit was required because the source-of-truth roadmap/spec/SAD files already matched the Release A direction and did not need correction in this slice.

## Assumptions
- Using a private sentinel for `context` and `messages` is acceptable so explicit `None` remains representable as caller evidence while still enforcing the exactly-one-of contract.
- Release A only requires `text` and `json` message parts, so any other part type is treated as invalid configuration rather than partially supported runtime behavior.
- Serializing `json` parts as deterministic JSON text at the adapter transport layer satisfies the current provider integration without introducing hidden public normalization.
- Reviewer follow-up required strict rejection of unsupported extra keys on message objects and message parts, so the validator now enforces exact allowed-key sets rather than dropping unknown fields.

## Expected Side Effects
- Direct primitive calls and `LLMOps` methods now reject both-missing and both-present `context`/`messages` combinations before any provider call.
- Direct primitive calls now also reject unsupported extra fields on message objects and `text`/`json` parts before any provider call.
- Adapter request objects now carry `messages` instead of `context_json`.
- `from fuzzy import drop` no longer works; internal code can still import `drop` from `fuzzy.core`.
- Existing `context=` callers remain supported.

## Deduplication / Centralization Decisions
- Centralized evidence validation and normalization into one shared `fuzzy/core.py` path instead of duplicating checks across primitives.
- Centralized exact-key enforcement in the same shared evidence-normalization path so unsupported message shapes fail consistently across all primitives and `LLMOps`.
- Centralized provider JSON-part serialization on `deterministic_json_dumps()` so both adapters encode `json` parts consistently.

## Verification
- `python3 -m compileall fuzzy tests`
- `pytest -q`
- Result: `49 passed, 1 skipped`
