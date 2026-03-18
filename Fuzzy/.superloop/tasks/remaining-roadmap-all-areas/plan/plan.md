# Remaining Roadmap Run Plan

## Scope and Baseline

This plan covers every still-deferred roadmap area called out in the request, using the current repository state as the baseline.

Already landed baseline confirmed in code:
- Release A contract pivot and typed `context` / `messages` evidence boundary in [`fuzzy/core.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/core.py)
- Release B trust layer foundations in [`fuzzy/trace.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/trace.py), [`fuzzy/evals.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/evals.py), and tests
- Release C flagship recipes and examples in [`fuzzy/recipes/`](/home/marcelo/code/docloop/Fuzzy/fuzzy/recipes)
- One Phase 4 slice: explicit batch execution in [`fuzzy/batch.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/batch.py)

Still deferred and in scope for this run:
- Phase 4: fallback model policies
- Phase 4: approval and audit hooks
- Phase 4: runtime cost controls
- Phase 4: additional first-party adapters where feasible
- Phase 4: remaining batch follow-through needed for coherence
- Phase 5: optional domain-pack structure
- Phase 5: pack template / contribution scaffolding
- Phase 5: eval-backed contribution standards

Planning constraints from roadmap/spec/SAD:
- Keep the core semantic surface small.
- Keep outputs typed and locally validated.
- Preserve explicit orchestration and instruction/evidence boundaries.
- Do not widen the product into an agent runtime or workflow platform.

## Repository Findings

### Implemented baseline relevant to this run
- Adapter boundary is intentionally narrow: `LLMAdapter.complete(request) -> {"raw_text": ..., ...}` in [`fuzzy/adapters.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/adapters.py)
- `LLMOps` currently exposes only OpenAI and OpenRouter factories in [`fuzzy/ops.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/ops.py)
- Batch support already handles concurrency, traces, and stop-on-error, but has no budgeting, fallback, or provider-aware retry policy in [`fuzzy/batch.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/batch.py)
- `dispatch(..., auto_execute=True)` executes directly after model selection and only surfaces execution/output-validation failures; there is no approval gate, simulator mode, allow/deny policy, timeout wrapper, or audit record in [`fuzzy/core.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/core.py)
- Trace and eval modules provide reusable serialization/reporting hooks that can support new audit and contribution standards without platform expansion

### Important gaps to address coherently
- There is no normalized concept of a run policy spanning retries, fallback, approval, audit, and cost budget.
- There is no normalized accounting contract for deriving runtime cost controls from the optional provider metadata already exposed by current adapters.
- There are no additional adapters beyond OpenAI/OpenRouter.
- There is no package/template/contribution scaffolding for optional domain packs.

## Delivery Strategy

Implement the remaining roadmap in four coherent milestones, ordered by dependency:

1. Policy and cost primitives
2. Safe execution and audit controls
3. Adapter and batch follow-through
4. Ecosystem scaffolding and contribution standards

This ordering keeps the public surface explicit and lets the implementation phase ship multiple roadmap areas in one pass instead of isolated fragments.

## Milestones

### Milestone 1: Policy and Cost Primitives

Goal:
- Add minimal, explicit policy objects that unlock fallback models, runtime budgets, and batch follow-through without destabilizing the current primitive API.

