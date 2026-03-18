# Remaining Roadmap Retry Plan

## Scope And Source Of Truth

This plan covers all roadmap items after Release A using `fuzzy_roadmap.md`, `fuzzy_product_spec.md`, and `SAD.md` as the governing product and architecture documents for this retry run.

It is implementation-oriented and reflects the repository state observed on 2026-03-18 rather than assuming the post-Release-A roadmap is still entirely future work.

## Verified Baseline In Repository

Release A baseline already present and treated as complete for this run:
- `system_prompt` plus exactly one of `context` or `messages`
- provider-neutral ordered `Message` input with `text` and `json` parts
- adapter consumption of ordered messages
- `drop` removed from the top-level public package surface

Post-Release-A slices already present in the repository and therefore treated as baseline for planning:
- Release B trust-layer substrate exists:
  - [`fuzzy/trace.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/trace.py)
  - [`fuzzy/evals.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/evals.py)
  - trace-aware primitive/wrapper support in [`fuzzy/core.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/core.py) and [`fuzzy/ops.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/ops.py)
- Release C partial utility slice exists:
  - [`fuzzy/recipes/`](/home/marcelo/code/docloop/Fuzzy/fuzzy/recipes)
  - three flagship recipes instead of the roadmap target of 3-4 plus partial example integrations in [`examples/`](/home/marcelo/code/docloop/Fuzzy/examples)
- Regression coverage exists and is currently green:
  - `pytest -q` passed with `64 passed, 1 skipped`

## Product Guardrails

All remaining work must preserve these invariants from the spec and SAD:
- keep the core semantic surface small
- keep outputs typed and locally validated
- keep instruction/evidence boundaries explicit
- keep orchestration explicit and code-first
- do not introduce agent runtimes, memory, workflow UIs, hidden optimization layers, or platform control planes

## Request-Aligned Planning Interpretation

The retry request asks for:
- a complete end-to-end plan for all remaining roadmap work
- implementation of the next coherent milestones in roadmap order
- preference for a strong Release B foundation plus coherent Release C slices over shallow Phase 4/5 stubs

Because Release B and part of Release C are already present in the repository, this retry plan treats them as implemented baseline where verified, identifies the remaining gaps inside Release C, and then plans Phase 4 and Phase 5 concretely without inventing empty modules.

## Codebase Findings That Drive The Plan

- [`fuzzy/core.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/core.py) remains the single critical seam for retries, validation, trace capture, and dispatch execution. Future batch/fallback/policy controls should layer around or through this seam rather than duplicating primitive logic.
- [`fuzzy/adapters.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/adapters.py) currently ships only `OpenAIAdapter` and `OpenRouterAdapter`. No Phase 4 portability work is implemented yet beyond that.
- [`fuzzy/trace.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/trace.py) already provides typed attempt records, JSON persistence, HTML rendering, and redaction. The trust-layer plan should therefore focus on hardening and integration rather than reintroducing the same feature.
- [`fuzzy/evals.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/evals.py) already provides fixture-driven eval runners, report serialization, threshold assertions, and matrix execution. CI helper work should extend from this surface rather than create a parallel evaluation mechanism.
- [`fuzzy/recipes/`](/home/marcelo/code/docloop/Fuzzy/fuzzy/recipes) provides support triage, lead qualification, and approval routing. The roadmap gap is not “recipes absent”; it is “one recipe short of the 3-4 target, limited reference integrations, and no broader ecosystem scaffolding.”
- The repository is still compact. That favors shipping vertical, well-tested slices instead of introducing many package-level placeholders.

## Current Gap Map Against Remaining Roadmap

### Release B / Trust Layer

Implemented and verified:
- `fuzzy.trace`
- local JSON and HTML trace viewing
- `fuzzy.evals`
- threshold assertions and report export suitable for CI artifacts

Remaining gaps:
- no dedicated pytest plugin/helper module; current CI support is library-level only
- no golden fixture helper workflow beyond generic suite loading and report writing
- no explicit per-case trace-link manifest for CI/PR review beyond embedded serialized traces
- no documented redaction policy presets or trace-storage directory conventions

### Release C / Flagship Utility

Implemented and verified:
- `fuzzy.recipes`
- three flagship recipes:
  - support triage
  - lead qualification
  - approval routing
- lightweight reference integrations:
  - FastAPI-style example
  - Django-style example

