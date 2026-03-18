# Remaining Roadmap Plan

## Scope And Baseline

This plan covers all roadmap items after Release A using [fuzzy_roadmap.md](/home/marcelo/code/docloop/Fuzzy/fuzzy_roadmap.md), [fuzzy_product_spec.md](/home/marcelo/code/docloop/Fuzzy/fuzzy_product_spec.md), and [SAD.md](/home/marcelo/code/docloop/Fuzzy/SAD.md) as the source of truth.

Assumed baseline already present in the repository:
- Release A input contract has landed: `system_prompt` plus exactly one of `context` or `messages`.
- Provider-neutral `Message` support already exists for `text` and `json`.
- Adapters already consume ordered messages.
- `drop` is no longer on the top-level public surface.

Current repository constraints that shape the plan:
- The codebase is intentionally small: `fuzzy/core.py` owns the request envelope, retry loop, validation flow, and dispatch execution path.
- `fuzzy/adapters.py` currently ships only `OpenAIAdapter` and `OpenRouterAdapter`.
- Tests are concentrated in `tests/test_fuzzy.py`, so new areas should stay local-first and testable without adding a large harness.
- The worktree is already dirty in baseline files; this plan avoids assuming those unrelated changes should be reverted.

Planning principle for this run:
- Plan the full remaining roadmap end to end.
- Implement the next coherent milestones in roadmap order.
- Prefer a complete Release B foundation plus a small Release C slice over partial scaffolding for every later phase.

## Product Guardrails

Every milestone in this plan must preserve these invariants:
- Keep the core semantic surface small; new features should layer around existing primitives instead of replacing them.
- Keep outputs typed and locally validated.
- Keep instruction and evidence boundaries explicit; traces and eval fixtures must record evidence, not invent hidden prompt state.
- Keep orchestration explicit and code-first.
- Do not introduce agent runtimes, hidden workflow engines, persistent memory, or UI-first control planes.

## Codebase Findings That Inform The Plan

- The main extension seam is `_run_model_operation(...)` in [fuzzy/core.py](/home/marcelo/code/docloop/Fuzzy/fuzzy/core.py). Tracing, metrics capture, and eval hooks should hang off this request/attempt lifecycle instead of duplicating primitive logic.
- Dispatch already has a normalized command path with post-selection execution and validation. That makes dispatch-heavy recipes feasible without new execution machinery.
- Adapters already expose `provider_response_id` and return raw text, but they do not yet expose normalized provider metadata like token usage or latency.
- The public surface is still narrow enough that new modules can remain optional: `fuzzy.trace`, `fuzzy.evals`, and `fuzzy.recipes` can be additive packages with minimal changes to current primitive signatures.

## Delivery Strategy

### This Run Target

Implement the next coherent slices in this order:
1. Release B foundation: tracing data model, opt-in trace return, trace sinks, and local JSON/HTML viewing.
2. Release B evaluation foundation: fixture-driven eval runners plus pytest-friendly regression helpers.
3. Release C narrow utility slice: `fuzzy.recipes` package with 2-3 flagship recipes if they can be shipped end to end on top of traces/evals in the same pass.

Later roadmap items stay fully planned below, but they are deferred unless they can be added without fragmenting the design.

### Sequencing Rule

No later-phase feature should land before Release B produces:
- one stable trace object,
- one local viewing path,
- one reusable eval fixture format,
- one regression helper path suitable for tests and CI.

## Milestone Plan

### Milestone B1: Core Trace Substrate

Goal:
- Make every primitive call inspectable without changing its decision semantics.

Deliverables:
- New `fuzzy.trace` module containing typed trace records for call-level and attempt-level metadata.
- Opt-in `return_trace=True` support on `eval_bool`, `classify`, `extract`, `dispatch`, and matching `LLMOps` methods.
- Trace capture for:
  - operation name,
  - model,
  - normalized messages,
  - effective instructions,
  - attempt count,
  - raw provider text per attempt,
  - validation failures per attempt,
  - final result shape,
  - provider response ID when available,
  - command selection and command execution metadata for `dispatch`,
  - optional adapter metadata such as token counts and latency when available.
