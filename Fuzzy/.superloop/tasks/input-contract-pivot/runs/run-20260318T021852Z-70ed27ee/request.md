# Superloop Intent: Fuzzy Roadmap Execution

Use these documents as the source of truth for product and architecture direction:

- `fuzzy_roadmap.md`
- `fuzzy_product_spec.md`
- `SAD.md`

## Objective

Use the full roadmap, product spec, and architecture doc as strategic context, but do not attempt to implement the entire multi-release roadmap in one run.

The implementation scope for this run is Release A only:

- align the codebase with the new input-contract pivot,
- preserve Fuzzy's core ethos,
- update code, tests, and docs as needed for a coherent Release A slice,
- leave later roadmap phases as planned future work unless a small enabling change is strictly required.

## Product Direction To Preserve

- Keep `system_prompt` as the standard top-level instruction surface.
- Do not expose `drop` or `to_json` as first-class public primitives in the new direction.
- The public semantic core remains:
  - `eval_bool`
  - `classify`
  - `extract`
  - `dispatch`
  - `LLMOps`
- The public input contract should be:
  - `system_prompt`
  - exactly one of `context` or `messages`
- `messages` is the advanced input surface.
- `context` is shorthand for simple cases.
- `context` and `messages` are mutually exclusive.
- Keep outputs strongly typed and locally validated.
- Do not add agent loops, workflow runtimes, memory, platform behavior, or hidden normalization layers.

## Release A Scope

Implement the following if feasible within one coherent repo change:

1. Input contract
- Update primitive and wrapper interfaces toward the new input contract.
- Support exactly one of `context` or `messages` per call.
- Keep `system_prompt`.

2. Message model
- Introduce provider-neutral message structures suitable for the new contract.
- Required part types for this slice are `text` and `json`.
- Keep the design extensible for future multimodal parts, but do not implement multimodal support now unless it is trivial and low-risk.

3. Adapter boundary
- Update adapter request handling away from `context_json` as the primary public boundary and toward ordered evidence/messages.
- Preserve the clear separation between framework instructions and caller evidence.

4. Validation and errors
- Invalid combinations such as both `context` and `messages` should fail before provider calls.
- Unsupported message shapes should fail clearly.
- Preserve existing typed-output validation and bounded retry behavior.

5. Tests
- Update or add tests so the new public contract is exercised.
- Preserve existing behavior where still in scope.

6. Docs
- Keep docs consistent with implementation for this release slice.

## Out Of Scope For This Run

Do not attempt to fully implement later roadmap items such as:

- `fuzzy.trace`
- `fuzzy.evals`
- recipe packs
- additional adapters beyond what is required for the input pivot
- batch/runtime policy features
- domain packs
- multimodal input support beyond keeping the API extensible

## Migration Guidance

- Favor a coherent implementation over preserving every old internal assumption.
- If backward compatibility is cheap and clean, preserve it.
- If a legacy behavior conflicts with the new public direction, prefer the new direction and update tests/docs accordingly.
- Avoid unnecessary churn outside the scoped change.

## Acceptance Criteria

The run is successful if it leaves the repository in a state where:

- the implementation matches the Release A direction in the roadmap/spec/SAD,
- the input contract is explicit and test-covered,
- the separation of `system_prompt` and caller evidence is preserved,
- the codebase is more internally consistent than before,
- later roadmap phases remain clearly future work rather than partially implemented sprawl.

## Working Style

- First produce a plan using the roadmap/spec/SAD as context.
- Then implement only the Release A slice.
- Then test and verify the scoped change.
- Prefer clarity and consistency over broad feature count.