Remaining gaps:
- fourth flagship recipe not yet shipped
- no worker/queue integration example
- no document-completeness recipe, which is the best fit for the missing fourth recipe based on roadmap use cases
- recipe docs/examples are code-only; no contribution standard for adding more recipes yet

### Phase 4 / Portability And Scale

Not implemented yet:
- more first-party adapters
- batch execution
- fallback model policies
- approval and audit hooks as reusable framework surfaces
- runtime cost controls

### Phase 5 / Ecosystem Expansion

Not implemented yet:
- optional domain-pack structure
- pack template / contribution scaffolding
- eval-backed contribution standards

## Delivery Strategy For The Retry Run

### Priority Order

1. Finish the remaining coherent Release C slice.
2. Implement the first non-speculative Phase 4 foundation that composes cleanly with the current core.
3. Document the rest of Phase 4 and all of Phase 5 as concrete deferred milestones if they cannot be landed coherently in one pass.

### Why This Order

- Release B is already in place and tested.
- The roadmap explicitly prefers a strong Release B foundation plus coherent Release C slices over speculative later stubs.
- The smallest high-value remaining roadmap step is to complete Release C with a fourth recipe and the missing reference integration slice.
- Phase 4 should begin only where the current codebase has a clear architectural seam and where the result remains explicit and typed.

## Implementation Milestones

### Milestone C3: Complete The Flagship Recipe Set

Goal:
- finish Release C by shipping the missing fourth first-party recipe and aligning recipe fixtures/examples around it

Scope:
- add one fourth flagship recipe under [`fuzzy/recipes/`](/home/marcelo/code/docloop/Fuzzy/fuzzy/recipes)
- preferred recipe: `document_completeness`

Why this recipe:
- it is explicitly called out in the roadmap/product-spec use cases
- it composes naturally from existing `extract`, `eval_bool`, and `dispatch` semantics
- it expands utility without requiring external systems or widening the core API

Concrete deliverables:
- typed input contract for document package evidence
- typed output contract covering completeness decision, missing fields/items, risk or escalation indicator, and next action
- default schema and prompts
- bundled eval fixture suite in [`fuzzy/recipes/fixtures.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/recipes/fixtures.py)
- tests mirroring the existing recipe test style
- export from [`fuzzy/recipes/__init__.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/recipes/__init__.py)

Interfaces:
- recipe entrypoint:
  - `assess_document_completeness(...)` or equivalent explicit name
- recipe trace contract:
  - reuse existing `RecipeRun`, `RecipeStepTrace`, `trace_sink`, and `return_trace`

Risk controls:
- keep the recipe as thin composition over existing primitives
- do not introduce a generic recipe framework
- do not add external file-processing or OCR abstraction; accept already-prepared text/JSON evidence only

Acceptance checks:
- deterministic tests with fake adapters
- eval fixture pass using `run_extraction_eval(...)` or task-appropriate runner
- recipe exports remain narrow and explicit

### Milestone C4: Finish Reference Integration Coverage

Goal:
- satisfy the roadmap’s “reference service integrations” more completely without shipping a framework-specific sample app

Scope:
- add one worker/queue-style example
- extend example coverage to show conversation-style `messages` evidence or mixed text+JSON evidence where the recipe benefits from it

Concrete deliverables:
- new lightweight example under [`examples/`](/home/marcelo/code/docloop/Fuzzy/examples)
- example stays dependency-free and demonstrates application integration shape only

Risk controls:
- no new runtime dependencies
- no executable service scaffold
- examples remain illustrative and testable as plain Python modules if needed

Acceptance checks:
- import-smoke or focused example tests if example logic becomes non-trivial

### Milestone P4-1: Batch Execution Foundation

Goal:
- add explicit, typed bulk execution for homogeneous workloads without changing primitive semantics

Why this first in Phase 4:
- it uses current primitives directly
- it does not require provider-specific transport work
- it composes naturally with traces/evals already in the repository

Scope:
- introduce batch helpers above the primitive level, not inside adapters as the first implementation
- support repeated classification/extraction/dispatch calls with bounded concurrency and aggregated reporting

Preferred module:
- new module such as `fuzzy/batch.py` or a narrowly named equivalent

Concrete interface:
- `BatchCall` typed record or mapping
- `BatchResult` / `BatchReport` typed result
- `run_batch(calls, *, concurrency: int = ..., return_traces: bool = False, stop_on_error: bool = False)`

Required behavior:
- each call preserves its own validation/error boundary
- traces remain per-call, never merged into hidden summaries only
- concurrency is explicit and local
- no queueing system, persistence layer, or provider-native batch API required in the first slice

