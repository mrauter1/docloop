# Implementation Notes

## Files changed

- [`fuzzy/policy.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/policy.py)
- [`fuzzy/execution.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/execution.py)
- [`fuzzy/packs.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/packs.py)
- [`fuzzy/adapters.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/adapters.py)
- [`fuzzy/core.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/core.py)
- [`fuzzy/batch.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/batch.py)
- [`fuzzy/ops.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/ops.py)
- [`fuzzy/trace.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/trace.py)
- [`fuzzy/__init__.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/__init__.py)
- [`tests/test_portability.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_portability.py)
- [`tests/test_packs.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_packs.py)
- [`domain_packs/template/README.md`](/home/marcelo/code/docloop/Fuzzy/domain_packs/template/README.md)
- [`domain_packs/template/pyproject.toml`](/home/marcelo/code/docloop/Fuzzy/domain_packs/template/pyproject.toml)
- [`domain_packs/template/compatibility.json`](/home/marcelo/code/docloop/Fuzzy/domain_packs/template/compatibility.json)
- [`domain_packs/template/src/fuzzy_pack_template/__init__.py`](/home/marcelo/code/docloop/Fuzzy/domain_packs/template/src/fuzzy_pack_template/__init__.py)
- [`domain_packs/template/src/fuzzy_pack_template/recipes.py`](/home/marcelo/code/docloop/Fuzzy/domain_packs/template/src/fuzzy_pack_template/recipes.py)
- [`domain_packs/template/evals/template_suite.json`](/home/marcelo/code/docloop/Fuzzy/domain_packs/template/evals/template_suite.json)
- [`domain_packs/template/tests/test_pack.py`](/home/marcelo/code/docloop/Fuzzy/domain_packs/template/tests/test_pack.py)
- [`domain_packs/support/README.md`](/home/marcelo/code/docloop/Fuzzy/domain_packs/support/README.md)
- [`domain_packs/support/compatibility.json`](/home/marcelo/code/docloop/Fuzzy/domain_packs/support/compatibility.json)
- [`domain_packs/support/src/fuzzy_support/__init__.py`](/home/marcelo/code/docloop/Fuzzy/domain_packs/support/src/fuzzy_support/__init__.py)
- [`domain_packs/support/evals/support_triage_suite.json`](/home/marcelo/code/docloop/Fuzzy/domain_packs/support/evals/support_triage_suite.json)
- [`domain_packs/support/tests/test_pack.py`](/home/marcelo/code/docloop/Fuzzy/domain_packs/support/tests/test_pack.py)

## Checklist mapping

### Milestone 1: Policy and cost primitives

- Implemented `FallbackModel`, `RuntimeBudget`, `RuntimeCost`, `BatchPolicy`, `UsageAccounting`, and `ModelPricing` in [`fuzzy/policy.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/policy.py).
- Added fallback-model support to direct primitives through [`fuzzy/core.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/core.py) and [`fuzzy/ops.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/ops.py).
- Added normalized runtime accounting and batch budget enforcement in [`fuzzy/batch.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/batch.py) without changing the canonical adapter success shape.
- Preserved the existing public batch trace contract by keeping internal trace collection private unless `return_traces=True`.

### Milestone 2: Safe execution and audit controls

- Implemented `CommandPolicy`, `ApprovalDecision`, `ExecutionContext`, and `AuditRecord` in [`fuzzy/execution.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/execution.py).
- Added allow/deny policy checks, approval hooks, simulator mode, timeout handling, and audit sink emission to `dispatch(..., auto_execute=True)` in [`fuzzy/core.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/core.py).
- Preserved the canonical `DispatchExecution` top-level shape for simulator mode.
- Restored existing sync executor behavior when no timeout is configured; timeout-specific off-thread execution is now limited to the timeout path.
- Narrowed timeout support so configured timeouts are accepted only for async executors; synchronous executors now fail fast before execution instead of running in the background after a timeout.

### Milestone 3: Adapter and batch follow-through

- Added `AzureOpenAIAdapter` in [`fuzzy/adapters.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/adapters.py).
- Added `LLMOps.from_azure_openai(...)` and `from_provider("azure_openai", ...)` in [`fuzzy/ops.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/ops.py).
- Extended batch reporting with `cost` and `budget_exhausted` in [`fuzzy/batch.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/batch.py).
- Added trace-attempt model capture in [`fuzzy/trace.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/trace.py) so fallback usage is visible.

### Milestone 4: Ecosystem scaffolding and contribution standards

- Added in-repo optional-pack scaffolding under [`domain_packs/`](/home/marcelo/code/docloop/Fuzzy/domain_packs).
- Added pack validation in [`fuzzy/packs.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/packs.py) to enforce compatibility metadata, eval fixtures, and tests.
- Exported the new pack validation helper in [`fuzzy/__init__.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/__init__.py).

## Assumptions

- Fallback policy should only apply to provider-side failures, not validation failures, to preserve the trust boundary.
- Runtime cost estimation should remain explicit and best-effort; no provider pricing is guessed by the framework.
- Simulator mode should remain a local execution-control feature, not a new dispatch result category or workflow runtime.
- Azure OpenAI support should stay structurally close to the existing OpenAI adapter and avoid new dependencies.
- Timeout handling should prefer explicit fail-fast rejection over best-effort cancellation when safe cancellation semantics are not available.

## Expected side effects

- Trace attempts now include the model used for each provider attempt, which makes fallback behavior visible in trace payloads.
- Batch execution now internally gathers trace data even when `return_traces=False` so it can compute cost/budget results, but successful public `BatchResult.trace` values remain hidden unless `return_traces=True`.
- Timeout-configured sync executors now fail before execution with a clear error instead of attempting unsafe background-thread cancellation semantics.
- `dispatch(..., auto_execute=True)` can now fail earlier on command-policy denial, approval rejection, timeout, or audit sink misconfiguration.

## Deduplication / centralization decisions

- Centralized fallback validation, budget normalization, usage extraction, and pricing logic in [`fuzzy/policy.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/policy.py) instead of duplicating it across batch and core.
- Centralized approval/audit policy validation and audit helpers in [`fuzzy/execution.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/execution.py).
- Centralized optional-pack contribution validation in [`fuzzy/packs.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/packs.py) rather than scattering checks across tests and docs.

## Intentional deferrals

- Did not add Anthropic, Gemini, or local OpenAI-compatible adapters in this run; Azure OpenAI was the single additional first-party adapter shipped per the roadmap priority order.
- Did not introduce richer provider-specific price catalogs or hosted audit persistence; pricing remains caller-supplied and audit handling remains local callback-based.
- Did not turn sample domain packs into separately publishable packages beyond the in-repo scaffold and validation standard.

## Verification

- Ran `python3 -m pytest -q`
- Result: `89 passed, 1 skipped`