- Backward-compatible default behavior: existing callers still receive the original primitive return values when `return_trace` is omitted or false.

Interface definition:
- Add `TraceAttempt` and `TraceRecord` typed structures.
- Add `TraceResult[T]` shape:
  - `value: T`
  - `trace: TraceRecord`
- Primitive signature addition:
  - `return_trace: bool = False`
- Return contract:
  - if `return_trace=False`, return the existing `T`
  - if `return_trace=True`, return `TraceResult[T]`

Implementation notes:
- Build traces inside `_run_model_operation(...)` so all primitives share one attempt capture path.
- Keep trace collection opt-in to avoid unexpected payload retention or overhead.
- Do not change validation rules or retry behavior.

Tests:
- Unit tests for each primitive showing unchanged default returns.
- Trace tests for success, validation exhaustion, provider failures, and dispatch execution failures.
- Adapter tests for metadata passthrough when present and graceful absence when missing.

### Milestone B2: Trace Storage, Redaction, And Local Viewing

Goal:
- Make trace inspection local-first and file-based.

Deliverables:
- JSON-serializable trace export helpers in `fuzzy.trace`.
- File sink utility that writes trace JSON to a directory tree with deterministic filenames.
- Callback hook support so callers can capture traces without binding to file storage.
- Redaction helper that removes or masks configured JSON paths before persistence or rendering.
- Minimal local HTML trace viewer generated from stored trace JSON, with no server requirement.

Interface definition:
- `TraceSink` protocol or callable contract: accepts `TraceRecord`.
- Per-call optional hook:
  - `trace_sink: TraceSink | None = None`
- Utility helpers:
  - `save_trace(trace, path_or_dir, *, redact=None) -> Path`
  - `render_trace_html(trace_or_path, *, redact=None) -> str`
  - `write_trace_html(trace_or_path, output_path, *, redact=None) -> Path`

Implementation notes:
- Keep the viewer static and small: single-file HTML with embedded JSON is sufficient.
- Redaction should run before file writes and before HTML rendering.
- Avoid introducing a web app or persisted database.

Tests:
- JSON serialization round-trip.
- File sink writes and redaction behavior.
- HTML render smoke tests that assert key sections exist.

### Milestone B3: `fuzzy.evals` Foundation

Goal:
- Let teams evaluate prompt or model changes locally using stable fixtures and trace outputs.

Deliverables:
- New `fuzzy.evals` package with fixture-driven runners for:
  - classification accuracy,
  - extraction validity,
  - dispatch decision accuracy.
- Shared eval fixture schema that references primitive type, input evidence, expected result, and optional notes/tags.
- Runner outputs with summary metrics and per-case results linked to traces.
- Model comparison and prompt variant execution support via explicit run matrices.

Interface definition:
- Fixture types:
  - `EvalCase`
  - `EvalSuite`
- Runner entrypoints:
  - `run_classification_eval(...)`
  - `run_extraction_eval(...)`
  - `run_dispatch_eval(...)`
  - `run_eval_matrix(...)`
- Result types:
  - `EvalCaseResult`
  - `EvalSummary`
  - `EvalReport`

Minimum metrics for first release:
- total cases,
- pass rate,
- accuracy for label/decision tasks,
- schema validity rate for extraction,
- retry rate,
- validation exhaustion count,
- optional confusion matrix for classification/dispatch label mode.

Implementation notes:
- Reuse `return_trace=True` so evals do not invent a separate instrumentation path.
- Keep fixture format JSON-first and repository-friendly.
- Do not attempt hosted dashboards or long-lived run stores.

Tests:
- Deterministic eval tests using fake adapters.
- Matrix tests for prompt/model comparison.
- Report serialization tests.