Tests:
- deterministic batch success path
- mixed success/failure path
- trace aggregation path
- concurrency limit behavior if implemented with async semaphore control

Risk controls:
- do not add hidden retry layers beyond existing per-call retries
- keep memory bounded when `return_traces=True`
- avoid speculative abstraction for heterogeneous workflow orchestration

### Milestone P4-2: Fallback Model Policy Surface

Goal:
- allow explicit model fallback decisions while keeping provenance visible

Scope:
- define an explicit fallback policy object or callback
- support per-call or `LLMOps`-level override
- record model-switch decisions in traces

Concrete interface:
- `FallbackPolicy`
- receives operation, current model, attempt number, and failure category
- returns next action:
  - retry same model
  - switch to fallback model
  - stop

Architecture constraints:
- fallback remains opt-in
- trace must record attempted model sequence
- policy cannot suppress validation or change typed result contracts

Dependency note:
- this milestone depends on the batch/foundation work only conceptually, not structurally

Major risk:
- accidental hidden behavior if fallback is applied automatically through adapters

Implementation rule:
- keep policy evaluation in core orchestration, not inside adapter implementations

### Milestone P4-3: Approval And Audit Hooks

Goal:
- add safer execution controls for dispatch-heavy workflows without drifting into an orchestration platform

Scope:
- explicit approval hook before command execution
- explicit audit record emission for command decisions/executions
- allow-list / deny-list hooks for commands
- optional simulation mode for `dispatch`

Concrete interface:
- `approval_hook(decision, trace) -> approved | rejected | replacement decision`
- `audit_sink(audit_record) -> None`
- optional `simulate=True` or equivalent on dispatch-related helper surfaces

Architecture constraints:
- hooks are opt-in and explicit per call or wrapper
- no hidden human workflow engine
- command execution still happens at most once
- rejected approvals are terminal results, not silent retries

Tests:
- approval denied before executor invocation
- audit record emitted on successful execution
- simulated mode skips executor side effects but returns the decision

Risk controls:
- preserve the current dispatch contract
- keep audit records JSON-serializable and local-first

### Milestone P4-4: Runtime Cost Controls

Goal:
- let callers account for and bound runtime spend explicitly

Scope:
- normalize token/cost metadata from adapter responses when available
- expose cost/accounting hooks at trace/batch/report layers
- add optional budget limit for batch runs or explicit call groups

Concrete interface:
- `CostRecord`
- `cost_sink`
- optional `budget_limit` for batch/report helpers

Dependency note:
- useful only after batch reporting and richer provider metadata normalization are in place

Risk controls:
- do not infer fake cost values when providers omit usage metadata
- keep budgeting as caller-supplied policy, not a hidden global limiter

### Milestone P4-5: More First-Party Adapters

Goal:
- expand portability after the trust and utility story is coherent

Priority order for this repository:
1. local OpenAI-compatible endpoint support by parameterizing existing OpenAI adapter usage where feasible
2. Azure OpenAI
3. Anthropic
4. Gemini

Reason for adjusted order:
- the roadmap lists Azure/Anthropic/Gemini/local-compatible, but this repository already has an OpenAI-style adapter with configurable `base_url`, making local compatibility the cheapest coherent portability win

