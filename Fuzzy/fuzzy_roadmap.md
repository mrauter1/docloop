# Fuzzy Roadmap: 10x Adoption Without Ethos Drift

## 1. Roadmap Thesis

Fuzzy will not win by becoming a general AI framework.

Fuzzy will win by becoming the most trusted way to put a constrained LLM decision inside production code.

That means the roadmap should optimize for:

- fastest path from install to first safe decision,
- strongest debugging story when the model fails,
- easiest way to define schemas and commands,
- easiest way to measure regressions before shipping,
- best out-of-the-box fit for narrow operational workflows.

The market signal from DSPy, LangChain, Langflow, and AutoGen is consistent:

- users like leverage,
- users hate hidden behavior,
- users hate version churn,
- users hate unclear docs,
- users hate weak production debugging,
- users lose trust when a framework expands faster than its reliability story.

Fuzzy should build around those pain points, not repeat them.

## 2. Product Strategy

### Keep the core small

The core remains:

- `eval_bool`
- `classify`
- `extract`
- `dispatch`
- `LLMOps`
- explicit evidence boundaries via `system_prompt` plus exactly one of `context` or `messages`

Everything else is an optional layer around the core, not a replacement for it.

### Expand around the core, not above it

The right expansion layers are:

1. authoring ergonomics
2. debugging and traces
3. evals and regression control
4. reusable recipes
5. provider portability
6. scale and policy controls

The wrong expansion layers are:

- visual workflow builders
- autonomous agent loops
- mandatory runtime state
- long-running orchestration
- hosted control planes as the default experience

## 3. North Star

Within 2 releases, Fuzzy should enable this experience:

1. A backend engineer can ship a production-safe classification or extraction in under 30 minutes.
2. Every failure is inspectable with one trace object and one clear validation boundary.
3. Every prompt or model change can be evaluated locally and in CI before rollout.
4. Common business workflows can be assembled from recipes with minimal glue code.

## 4. Revised Priority Order

The current spec is directionally right, but the order should change.

The biggest adoption blockers are not missing domain packs or missing adapters. The biggest blockers are:

- unclear input surface for non-trivial evidence and conversation history,
- schema friction,
- command setup friction,
- weak onboarding,
- weak debugging visibility,
- lack of evaluation workflow.

So the roadmap should prioritize:

1. docs and stable contracts
2. schema and command ergonomics
3. traces and evals
4. flagship recipes
5. adapters and scale features
6. domain packs

## 5. Phase 1: Adoptability First

### Goal

Make Fuzzy the easiest way to add one safe LLM decision to an existing Python service.

### Why this phase comes first

If teams cannot get to a clean first use case quickly, nothing else matters.

This phase removes the friction that causes users to reach for bigger frameworks even when they do not actually need them.

### Deliverables

#### A. Contract hardening

- Freeze the public primitive signatures for a stable minor-series API.
- Freeze the first-class input contract: `system_prompt`, `context`, and `messages`.
- Add explicit deprecation policy.
- Add compatibility tests for all documented examples.
- Publish a short "what Fuzzy is / is not" page.

#### B. Onboarding and docs

- 15-minute quickstart for each primitive.
- "Choose the right primitive" decision guide.
- "Why not agents?" positioning page.
- migration guide from hand-written prompting.
- examples for sync and async usage.
- examples with `messages`, simple `context`, plain dict schema, Pydantic, and command dispatch.

#### C. Typed message input contract

- provider-neutral `Message` and `Part` types,
- required `text` and `json` parts,
- clear `role` rules for `user` and `assistant`,
- `system_prompt` remains separate from caller messages,
- `context` and `messages` are mutually exclusive,
- extensible contract for future `image`, `audio`, `video`, and `file` parts.

This is the right way to support richer inputs without forcing users through hidden normalization.

#### D. `fuzzy.schema`

- first-class Pydantic support,
- dataclass-to-schema helper,
- TypedDict helper,
- enum and literal helpers,
- schema builder utilities for common cases.

The objective is simple: users should rarely need to hand-author raw JSON Schema.

#### E. `fuzzy.commands`

- `@command` decorator,
- command registry,
- schema inference where safe,
- docs generation for commands,
- validation helpers,
- dry-run inspection of command menus.

This should make `dispatch` one of Fuzzy's easiest primitives, not the heaviest.

#### F. Local testing primitives

- `MockAdapter` for deterministic unit tests,
- record-and-replay adapter for fixture-driven tests,
- fake transport error helpers,
- examples showing how to test business logic around Fuzzy without live model calls.

### Exit criteria

- First working example for each primitive in under 50 lines.
- Every documented example runs in CI.
- A user can define a schema or command without learning JSON Schema internals.
- A user can clearly choose between `context` and `messages` without guessing how the framework rewrites their evidence.

## 6. Phase 2: Trust Layer

### Goal

Make Fuzzy production-credible by default.

### Why this phase matters

Competing frameworks lose trust when the framework is doing a lot, but users cannot see why it failed.

Fuzzy should be the opposite: constrained, inspectable, and measurable.

### Deliverables

#### A. `fuzzy.trace`

- opt-in `return_trace=True` on all primitives,
- per-attempt validation failures,
- raw provider text,
- normalized schema metadata,
- provider request/response IDs when available,
- token and latency metadata when available,
- final validation category,
- command selection and execution metadata for `dispatch`.

#### B. Trace storage and viewing

- JSON-serializable trace format,
- file sink and callback hooks,
- minimal local HTML trace viewer,
- redaction support for sensitive fields.

This should be local-first. SaaS should not be required to debug Fuzzy.