### Milestone B4: Regression And CI Helpers

Goal:
- Make evals usable in ordinary test suites and pull request checks.

Deliverables:
- Pytest helper assertions for threshold gating.
- Golden fixture helpers for snapshot-style regression workflows.
- Machine-readable and human-readable report export suitable for CI artifacts.
- Simple diff output for regression review.

Interface definition:
- `assert_eval_thresholds(report, *, min_pass_rate=..., max_retry_rate=..., ...)`
- `load_eval_suite(path)`
- `write_eval_report(report, path)`

Implementation notes:
- Keep helpers library-level rather than introducing a CLI in the first pass unless needed for test ergonomics.
- CI outputs should be plain JSON and markdown so they work in any pipeline.

Tests:
- Threshold assertion pass/fail tests.
- Golden fixture loading and report writing tests.

### Milestone C1: `fuzzy.recipes` Package

Goal:
- Ship opinionated, useful workflows without widening the core into an agent platform.

Deliverables:
- New `fuzzy.recipes` package containing recipe modules that compose existing primitives explicitly.
- Each recipe includes:
  - typed input contract,
  - typed output contract,
  - default prompts,
  - default schema or command set,
  - escalation guidance,
  - eval fixtures,
  - trace support by default.

Recipe selection rule for this repository:
- Prioritize recipes that can be implemented with the current primitives and no external service dependencies.
- Recommended first set for this run:
  - support triage,
  - lead qualification,
  - approval router.
- Document completeness is a valid fourth recipe, but only ship it if the first three are complete and tested.

Interface definition:
- Recipe modules expose explicit functions or lightweight classes, for example:
  - `triage_support_request(...)`
  - `qualify_lead(...)`
  - `route_approval(...)`
- Recipe parameters accept:
  - `adapter`,
  - `model`,
  - typed evidence input,
  - optional overrides for prompts/labels/commands,
  - optional trace/eval hooks.

Implementation notes:
- Recipes should be thin compositions over `classify`, `extract`, and `dispatch`.
- Keep recipe defaults inspectable in code; no hidden prompt registry.
- Package recipe fixtures with the repository so evals can exercise them directly.

Tests:
- Happy-path recipe tests.
- Escalation or invalid-output tests.
- Eval fixtures proving baseline regression coverage for each shipped recipe.

### Milestone C2: Reference Service Integrations

Goal:
- Show how recipes plug into normal application code.

Deliverables:
- Minimal reference integrations, preferably examples or tests rather than a full sample app:
  - FastAPI-style handler example,
  - simple Django-style service function example.

Implementation notes:
- Keep these as lightweight examples under `tests/` or an `examples/` folder.
- Do not introduce framework dependencies into the core package unless clearly isolated as optional.

Tests:
- Example smoke tests if examples become executable code.

### Milestone P4-1: More First-Party Adapters

Goal:
- Expand provider portability without coupling the architecture to provider quirks.

Planned scope:
- Add one more adapter only if it fits the current request contract cleanly.
- Candidate order:
  - Anthropic-style messages API,
  - Google Gemini-style content API,
  - local OpenAI-compatible endpoint support as a low-friction option.

Interface constraints:
- Any new adapter must consume the same normalized request envelope from `_run_model_operation(...)`.
- Local validation remains mandatory even when provider structured output exists.
- Unsupported modalities must fail before provider calls.

Deferred by default for this run:
- New adapters are lower priority than traces/evals unless needed to validate portability seams.

### Milestone P4-2: Batch Execution

Goal:
- Run many homogeneous cases efficiently while preserving explicitness.

Planned scope:
- Batch helpers live above the primitives, not inside adapters first.
- Introduce a local batch runner that executes a list of independent primitive calls and aggregates traces and metrics.
- Provider-native batch APIs remain optional adapter-specific optimizations for later.