Adapter contract requirements:
- preserve the normalized request envelope from [`fuzzy/adapters.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/adapters.py)
- preserve local JSON parsing/validation
- preserve instruction/evidence boundary semantics
- surface provider metadata without changing primitive return types

Tests:
- request-mapping tests using fake HTTP payloads
- provider-category mapping tests
- metadata extraction tests

Risk controls:
- no provider-specific prompt semantics leak into public APIs
- reject unsupported modalities before provider calls

## Phase 5 Plan: Ecosystem Expansion Without Core Sprawl

### Milestone E1: Optional Domain-Pack Layout

Goal:
- define a clean packaging boundary for vertical value outside the core package

Scope:
- specify naming/layout conventions for packs such as:
  - `fuzzy-support`
  - `fuzzy-crm`
  - `fuzzy-compliance`
  - `fuzzy-intake`

Required structure for each pack:
- recipe wrappers
- prompts
- schemas
- command definitions
- eval fixtures
- compatibility declaration against core Fuzzy versions

Implementation constraint:
- do not move first-party core recipes out of `fuzzy.recipes` yet; Phase 5 starts with scaffolding, not package fragmentation

### Milestone E2: Pack Template And Contribution Scaffolding

Goal:
- make new packs/reipes repeatable without weakening quality

Scope:
- template directory or cookiecutter-free simple scaffold
- contribution guide
- checklists for prompts, schemas, fixtures, and examples

Concrete deliverables:
- `templates/` or `contrib/` skeleton
- author checklist covering tests, eval coverage, and version compatibility

Risk controls:
- keep templates minimal and repo-native
- avoid introducing new project generators or build tools

### Milestone E3: Eval-Backed Contribution Standards

Goal:
- require measurable quality for new recipes/packs

Scope:
- define minimum test and eval expectations for contributed recipes/packs
- standardize threshold assertions for pack acceptance

Concrete standards:
- each contributed recipe must ship:
  - deterministic unit tests
  - at least one eval fixture suite
  - minimum pass-rate threshold definition
  - trace compatibility

Dependency note:
- this milestone depends on the existing `fuzzy.evals` surface and any CI-helper hardening from Release B follow-through

## Recommended Implementation Boundary For This Run

Implement in this run, in order:
1. Milestone C3: fourth flagship recipe
2. Milestone C4: missing worker/queue reference integration
3. Milestone P4-1: batch execution foundation if it fits cleanly after C3/C4

Defer unless the implementation remains small and coherent:
- P4-2 fallback policy
- P4-3 approval/audit hooks
- P4-4 runtime cost controls
- P4-5 more adapters
- all Phase 5 scaffolding

## File-Level Change Guidance For Implement Phase

Likely touch points for the next coherent slice:
- [`fuzzy/recipes/`](/home/marcelo/code/docloop/Fuzzy/fuzzy/recipes) for the fourth recipe
- [`fuzzy/recipes/fixtures.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/recipes/fixtures.py) for eval fixtures
- [`tests/test_recipes.py`](/home/marcelo/code/docloop/Fuzzy/tests/test_recipes.py) for recipe coverage
- [`examples/`](/home/marcelo/code/docloop/Fuzzy/examples) for the worker/queue-style integration example

Likely touch points if P4-1 is included:
- new batch module under [`fuzzy/`](/home/marcelo/code/docloop/Fuzzy/fuzzy)
- [`fuzzy/__init__.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/__init__.py) only if the batch API is intentionally public
- new focused batch tests under [`tests/`](/home/marcelo/code/docloop/Fuzzy/tests)

## Risk Register

### RR-001: Hidden platform drift

Risk:
- Phase 4 controls could turn into orchestration/runtime behavior that violates the product thesis

Control:
- keep all new features opt-in, local-first, and code-level
- reject any design that introduces background state, hosted coordination, or implicit execution

### RR-002: Core API sprawl

Risk:
- too many top-level exports dilute the narrow semantic core

Control:
- keep new roadmap layers in dedicated modules
- expose only the minimum intentional public APIs

### RR-003: Duplicate instrumentation paths

Risk:
- batch/fallback/audit work could bypass existing trace/eval seams and create inconsistent observability

Control:
- reuse `TraceRecord`, `TraceResult`, `trace_sink`, and eval report surfaces
- route new policy decisions through existing operation/attempt accounting where possible

### RR-004: Recipe framework overreach

Risk:
- completing Release C could accidentally become a generic DSL or recipe runtime

Control:
- each recipe remains a thin explicit function
- no prompt registries, runtime recipe graph, or hidden planner layer

### RR-005: Provider portability leakage

Risk:
- new adapters/fallback logic could leak provider-specific semantics into the public contract

Control:
- keep provider differences inside adapters
- preserve local validation and normalized request/response handling

### RR-006: Dirty worktree regression risk

Risk:
- the repository already contains unrelated dirty files from earlier work

Control:
- implementation should touch only request-relevant files
- do not revert unrelated changes
- validate with targeted tests plus full-suite regression checks

## Verification Requirements For Implement Phase

Minimum verification for the next implementation pass:
- targeted tests for every new module/function added
- `pytest -q`
- if new example modules become non-trivial, import/smoke verification for those examples

If P4-1 batch work lands, also verify:
- deterministic mixed-result batch tests
- trace aggregation serialization behavior

## Definition Of Success For This Retry Run

This retry run is successful if the implementation phase:
- completes the remaining Release C gap coherently
- optionally lands one small, explicit Phase 4 foundation slice without violating the product thesis
- keeps deferred Phase 4/5 work documented concretely rather than implied by placeholders
- preserves internal consistency and a green test suite
