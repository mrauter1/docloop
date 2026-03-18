# Superloop Intent: Remaining Fuzzy Roadmap

Use these documents as the source of truth:

- `fuzzy_roadmap.md`
- `fuzzy_product_spec.md`
- `SAD.md`

Also treat the completed Release A input-contract pivot as already implemented in the repository. The new evidence model is now part of the baseline.

## Objective

Use the full remaining roadmap as scope for this run.

That means:

- include all remaining roadmap items after Release A as planning context,
- plan the remaining work end to end,
- implement and test as much of the remaining roadmap as can be added coherently in this codebase in one run,
- prefer shipping complete, well-integrated slices over scattering partial stubs across every future area.

## Release A Baseline Already Landed

Assume the repository already has:

- `system_prompt` plus exactly one of `context` or `messages`,
- provider-neutral `Message` support with `text` and `json` parts,
- adapter consumption of ordered messages,
- `drop` removed from the top-level public package surface.

Do not redo Release A unless a small corrective adjustment is required by later work.

## Remaining Roadmap Scope

Treat all of these as in-scope for planning and potential implementation:

1. Release B / Trust Layer
- `fuzzy.trace`
- local trace viewing
- `fuzzy.evals`
- regression and CI helpers

2. Release C / Flagship Utility
- `fuzzy.recipes`
- 3-4 flagship recipes
- reference service integrations

3. Phase 4 / Portability And Scale
- more first-party adapters where feasible
- batch execution
- fallback model policies
- approval and audit hooks
- runtime cost controls

4. Phase 5 / Ecosystem Expansion
- optional domain-pack structure
- pack template / contribution scaffolding
- eval-backed contribution standards

## Implementation Guidance

- Include all roadmap items in the plan.
- Implement the next coherent milestones in roadmap order.
- Prefer a strong Release B foundation plus any coherent Release C slices over speculative stubs for later phases.
- If the full remaining roadmap cannot be fully implemented in one coherent pass, still produce a complete plan for all of it and implement the maximum coherent subset.
- Avoid fake completeness. Do not add empty modules or shallow placeholders just to say an item exists.

## Product Invariants

- Keep the core semantic surface small.
- Keep outputs typed and locally validated.
- Keep instruction/evidence boundaries explicit.
- Keep orchestration explicit and code-first.
- Do not add agent runtimes, memory systems, workflow UIs, or hidden optimization layers.
- Do not widen the product into a general agent platform.

## Acceptance Criteria

This run is successful if:

- the remaining roadmap is fully planned with concrete milestones,
- at least one major post-Release-A roadmap area is implemented and tested coherently,
- the implementation does not violate the product spec or SAD,
- deferred roadmap items are clearly documented rather than hand-waved,
- the codebase remains internally consistent and testable.

## Working Style

- Plan the full remaining roadmap first.
- Then implement the most coherent next slices in order.
- Then test and verify.
- Be explicit about what was completed versus deferred.
