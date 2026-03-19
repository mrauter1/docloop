# Superloop SAD: PRD Decomposition Into Coherent Phases

## 1. Document Control

- **Status**: Revised (post-review)
- **Scope**: `superloop.py` orchestration, `.superloop/tasks/<task-id>/` artifacts, and pair prompts
- **Feature**: First-class PRD decomposition that executes in coherent phases rather than one-shot implementation
- **Decision Date**: 2026-03-18

---

## 2. Context and Problem Statement

Superloop already supports a plan → implement → test loop with verifier gates, persistent task workspaces, and resumable runs. However, PRD-scale requests can still drift toward one-shot execution because decomposition is currently implicit and narrative-only.

Current behavior has three limitations:

1. The planning output is primarily freeform (`plan.md`) and lacks a required machine-readable decomposition contract.
2. Implement/test phases are not bound to an explicit active PRD phase boundary.
3. Granularity enforcement is currently indirect and can encourage overfitting to tooling checks.

The product requirement for this feature is to support **large, coherent implementation phases** while **not forcing micro-task granularity**, and to avoid heuristic granularity verification. The provider should be trusted to separate phases correctly when given precise planner and verifier instructions.

This revised SAD incorporates plan-review corrections:

1. Clarifies exactly where runtime and prompt changes land in `superloop.py` and task artifacts.
2. Makes phase execution semantics explicit for both fresh and resumed runs.
3. Reaffirms that decomposition quality is enforced by planner/verifier instructions and reviewer judgment, **not** heuristic scoring.

---

## 3. Goals

1. Represent PRD decomposition explicitly as an ordered phase plan artifact.
2. Execute implementation and testing against a selected phase boundary.
3. Keep phase boundaries coherent and meaningful, not tiny fragments.
4. Preserve current loop-control protocol and run-resume guarantees.
5. Express decomposition quality expectations via prompt contract (planner + verifier), not heuristic runtime checks.

## 4. Non-Goals

1. No optimization or scoring function for “ideal number of phases.”
2. No static heuristic pass that algorithmically validates granularity.
3. No change to canonical loop-control schema (`docloop.loop_control/v1`).
4. No expansion into general workflow DAG runtime.

---

## 5. Requirements

### 5.1 Functional Requirements

1. A planning run must emit a canonical phase decomposition artifact.
2. Implement/test runs must accept an explicit target phase.
3. All phase execution must remain resumable and auditable in existing run logs/events.
4. Verifier output must remain promise-driven (`COMPLETE|INCOMPLETE|BLOCKED`).

### 5.2 Product/UX Requirements

1. Operators can review the entire PRD decomposition before code changes start.
2. Operators can execute one phase at a time, or a controlled prefix (`up-to`) when desired.
3. Deferments must be explicit and phase-linked.

### 5.3 Constraints

1. Preserve existing pair order semantics and safety guarantees.
2. Keep git checkpoint behavior unchanged.
3. Avoid introducing decomposition heuristics in runtime validation.

---

## 6. High-Level Architecture

### 6.1 New/Updated Artifacts

Under `.superloop/tasks/<task-id>/plan/`:

- `phase_plan.yaml` (new, canonical machine-readable decomposition)
- `plan.md` (existing, narrative rationale and implementation context)
- `feedback.md` (existing)
- `criteria.md` (existing)

### 6.2 Runtime Extensions

`superloop.py` gains:

1. CLI options:
   - `--phase-id <id>` for implement/test scoped execution
   - `--phase-mode {single,up-to}`
2. Phase plan loading/validation (schema-level, not heuristic granularity checks).
3. Prompt preamble injection of active phase contract.
4. Phase lifecycle state persisted in task metadata and events.

Target implementation surfaces in `superloop.py`:

- CLI parsing in `main()` (`argparse` additions for phase options)
- Workspace bootstrap in `ensure_workspace()` (phase artifact creation path)
- Prompt composition in `build_phase_prompt()` (active phase injection)
- Pair loop execution in `main()` (phase gating rules for implement/test)
- Metadata helpers (`_load_task_meta` / `_write_task_meta`) for phase state persistence
- Event emission via `EventRecorder.emit()` and run summary in `write_run_summary()`

### 6.3 Prompt Contract Extensions

Planner and verifier prompts are updated to explicitly require:

- decomposition into coherent phases,
- clear phase boundaries with in-scope/out-of-scope definitions,
- explicit dependency ordering and acceptance criteria,
- deferments mapped to future phases.

No prompt or runtime logic should score or enforce granularity heuristically.

---

## 7. Detailed Design

### 7.1 Phase Plan Schema

`phase_plan.yaml` top-level structure:

```yaml
version: 1
task_id: <task-id>
request_snapshot_ref: <path-to-request.md>
phases:
  - phase_id: phase-1
    title: "<coherent capability slice>"
    objective: "<business/technical outcome>"
    in_scope:
      - "..."
    out_of_scope:
      - "..."
    dependencies:
      - "<phase-id or external dependency>"
    acceptance_criteria:
      - id: AC-1
        text: "..."
    deliverables:
      - "code"
      - "tests"
      - "docs"
    risks:
      - "..."
    rollback:
      - "..."
    status: planned
```

Notes:

- Schema validation checks required fields, allowed enums, and reference integrity.
- Validation does **not** attempt to determine whether the decomposition is “too coarse” or “too fine.”
- A phase may include multiple deliverables when they represent one coherent capability slice.

### 7.2 Planner Prompt Behavior

Planner must:

1. Produce `phase_plan.yaml` + update `plan.md`.
2. Keep phases coherent and implementation-ready.
3. Explicitly avoid one-shot bundling of all PRD scope into one phase unless the request itself is narrowly scoped.
4. Explain why each phase boundary exists.
5. Include explicit deferments in `phase_plan.yaml` for non-current scope to prevent accidental one-shot expansion.
6. If the task is genuinely small and implementation is coherently shippable as a single slice, prefer exactly one phase instead of artificial decomposition.

This is an instruction-contract requirement, not heuristic enforcement.

### 7.3 Plan Verifier Prompt Behavior

Plan verifier must:

1. Validate decomposition clarity and sequencing quality by review judgment.
2. Raise blocking findings for ambiguous/unsafe boundaries.
3. Require explicit deferment mapping.
4. Mark COMPLETE only when `criteria.md` is fully checked and decomposition is actionable.
5. Use reviewer judgment to challenge phase boundaries that are ambiguous, unsafe, or likely to create hidden regressions.
6. Accept a single-phase plan when scope is small and coherent; do not require multi-phase decomposition for its own sake.

Again, verifier judgment is trusted; no runtime granularity heuristic is added.

### 7.4 Implement/Test Execution Scoping

When `--phase-id` is set:

1. Runtime resolves selected phase from `phase_plan.yaml`.
2. `build_phase_prompt()` includes:
   - active phase objective,
   - in/out-of-scope bullets,
   - acceptance criteria,
   - dependencies and deferments.
3. Implement and test pairs are expected to limit edits to selected phase intent.
4. Any intentional out-of-phase edits must be explicitly justified in pair artifacts.

No heuristic auto-rejection is performed for granularity reasons.

When `--phase-id` is omitted:

1. `--pairs plan` remains valid and does not require phase selection.
2. `--pairs implement` or `--pairs test` requires either:
   - explicit `--phase-id`, or
   - explicit override mode (`--phase-mode up-to`) that defines deterministic phase set expansion.
3. If no valid phase target can be resolved, Superloop must fail fast with actionable CLI guidance.

Phase completion rules by enabled pairs:

1. If `--pairs implement` is used without `test`, a phase may transition to `completed` after implement verifier emits `COMPLETE`.
2. If `test` is enabled for the phase run (`--pairs implement,test` or `--pairs test` in a continuation), phase completion requires successful completion of test for that phase.
3. Completion semantics are determined by active/enabled pairs for the run, not by a hard always-test requirement.

### 7.5 Phase State Tracking

Extend `task.json`:

```json
{
  "phase_status": {
    "phase-1": "planned",
    "phase-2": "planned"
  },
  "phase_history": [
    {
      "phase_id": "phase-1",
      "run_id": "run-...",
      "status": "in_progress",
      "ts": "..."
    }
  ]
}
```

Event stream additions (`events.jsonl`):

- `phase_started`
- `phase_completed`
- `phase_blocked`
- `phase_deferred`

These complement existing pair and run events.

State transitions:

- `planned -> in_progress -> completed`
- `planned|in_progress -> blocked`
- `planned|in_progress -> deferred`

Transitions are driven by run outcomes and verifier promise results, not heuristic sizing checks.

---

## 8. Control Flow

### 8.1 Planning Flow

1. Run with `--pairs plan`.
2. Planner emits `phase_plan.yaml` and updated `plan.md`.
3. Plan verifier reviews decomposition quality and emits promise.
4. On COMPLETE, phase plan becomes authoritative for later runs.

### 8.2 Phase Execution Flow

1. Run with `--pairs implement,test --phase-id <phase-id>`.
2. Implement pair executes only active phase outcomes.
3. Test pair validates active phase behavior and regression coverage.
4. On COMPLETE, runtime records phase completion and operator moves to next phase.

### 8.3 Resume Semantics

- Existing run resume remains unchanged.
- If a run resumes mid-phase, phase context is reconstructed from `phase_plan.yaml` + `task.json` + run log.
- If a resumed run references a removed/renamed phase ID, runtime must fail fast and instruct operator to regenerate or reconcile `phase_plan.yaml`.

