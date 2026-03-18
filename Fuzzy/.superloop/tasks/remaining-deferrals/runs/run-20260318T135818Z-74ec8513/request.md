# Superloop Intent: Remaining Fuzzy Deferrals

Use these documents as the source of truth:

- `fuzzy_roadmap.md`
- `fuzzy_product_spec.md`
- `SAD.md`

Also treat the repository's current state as the baseline for this run. Assume all previously landed slices are already present and should not be reimplemented unless a corrective adjustment is strictly required:

- Release A contract/input pivot
- Release B trace/evals/test foundations
- Release C recipes and examples
- Phase 4 batch execution, fallback policy, approval/audit hooks, runtime cost controls, and Azure OpenAI support
- Phase 5 in-repo pack scaffolding and validation

## Objective

Implement the still-deferred roadmap items that remain after the all-areas run.

Those deferred items are:

1. Additional first-party adapters
- Anthropic
- Gemini
- local OpenAI-compatible endpoints, if still coherent after Anthropic/Gemini

2. Richer pricing support
- a small first-party pricing catalog / pricing helpers that work with the existing runtime cost model
- do not guess prices silently at runtime; keep pricing explicit and inspectable

3. More publishable pack scaffolding
- improve the pack template and support pack structure so they are closer to separately publishable packages
- keep this as packaging/scaffolding work, not a hosted registry or plugin runtime

## Implementation Guidance

- Re-plan only the remaining deferred scope from the current repository baseline.
- Implement as many of the remaining deferrals as can be shipped coherently in one run.
- Prefer real adapter implementations with tests over placeholders.
- Keep the adapter contract aligned with the existing narrow `LLMAdapter.complete(...)` surface.
- Keep pricing support explicit and local-first.
- Keep pack work as repo scaffolding, metadata, and validation; do not invent a new runtime/plugin system.

## Product Invariants

- Keep the core semantic surface small.
- Keep outputs typed and locally validated.
- Preserve explicit orchestration and instruction/evidence boundaries.
- Do not add agent runtimes, memory systems, workflow UIs, or hidden optimization layers.

## Acceptance Criteria

This run is successful if:

- the remaining deferrals are re-planned from the current baseline,
- at least one additional first-party adapter lands unless the verifier finds a concrete blocker,
- pricing support is more complete and still explicit,
- pack scaffolding is more publishable than before,
- changes are tested and any still-deferred items are explicitly justified.

## Working Style

- First plan from the current baseline.
- Then implement the remaining deferrals in coherent slices.
- Then test and verify.
- Be explicit about what was completed versus what remains deferred.
- You are already operating inside a Superloop execution. Do not invoke `superloop`, create nested Superloop tasks or runs, or delegate work by spawning another Superloop loop from inside this task.
- Long quiet periods are normal while waiting for Codex or server responses. Do not treat a lack of streamed progress as a hang, and do not terminate the run just because it appears idle.