Implementation targets:
- Add a new module, likely [`fuzzy/policy.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/policy.py), for portable policy dataclasses and helpers.
- Extend [`fuzzy/ops.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/ops.py) and [`fuzzy/batch.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/batch.py) to accept policy objects.
- Keep direct primitive entrypoints usable without requiring policy objects.
- Preserve the SAD’s canonical adapter success contract; do not require new top-level adapter response fields for this run.

Planned interfaces:

```python
@dataclass(frozen=True)
class FallbackModel:
    model: str
    on_categories: tuple[str, ...] = ("provider_transport", "provider_rate_limit")

@dataclass(frozen=True)
class RuntimeBudget:
    max_requests: int | None = None
    max_estimated_total_tokens: int | None = None
    max_estimated_cost: float | None = None

@dataclass(frozen=True)
class RuntimeCost:
    request_count: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost: float | None = None

@dataclass(frozen=True)
class BatchPolicy:
    fallback_models: tuple[FallbackModel, ...] = ()
    budget: RuntimeBudget | None = None

@dataclass(frozen=True)
class UsageAccounting:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

@dataclass(frozen=True)
class ModelPricing:
    model: str
    input_cost_per_1k_tokens: float | None = None
    output_cost_per_1k_tokens: float | None = None
```

Behavior decisions:
- Fallback is attempted only for provider-side failures that occur before usable candidate text is returned.
- Fallback does not mask validation failures; malformed JSON and schema-invalid output remain normal bounded-retry failures on the current model.
- Runtime accounting is derived from optional adapter metadata through one core-owned normalization helper, not from provider-specific logic spread across batch code.
- Normalization target for this run: best-effort extraction of `input_tokens`, `output_tokens`, and `total_tokens` from existing optional `provider_metadata`; if those fields cannot be derived, accounting degrades to request-count-only enforcement.
- Estimated cost is computed only when the caller supplies explicit `ModelPricing` data for the active model; the framework must not guess provider pricing.
- Budget exhaustion fails fast before launching additional batch work.

Why this milestone comes first:
- Approval/audit hooks and batch follow-through both need a normalized policy surface to avoid scattering one-off parameters across primitives.

### Milestone 2: Safe Execution and Audit Controls

Goal:
- Add approval hooks, simulator mode, command policy checks, timeout handling, and audit records around `dispatch` execution while preserving today’s explicit decision boundary.

Implementation targets:
- Add a new module, likely [`fuzzy/execution.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/execution.py), for dispatch execution policy types.
- Update [`fuzzy/core.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/core.py) `dispatch` execution flow.
- Reuse [`fuzzy/trace.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/trace.py) serialization patterns for audit records instead of inventing a new persistence subsystem.

Planned interfaces:

```python
ApprovalHook = Callable[[DispatchDecision, "ExecutionContext"], ApprovalDecision]
AuditSink = Callable[[AuditRecord], Any]

@dataclass(frozen=True)
class CommandPolicy:
    allow_commands: tuple[str, ...] | None = None
    deny_commands: tuple[str, ...] | None = None
    timeout_seconds: float | None = None
    simulator_mode: bool = False
    approval_hook: ApprovalHook | None = None
    audit_sink: AuditSink | None = None

@dataclass(frozen=True)
class ApprovalDecision:
    approved: bool
    reason: str | None = None

@dataclass(frozen=True)
class AuditRecord:
    operation: str
    model: str
    decision: dict[str, Any]
    approved: bool | None
    executed: bool
    simulated: bool
    result: Any = None
    error_category: str | None = None
    error_message: str | None = None
```

Behavior decisions:
- Approval hooks run only after the model has produced a validated command decision and before executor invocation.
- `simulator_mode=True` preserves the SAD’s canonical `DispatchExecution` top-level shape: `{"decision": ..., "result": ...}`.
- In simulator mode, `result` is a simulator payload owned by the framework, for example validated command args plus simulation metadata; simulation state is also emitted through audit/trace data rather than a new top-level dispatch field.
- Simulator mode skips executor invocation entirely and therefore must not claim executor output validation success for commands that define `output_schema`.
- Allow-list / deny-list enforcement happens before approval hooks so the policy boundary is deterministic.
- Timeout handling wraps executor invocation only; it must not change model retry semantics.
- Audit records are callback/file-sink oriented and local-first, matching the trace design.

Compatibility decisions:
- Plain `dispatch(..., auto_execute=False)` behavior remains unchanged.
- Plain `dispatch(..., auto_execute=True)` remains available; new controls are opt-in.

### Milestone 3: Adapter and Batch Follow-Through

Goal:
- Land at least one coherent additional first-party adapter and finish the batch story so policy/cost controls work end to end.

