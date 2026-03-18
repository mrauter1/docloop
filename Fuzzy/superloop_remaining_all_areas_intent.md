# Superloop Intent: Fuzzy Remaining Roadmap, All Deferred Areas

Use these documents as the source of truth:

- `fuzzy_roadmap.md`
- `fuzzy_product_spec.md`
- `SAD.md`

Also treat the repository's current state as the baseline for this run. The following slices are already present and should be treated as implemented baseline unless a corrective adjustment is strictly required:

- Release A input-contract pivot
- Release B trust layer foundations (`fuzzy.trace`, local trace viewing, `fuzzy.evals`, CI/regression helpers)
- Release C flagship utility slices already landed in the repository (`fuzzy.recipes`, examples, recipe tests)
- One Phase 4 portability/scale slice already landed: explicit batch execution

## Objective

Target all remaining roadmap areas explicitly in this run.

That means:

- plan against the full remaining roadmap,
- treat every still-deferred roadmap area as in scope,
- implement as many of the remaining areas as can be added coherently in one run,
- prefer real end-to-end delivery over placeholders,
- do not stop after a single additional slice if more remaining roadmap work can be shipped coherently afterward.

## Remaining Areas That Must Be Considered In Scope

1. Phase 4 / Portability And Scale
- fallback model policies
- approval and audit hooks
- runtime cost controls
- additional first-party adapters where feasible
- any remaining batch follow-through needed for coherence

2. Phase 5 / Ecosystem Expansion
- optional domain-pack structure
- pack template / contribution scaffolding
- eval-backed contribution standards

## Implementation Guidance

- Include all remaining roadmap items in the plan for this run.
- Implement multiple remaining areas when they fit together coherently; do not artificially stop after the first one.
- Prefer shipping complete slices with tests and docs rather than shallow stubs.
- If some remaining items still cannot be completed coherently in one run, make the deferral explicit and evidence-based.
- Keep the implementation grounded in the codebase as it exists now rather than redoing already-landed slices.

## Product Invariants

- Keep the core semantic surface small.
- Keep outputs typed and locally validated.
- Keep instruction/evidence boundaries explicit.
- Keep orchestration explicit and code-first.
- Do not add agent runtimes, memory systems, workflow UIs, or hidden optimization layers.
- Do not widen the product into a general agent platform.

## Acceptance Criteria

This run is successful if:

- the remaining roadmap is re-planned from the current repository baseline,
- all still-deferred roadmap areas are treated as in-scope for implementation consideration,
- more than one remaining roadmap area is implemented if coherence allows,
- the shipped changes are tested and aligned with the product spec and SAD,
- any still-deferred items are explicitly justified rather than silently skipped.

## Working Style

- First plan from the current repository baseline.
- Then implement as many coherent remaining roadmap areas as possible, in order.
- Then test and verify.
- Be explicit about what was completed versus what remains deferred.
- You are already operating inside a Superloop execution. Do not invoke `superloop`, create nested Superloop tasks or runs, or delegate work by spawning another Superloop loop from inside this task.
- Long quiet periods are normal while waiting for Codex or server responses. Do not treat a lack of streamed progress as a hang, and do not terminate the run just because it appears idle.