#### C. `fuzzy.evals`

- fixture-driven classification evals,
- extraction validity evals,
- dispatch accuracy evals,
- model comparison runs,
- prompt variant runs,
- retry-rate and validation-exhaustion metrics,
- confusion matrix and per-case trace links.

#### D. CI integration

- pytest helpers,
- snapshot or golden-fixture workflows,
- threshold assertions,
- regression reports suitable for PR review.

### Exit criteria

- A team can answer "what failed, on which attempt, and why?" in one step.
- A prompt or model change can be gated in CI with measurable pass/fail thresholds.

## 7. Phase 3: Flagship Utility

### Goal

Solve common operational workflows out of the box while keeping the core explicit.

### Why this phase matters

Users do not adopt libraries because the primitives are beautiful. They adopt them because a known business workflow becomes easier to ship.

### Deliverables

#### A. `fuzzy.recipes`

Ship 4 first-party recipes:

- support triage,
- lead qualification,
- document completeness,
- approval router.

Each recipe should include:

- typed input contract,
- typed output contract,
- default prompts,
- default schemas,
- eval fixtures,
- example service integration,
- failure and escalation guidance.

#### B. Reference applications

- FastAPI service example,
- Django integration example,
- worker or queue integration example,
- example approval workflow using `dispatch(..., auto_execute=False)`,
- conversation-style input example using `messages`,
- mixed text + JSON evidence example.

### Exit criteria

- A team can ship one real workflow with 20-100 lines of glue code.
- Recipes feel like accelerators, not alternate frameworks.

## 8. Phase 4: Portability And Scale

### Goal

Expand addressable adoption without changing the abstraction.

### Why this phase is not earlier

More adapters do not fix onboarding or trust. They matter after the product is easy to adopt and easy to trust.

### Deliverables

#### A. More adapters

Priority order:

1. Azure OpenAI
2. Anthropic
3. Gemini
4. local OpenAI-compatible endpoints

#### B. Batch and policy controls

- bulk classify and extract,
- concurrency controls,
- rate-limit aware retry hooks,
- fallback model policies,
- cost accounting hooks,
- budget limits per batch or run.

#### C. Safer execution controls

- approval hooks before command execution,
- allow-list and deny-list policies for commands,
- command timeout handling,
- simulator mode for `dispatch`,
- execution audit records.

### Exit criteria

- Fuzzy can serve enterprise portability needs without expanding into an orchestration platform.
- Fuzzy can handle high-volume decision workloads with predictable behavior.

## 9. Phase 5: Ecosystem Expansion

### Goal

Capture repeat use cases without bloating the core package.

### Deliverables

#### A. Optional domain packs

- `fuzzy-support`
- `fuzzy-crm`
- `fuzzy-compliance`
- `fuzzy-intake`

#### B. Pack template and quality bar

Every pack must include:

- recipe wrappers,
- prompts,
- schemas,
- command definitions,
- eval fixtures,
- version compatibility declaration.

#### C. Community contribution model

- recipe contribution guide,
- pack maintenance policy,
- acceptance criteria based on tests and eval coverage.

### Exit criteria

- The ecosystem grows through focused packs, not core-package sprawl.

## 10. Release Plan

### Release A: Trustworthy First Use

Ship:

- contract hardening,
- docs overhaul,
- typed input contract,
- `fuzzy.schema`,
- `fuzzy.commands`,
- `MockAdapter`,
- record-and-replay testing support.

Reason:

- This is the highest leverage release for adoption.
- It removes the biggest "I can probably just write this myself" objection.

### Release B: Debugging And Evals

Ship:

- `fuzzy.trace`,
- local trace viewer,
- `fuzzy.evals`,
- pytest integration,
- regression reports.

Reason:

- This is the release that makes Fuzzy production-credible.

### Release C: Flagship Workflows

Ship:

- `fuzzy.recipes`,
- 4 flagship recipes,
- reference service examples.

Reason:

- This turns Fuzzy from a strong primitive library into a repeatable adoption path.

### Release D: Portability And Scale

Ship:

- Azure OpenAI, Anthropic, Gemini, and local-compatible adapters,
- batch execution,
- fallback policies,
- approval and audit hooks,
- cost controls.

Reason:

- This expands enterprise fit after the product story is already coherent.

### Release E: Domain Packs

Ship:

- 1-2 optional domain packs,
- pack template and contribution guide.

Reason:

- This captures vertical value without turning the core into a platform.

## 11. What To Explicitly Not Build

Do not build:

- drag-and-drop flow builder,
- long-running agent runtime,
- memory system,
- multi-agent coordination layer,
- hosted control plane as the primary product,
- automatic prompt optimizer that hides the final behavior,
- giant integrations marketplace before the core is mature.

These are attractive distractions because they look like expansion. In practice they would blur the product boundary and weaken the moat.

## 12. Success Metrics

### Adoption metrics

- Time to first successful production-like use case
- Number of weekly installs reaching example completion
- Number of services using Fuzzy in CI
- Recipe adoption rate

### Reliability metrics

- Validation exhaustion rate
- Retry rate
- Schema-valid output rate
- Command argument validity rate
- Eval coverage per recipe

### Product quality metrics

- Docs task completion rate
- Example pass rate in CI
- API breakage incidents per release
- Median time to root-cause a failed call using traces

## 13. Final Product Rule

Every roadmap item must answer this question:

"Does this make a constrained LLM decision easier to adopt, easier to inspect, easier to evaluate, or easier to reuse inside normal application code?"

If the answer is no, it should not be on the roadmap.