Implementation targets:
- Extend [`fuzzy/adapters.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/adapters.py) with one additional adapter that fits the current narrow contract with low dependency overhead.
- Extend [`fuzzy/ops.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/ops.py) with a matching factory.
- Thread budget/fallback results through [`fuzzy/batch.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/batch.py) and exported types.

Adapter priority decision for this run:
- Follow the roadmap priority order for new adapters: Azure OpenAI first, then Anthropic, then Gemini, then local OpenAI-compatible endpoints.

Rationale:
- Azure OpenAI is the first-choice implementation target because it is the roadmap’s stated first priority and is structurally closest to the existing OpenAI request/response path.
- Anthropic and Gemini would likely require materially different payload/response shaping and a larger provider-contract test matrix.
- A local OpenAI-compatible adapter becomes the fallback implementation choice only if Azure-specific request construction proves incoherent relative to the current no-extra-dependency architecture during implementation.

Planned interfaces:

```python
class AzureOpenAIAdapter(LLMAdapter):
    ...

@classmethod
def from_azure_openai(...): ...

@dataclass(frozen=True)
class BatchReport:
    ...
    cost: RuntimeCost | None = None
    budget_exhausted: bool = False
```

Batch follow-through decisions:
- Batch worker scheduling should stop launching new calls once budget exhaustion or non-recoverable policy termination is reached.
- Per-call results should retain current success/failure ordering guarantees.
- Fallback usage should be visible in traces and batch results so eval/reporting can reason about model portability behavior.
- If Azure OpenAI is deferred during implementation for coherence reasons, that deferral must be explicit and the fallback adapter choice must be justified against the roadmap priority order in implementation notes.

### Milestone 4: Ecosystem Scaffolding and Contribution Standards

Goal:
- Ship the smallest useful Phase 5 slice in-repo: optional domain-pack structure, a pack template, and eval-backed contribution standards that reuse the existing recipes/evals model.

Implementation targets:
- Add a top-level scaffold directory, likely [`domain_packs/`](/home/marcelo/code/docloop/Fuzzy/domain_packs), containing:
  - one template pack skeleton
  - one concrete sample pack built from an existing recipe area if feasible
- Add contribution docs and compatibility metadata templates.
- Add tests or fixture validation that enforce the eval-backed quality bar.

Planned structure:

```text
domain_packs/
  template/
    README.md
    pyproject.toml
    src/fuzzy_pack_template/__init__.py
    src/fuzzy_pack_template/recipes.py
    evals/
    tests/
  support/
    README.md
    compatibility.json
    evals/
```

Contribution standard decisions:
- Every pack template must declare compatible core version range, exported recipe entrypoints, bundled eval fixtures, and required tests.
- Contribution validation should use existing `fuzzy.evals` helpers rather than a new bespoke framework.
- The first implementation pass should favor scaffolding and standards over trying to publish multiple fully distinct external packages from this repository.

## Cross-Cutting Interface Changes

Expected exported surface additions:
- Re-export new policy / execution types from [`fuzzy/__init__.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/__init__.py) only when the surface is stable and minimal.
- Preserve existing function signatures unless a new opt-in keyword is necessary.

Preferred new optional keywords:
- `fallback_models=` or `batch_policy=` on batch/ops entrypoints
- `command_policy=` on `dispatch` and `LLMOps.dispatch`
- `audit_sink=` only if it is not already nested under `command_policy`

Preferred accounting helper boundary:
- Keep adapter responses compatible with the SAD’s canonical `{"raw_text", "provider_response_id"}` success shape.
- Continue allowing optional `provider_metadata` internally, but normalize accounting through one core helper before any budget logic consumes it.

Avoid:
- Adding hidden global state
- Adding implicit provider failover defaults
- Adding pack loading/runtime discovery inside core primitives

## Test and Verification Plan

Required tests for this run:
- Fallback policy unit tests:
  - retries current model first for validation failures
  - switches model only on configured provider failure categories
  - records fallback usage in trace/batch outputs
- Cost control tests:
  - request-count budget exhaustion
  - token accounting normalization from optional provider metadata
  - cost accounting accumulation only when explicit pricing data is available
  - graceful degradation to request-count-only budgeting when metadata is absent
  - batch stops launching new calls after budget exhaustion
- Safe execution tests:
  - allow-list and deny-list enforcement
  - approval hook approves/rejects deterministically
  - simulator mode skips side effects while preserving canonical `DispatchExecution` shape
  - simulator mode records simulation state in audit/trace outputs instead of adding a new top-level dispatch field
  - executor timeout produces stable framework error and audit record
  - audit sink receives success and failure records