---

## 9. Data and Compatibility

1. Existing tasks without `phase_plan.yaml` remain valid for legacy usage.
2. If `phase_plan.yaml` is missing, Superloop treats the current request as a single implicit phase and proceeds in legacy-compatible mode.
3. When `phase_plan.yaml` exists, phase-scoped execution uses explicit phase boundaries from the artifact.
4. Legacy runs can adopt explicit decomposition by running the plan pair to generate `phase_plan.yaml`.

---

## 10. Security and Safety Considerations

1. No new external services introduced.
2. Existing verifier criteria and promise gating remain primary completion controls.
3. Scope mistakes are surfaced through verifier findings and logs, not hidden auto-corrections.

---

## 11. Observability

1. Run summaries include phase-level outcomes.
2. Raw logs preserve phase context for each pair cycle.
3. Task metadata provides a durable phase lifecycle record.

---

## 12. Testing Strategy

1. Unit tests:
   - phase plan schema validation,
   - CLI parse for `--phase-id` / `--phase-mode`,
   - phase resolution and prompt injection.
2. Integration tests:
   - plan-only run generates valid `phase_plan.yaml`,
   - implement/test with selected phase include correct context,
   - resume path retains phase context.
3. Regression tests:
   - legacy non-phase runs still function,
   - loop-control parsing unchanged.

4. Prompt contract tests (snapshot-style):
   - planner prompt includes explicit decomposition instructions and deferment mapping requirements,
   - verifier prompt includes phase-boundary judgment criteria and no heuristic granularity checks.

---

## 13. Rollout Plan

### Stage 1: Artifact + Prompt Contract

- Add `phase_plan.yaml` artifact generation requirement.
- Update planner/verifier prompts for phase decomposition quality instructions.

### Stage 2: Phase-Scoped Runtime

- Add CLI phase selection and prompt injection.
- Persist phase lifecycle state/events.

### Stage 3: Adoption Guidance

- Update README with phase-first execution patterns.
- Provide examples for plan → phase 1 → phase 2 iteration.

---

## 14. Alternatives Considered

1. **Heuristic granularity scoring (rejected)**
   - Rejected per product direction.
   - Risks brittle false positives and process over-constraint.

2. **Fully manual decomposition without machine-readable artifact (rejected)**
   - Rejected due to weak enforcement and poor automation support.

3. **DAG orchestration with dynamic branching (deferred)**
   - Out of scope; unnecessary complexity for current requirement.

---

## 15. Open Questions

1. Should phase transition enforcement use strict FSM only, or hybrid strict-with-override semantics?
2. Should `up-to` mode update all intermediate phase statuses within one run transaction or commit per-phase transitions incrementally?
3. Should single-implicit-phase legacy mode emit dedicated lifecycle events (for observability parity) or remain minimal?

---

## 16. Acceptance Criteria

The feature is complete when:

1. Superloop can generate a canonical phase decomposition artifact from PRD intent.
2. Superloop can execute implementation/test for a selected phase with explicit scoped context.
3. Planner/verifier prompts explicitly enforce clear phase boundaries and deferment mapping.
4. No heuristic granularity verification logic is introduced in runtime.
5. Existing loop-control behavior and legacy compatibility remain intact.
6. Small/coherent tasks are allowed to complete as a single phase without forced splitting.
7. If only implement is enabled for a run, implement verifier COMPLETE may mark the active phase completed.
8. If test is enabled for a phase run, phase completion requires test completion.
9. If `phase_plan.yaml` is absent, runtime executes in legacy mode as one implicit phase.

---

## 17. Reviewed Implementation Plan (Corrected)

### Phase A — Artifact + Prompt Contract

1. Add `phase_plan.yaml` to plan artifacts and task bootstrap behavior.
2. Update planner prompt to require explicit coherent phase decomposition and deferment mapping.
3. Update plan verifier prompt to review boundary quality by judgment and block unsafe/ambiguous decomposition.

### Phase B — Runtime Phase Targeting

1. Add `--phase-id` and `--phase-mode` CLI options.
2. Load and validate phase plan schema (required fields/reference integrity only).
3. Inject active phase context into implement/test prompts.
4. Add fail-fast behavior for invalid/missing phase selection when implement/test are requested.
5. Implement completion gating based on enabled pairs (implement-only completion vs implement+test completion).
6. Add legacy fallback path: no `phase_plan.yaml` => one implicit phase.

### Phase C — Lifecycle + Observability

1. Persist `phase_status` and `phase_history` in task metadata.
2. Emit phase lifecycle events in run event stream.
3. Extend run summary with phase outcome rollups.

### Phase D — Test and Documentation Completion

1. Add unit/integration/regression and prompt-contract tests.
2. Update README with phase-first operational guidance and examples.
3. Validate backward compatibility for non-phase legacy runs.
