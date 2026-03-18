# Plan ↔ Plan Verifier Feedback

- 2026-03-17 producer: Replaced the empty plan with an implementation-ready roadmap covering Release B, Release C, Phase 4, and Phase 5. The plan anchors new work on the existing single request/retry path, prioritizes trace/eval foundations first, defines concrete interfaces for trace/eval/recipe layers, and records explicit deferrals and risks so the implementation phase can ship a coherent subset without faking completeness.
- PLAN-001 non-blocking: The plan is complete and implementation-ready. Keep `return_trace` strictly opt-in during implementation so existing primitive return types remain unchanged for current callers.
- PLAN-002 non-blocking: The plan correctly defers later Phase 4 and Phase 5 work behind the Release B substrate. In implementation, avoid introducing recipe-specific hook shapes that diverge from the shared `return_trace` and `trace_sink` interfaces defined earlier in the plan.