- Adapter tests:
  - Azure OpenAI request assembly
  - Azure OpenAI response extraction
  - `LLMOps.from_azure_openai(...)` coverage
- Ecosystem tests:
  - pack template fixtures load cleanly
  - contribution metadata validation
  - eval-backed standards reject incomplete pack definitions

Regression checks:
- Existing primitive semantics must remain unchanged when no new policies are provided.
- Existing recipe tests must continue passing.
- Existing trace/eval report serialization must remain backward compatible for current fields.

## Risk Register

### Risk 1: Surface-area creep

Why it matters:
- The request covers many deferred items, and the easiest failure mode is to scatter knobs across the core API.

Mitigation:
- Group related knobs under a small number of policy dataclasses.
- Keep all new controls opt-in.
- Prefer `LLMOps` / batch integration first, then expose only the minimum direct primitive keywords required for coherence.

### Risk 2: Fallback semantics hide validation problems

Why it matters:
- Falling back after malformed or schema-invalid output would blur the framework’s trust boundary.

Mitigation:
- Restrict fallback to provider-side failure categories by default.
- Keep validation exhaustion attached to the selected model attempt chain.
- Add explicit trace fields showing model used per attempt.

### Risk 3: Cost control accuracy is provider-fragile

Why it matters:
- Current adapters expose provider metadata inconsistently, and not every provider returns standardized cost data.

Mitigation:
- Make request-count budgeting the guaranteed baseline.
- Treat token/cost accounting as opportunistic when metadata exists.
- Keep the accounting contract explicit and best-effort.

### Risk 4: Safe execution hooks turn into hidden orchestration

Why it matters:
- Approval hooks, simulator mode, and audits can drift toward a workflow engine if overbuilt.

Mitigation:
- Run hooks only around one validated dispatch decision.
- Use callback/file sinks, not managed runtimes.
- Do not add queues, persistence layers, or human task state machines.

### Risk 5: Additional adapter work overruns the run

Why it matters:
- Anthropic/Gemini support could consume the run and crowd out the other roadmap areas.

Mitigation:
- Prioritize a structurally adjacent adapter this run.
- Defer broader adapter expansion explicitly if one coherent adapter plus tests is already shipped.

### Risk 6: Domain-pack scaffolding becomes pseudo-packaging theater

Why it matters:
- Creating many empty directories would satisfy the letter of Phase 5 while shipping little value.

Mitigation:
- Ship one reusable template and one standards-enforced sample structure.
- Tie contribution acceptance to eval fixtures and compatibility metadata.

## Expected Implementation Cut Line

Items expected to be fully implemented in this run if execution proceeds cleanly:
- Fallback model policies
- Runtime cost controls at least for request-count budgeting and metadata-backed accounting
- Approval hooks, audit hooks, allow/deny command policies, and simulator mode
- Batch follow-through integrating policy and budget behavior
- One additional first-party adapter that is structurally adjacent to existing OpenAI support
- Optional domain-pack structure, pack template, and eval-backed contribution standards

Items that may remain partially deferred if time/regression pressure forces a cut line:
- More than one additional first-party adapter
- Rich provider-specific cost estimation for providers that do not expose stable usage metadata
- Full standalone publishable optional packages beyond in-repo scaffolding

Any such deferral must be documented explicitly in implementation notes with regression- or coherence-based justification.

## Implementation Sequence for the Next Phase

1. Add policy dataclasses and wire them into batch/ops entrypoints.
2. Refactor dispatch execution to support command policies, approval, simulation, timeout, and audit sinks.
3. Add fallback-aware execution flow and trace/batch visibility.
4. Add budget accumulation and stop conditions.
5. Add one additional first-party adapter and factory.
6. Add pack template, sample pack structure, and contribution-standard validation.
7. Run targeted tests first, then full suite.

## Done Criteria for This Plan

This plan is implementation-ready when the next phase can answer, for each roadmap item, all of:
- Which module changes are required
- Which public interfaces change
- Which tests prove behavior
- Which items are full delivery targets versus explicit deferral candidates

That standard is met by the milestones, interfaces, test plan, and risk controls above.