Interface definition:
- `run_batch(calls, *, concurrency=..., return_traces=False) -> BatchReport`

Risks to manage:
- preserving per-call error boundaries,
- avoiding hidden retries or queue semantics,
- keeping memory usage bounded when traces are enabled.

Deferred by default for this run.

### Milestone P4-3: Fallback Model Policies

Goal:
- Allow explicit secondary model fallback without hiding decision provenance.

Planned scope:
- Add optional policy objects that decide whether to retry on the same model, switch models, or stop.
- Policy decisions must be recorded in traces.

Interface definition:
- `FallbackPolicy` object supplied explicitly per call or through `LLMOps`.
- Policy can inspect operation, attempt number, and failure category.

Non-goal:
- no hidden auto-optimization or model routing heuristics.

Deferred by default for this run because it depends on the trace substrate.

### Milestone P4-4: Approval And Audit Hooks

Goal:
- Support audit-sensitive flows without building a workflow engine.

Planned scope:
- Pre-execution approval hooks for `dispatch(..., auto_execute=True)`.
- Audit callback that receives final decision and trace summary.

Interface definition:
- `approval_hook(decision, trace) -> approved | raises`
- `audit_hook(record) -> None`

Constraints:
- Hooks remain synchronous library callbacks in first release.
- Fuzzy must not own queueing, inboxes, or human task state.

Deferred by default for this run.

### Milestone P4-5: Runtime Cost Controls

Goal:
- Make spending boundaries explicit.

Planned scope:
- Per-call cost budget hooks based on adapter metadata when available.
- Hard caps on attempts, optional token ceilings, and report-time cost summaries.

Dependencies:
- adapter metadata normalization in traces,
- fallback policy design.

Deferred by default for this run.

### Milestone P5-1: Optional Domain Packs

Goal:
- Allow optional higher-level vertical utilities without bloating the base package.

Planned scope:
- Keep `fuzzy.recipes` first-party and generic.
- Introduce optional pack structure only after generic recipe patterns stabilize.

Structure proposal:
- base package remains `fuzzy`
- optional packs use separate namespaces or distributions such as `fuzzy_pack_support`

Deferred by default for this run.

### Milestone P5-2: Pack Template And Contribution Scaffolding

Goal:
- Make external contributions consistent and low-friction.

Planned scope:
- Template with:
  - recipe contract,
  - fixture layout,
  - trace expectations,
  - eval baseline,
  - docs checklist.

Deferred by default for this run.

### Milestone P5-3: Eval-Backed Contribution Standards

Goal:
- Require new recipes/packs to ship with measurable quality controls.

Planned scope:
- Contribution standard requiring:
  - fixture suite,
  - threshold assertions,
  - trace examples for failure cases.

Deferred by default for this run, but the standards should be enabled by B3 and B4 outputs.

## Shared Interface Decisions

These decisions keep the roadmap coherent across milestones:

### Trace And Eval Reuse

- Traces are the single observability artifact.
- Eval reports link to or embed traces rather than creating a second failure format.
- Regression helpers consume eval reports, not raw primitive outputs.

### Optional Feature Surface

- New capability remains opt-in:
  - `return_trace`,
  - `trace_sink`,
  - eval runner imports,
  - recipe imports.
- Existing primitive behavior remains stable for current callers.

### Typed Structures Over Hidden DSLs

- Prefer Python dataclasses or `TypedDict` contracts for traces, eval cases, and recipe IO.
- Avoid YAML-heavy or runtime-generated configuration systems.

### Local-First Artifacts

- Persist traces and eval reports as JSON and markdown.
- HTML viewing is generated locally from saved traces.
- CI integration is file-based.

## File And Module Plan

Recommended module additions, assuming implementation proceeds:
- `fuzzy/trace.py`
- `fuzzy/evals.py` or `fuzzy/evals/__init__.py` plus focused submodules if needed
- `fuzzy/recipes/__init__.py`
- `fuzzy/recipes/support.py`
- `fuzzy/recipes/leads.py`
- `fuzzy/recipes/approval.py`
- optional `examples/` or recipe fixtures under `tests/fixtures/`

