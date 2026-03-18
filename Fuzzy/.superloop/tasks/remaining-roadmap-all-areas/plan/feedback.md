# Plan ↔ Plan Verifier Feedback

## 2026-03-18 Producer Cycle 1 Attempt 1

- Replaced the empty plan stub with an implementation-ready plan covering every remaining Phase 4 and Phase 5 roadmap item from the current repository baseline.
- Documented the confirmed baseline already present in code, the missing gaps, four concrete milestones, proposed public interfaces, required tests, and a risk register.
- Chose a coherence-first delivery order: policy/cost primitives, safe dispatch execution hooks, one adjacent new adapter plus batch follow-through, then domain-pack scaffolding and eval-backed contribution standards.

## 2026-03-18 Verifier Cycle 1 Attempt 1

- `PLAN-001` `blocking`: The proposed simulator behavior in Milestone 2 says `dispatch(..., auto_execute=True)` should return a normal execution-shaped result with an added `"simulated": True` marker, but the SAD defines the canonical `DispatchExecution` shape as only `{"decision": ..., "result": ...}`. This is a compatibility break for existing callers and contradicts the source-of-truth contract. Minimal correction: keep the dispatch return shape canonical and carry simulation state through trace/audit metadata or define a separate non-breaking wrapper shape explicitly justified against the SAD.
- `PLAN-002` `blocking`: Milestone 1 calls for runtime token/cost accounting, but the plan never defines the minimal normalized usage/cost contract that adapters must provide to support that work. Today `provider_metadata` is provider-specific and optional in [`fuzzy/adapters.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/adapters.py), so implementation would be forced either to leak provider quirks upward or invent inconsistent accounting. Minimal correction: add an explicit normalized accounting contract to the plan, such as stable token fields and optional pricing inputs, and state how missing metadata degrades behavior.
- `PLAN-003` `blocking`: Milestone 3 reprioritizes the adapter slice toward "a local OpenAI-compatible adapter or Azure OpenAI adapter", but the roadmap source of truth sets the Phase 4 adapter priority order as Azure OpenAI, then Anthropic, then Gemini, then local OpenAI-compatible endpoints. Because the plan is the run’s single source of truth, this changes roadmap priority without an evidence-based deferral rationale. Minimal correction: align the priority order to the roadmap or explicitly justify why Azure remains first-choice and local-compatible is only the fallback if Azure proves incoherent during implementation.

## 2026-03-18 Producer Cycle 2 Attempt 1

- Revised the plan to resolve the verifier’s blocking issues rather than broadening scope.
- Preserved the SAD dispatch contract by changing simulator-mode planning to keep the canonical `DispatchExecution` top-level shape and move simulation state into `result` plus audit/trace metadata.
- Added a concrete normalized accounting layer for runtime cost controls: best-effort token extraction from optional `provider_metadata`, explicit caller-supplied pricing, and request-count-only degradation when usage data is absent.
- Restored the roadmap adapter priority order with Azure OpenAI as the first-choice implementation target and local OpenAI-compatible support as the explicit fallback only if Azure proves incoherent during implementation.

## 2026-03-18 Verifier Cycle 2 Attempt 1

- `PLAN-004` `non-blocking`: Re-review found no remaining blocking plan issues. The revised plan now preserves the SAD dispatch contract, defines a concrete normalized accounting path without expanding the canonical adapter success shape, and aligns the adapter milestone with the roadmap priority order. Criteria updated to complete.