Likely touched existing modules:
- `fuzzy/core.py` for `return_trace`, `trace_sink`, and shared instrumentation
- `fuzzy/ops.py` for matching method support
- `fuzzy/types.py` for new typed public contracts
- `fuzzy/__init__.py` for carefully chosen exports
- `fuzzy/adapters.py` for optional metadata normalization
- `tests/test_fuzzy.py` plus new focused test modules if the single test file becomes too dense

## Test And Verification Plan

Required verification for the implementation phase:
- Preserve all existing primitive behavior with default parameters.
- Add trace coverage for each primitive and for dispatch execution paths.
- Add file-based trace persistence/view tests.
- Add eval fixture and threshold-helper tests.
- Add recipe tests and bundled eval fixtures for each shipped recipe.
- Run the full test suite after implementation.

Preferred test organization:
- Split by concern once new modules land:
  - `tests/test_trace.py`
  - `tests/test_evals.py`
  - `tests/test_recipes.py`
  - retain `tests/test_fuzzy.py` for core primitive and adapter behavior

## Risk Register

### Risk 1: Public API Drift

Issue:
- Adding trace support could accidentally change return types for existing callers.

Mitigation:
- Make trace return opt-in only.
- Keep the default return contract untouched.
- Add explicit compatibility tests for existing call patterns.

### Risk 2: Trace Payload Leakage

Issue:
- Traces may persist sensitive evidence or prompts.

Mitigation:
- Make sinks opt-in.
- Add redaction helpers before save/render.
- Document that in-memory traces still contain original evidence unless explicitly redacted.

### Risk 3: Instrumentation Duplicates Core Logic

Issue:
- Separate trace or eval codepaths could diverge from primitive behavior.

Mitigation:
- Instrument `_run_model_operation(...)` once.
- Reuse `return_trace=True` inside eval runners.

### Risk 4: Recipes Become A Hidden Framework

Issue:
- Recipes could grow internal orchestration layers or opaque defaults.

Mitigation:
- Implement recipes as thin compositions over current primitives.
- Keep prompts, labels, schemas, and commands visible in code.

### Risk 5: Provider Metadata Is Inconsistent

Issue:
- Token and latency data vary by adapter and may be absent.

Mitigation:
- Normalize metadata as optional fields.
- Do not make evals or cost controls depend on complete metadata in the first release.

### Risk 6: Eval Fixtures Become Too Abstract

Issue:
- A generic fixture DSL would add complexity without value in a small repository.

Mitigation:
- Start with primitive-specific fixture fields and one shared report shape.
- Expand only after real recipe coverage reveals common needs.

### Risk 7: Scope Sprawl Into Later Phases

Issue:
- Adapters, fallback, approval hooks, cost controls, and packs can fragment the run.

Mitigation:
- Treat Release B as the gate.
- Defer later phases unless they reuse B outputs directly and can be tested end to end.

## Deferred Work Summary

Planned but likely deferred beyond this run unless the implementation phase moves unusually fast:
- additional first-party adapters,
- batch execution,
- fallback model policies,
- approval and audit hooks,
- runtime cost controls,
- optional domain-pack structure,
- pack template and contribution scaffolding,
- formal eval-backed contribution standards document.

Deferral rationale:
- These areas depend on a stable trace/eval substrate or on recipe patterns that do not exist yet in the repository.
- Shipping them before Release B hardens would increase surface area faster than trust.

## Definition Of Success For This Plan

This plan is complete if the implementation phase:
- delivers at least one major post-Release-A area coherently, with Release B as the primary target,
- keeps the primitive surface explicit and backward-compatible by default,
- leaves later roadmap items documented with interfaces and sequencing rather than placeholders,
- preserves repository testability.
