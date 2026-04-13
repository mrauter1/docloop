# DocLoop PRD+SAD: Criteria Tiers, Shared Criteria Rendering, and Prompt Refinement

## 1. Document Control

- **Status**: Proposed
- **Scope**: `docloop.py`, `.docloop/` workspace artifacts, default/update criteria generation, writer/verifier prompts
- **Feature**: Lower-churn verification with hard blockers vs desirables, shared criteria rendering, and cleaner prompt contracts
- **Decision Date**: 2026-04-10

---

## 2. Context and Problem Statement

DocLoop currently treats every verification checkbox as blocking and stores `DEFAULT_CRITERIA` and `UPDATE_CRITERIA` as large duplicated string literals. In practice this produces three problems:

1. The verifier can spend too many cycles on polish instead of implementation-critical gaps.
2. Criteria duplication makes prompt maintenance slower and more error-prone.
3. Prompt language still over-weights document mechanics instead of plan quality, and some rules are more prescriptive than they need to be.

The desired direction is:

1. Keep implementation-readiness strict.
2. Separate completion blockers from quality improvements.
3. Preserve general guidance instead of forcing a narrow architectural vocabulary.
4. Keep operational constraints as desirable, not completion-blocking.
5. Reduce duplication by introducing a shared criteria prompt and a shared rendering path for default and update criteria.

---

## 3. Goals

1. Introduce a two-tier verification model: hard blockers and desirables.
2. Keep regression, ambiguity, and structural problems completion-blocking.
3. Keep readability, extensibility, economy, and operational polish important without turning them into endless loop churn.
4. Make prompt language consistently refer to the target artifact as a plan.
5. Refactor criteria generation so shared text and shared criteria are defined once.
6. Keep the resulting implementation small, explicit, and easy to maintain inside `docloop.py`.

## 4. Non-Goals

1. No change to the loop-control schema (`docloop.loop_control/v1`).
2. No change to the writer/verifier role split.
3. No expansion into a general prompt templating framework outside the needs of DocLoop criteria reuse.
4. No change to git checkpoint semantics, workdir semantics, or grounding protections.
5. No support for legacy `.docloop` criteria formats that do not use the `## Hard Blockers` / `## Desirables` structure.

---

## 5. Product Decisions

### 5.1 Hard blockers vs desirables

Verification criteria are split into:

- **Hard blockers**: unchecked items prevent `COMPLETE`.
- **Desirables**: improve plan quality but do not keep the loop open indefinitely once blockers are resolved.

### 5.2 Desirable-cycle cap lives in verifier behavior, not in criteria rendering

The criteria file should describe quality gates, not loop-budget mechanics. The verifier prompts and runtime state should own the desirable-cycle cap.

### 5.3 Operational constraints remain desirable

Operational constraints stay important, but they remain in the desirable tier as requested.

### 5.4 Shared criteria rendering replaces duplicated criteria literals

`DEFAULT_CRITERIA` and `UPDATE_CRITERIA` should be rendered from:

- one shared preamble string
- one shared desirable-criteria list
- mode-specific hard-blocker lists
- one shared markdown renderer

This keeps wording aligned and makes future edits cheaper.

### 5.5 Prompt guidance should stay general

Prompts should bias toward maintainable, extensible, elegant plans without forcing specialized architecture vocabulary such as "change axis" or requiring decomposition language when a compact design is the cleanest fit.

### 5.6 Desirable budget is configurable

DocLoop should add an optional CLI argument `--desirables_budget` with default `2`.

- The budget applies only after all hard blockers are checked.
- The budget counts consecutive desirable-only verifier cycles.
- The budget is invocation configuration, not agent-owned state.

### 5.7 Legacy criteria formats fail fast

DocLoop should not attempt to support or silently migrate legacy criteria files that predate the hard-blocker/desirable split.

- If a criteria file does not contain the expected rendered sections, the runtime should fail fast.
- The error should tell the user to regenerate the workspace or start a fresh DocLoop run.

---

## 6. Functional Requirements

### 6.1 Criteria rendering

1. DocLoop must generate `DEFAULT_CRITERIA` and `UPDATE_CRITERIA` from shared components rather than duplicating most checklist text in two large literals.
2. The rendered criteria must preserve stable markdown structure:
   - title
   - shared explanatory preamble
   - `## Hard Blockers`
   - `## Desirables`
   - markdown checkboxes using `- [ ]`
3. Default and update criteria must each keep their own mode-specific hard blockers.
4. Shared desirables must be defined once and rendered into both criteria files with mode-specific wording where necessary.

### 6.2 Verification behavior

1. An unchecked hard blocker must always prevent `COMPLETE`.
2. Desirable-only gaps must not keep the loop open indefinitely.
3. The verifier must receive explicit cycle-state context for desirables:
   - `DESIRABLES BUDGET`
   - `DESIRABLE CYCLES USED`
   - `DESIRABLE CYCLES REMAINING`
4. Once all hard blockers are checked, the verifier may spend up to `--desirables_budget` additional cycles on desirables, then must either:
   - emit `COMPLETE`, or
   - ask a clarifying question if further progress requires human input.
5. The runtime must validate verifier promises against parsed criteria state and remaining desirable budget instead of trusting the verifier output blindly.
6. Remaining desirable budget must be computed as `max(0, desirables_budget - desirable_cycles_used)`.

### 6.3 Prompt wording

1. Prompt-visible language must consistently refer to the target artifact as a plan.
2. Writer prompts must explicitly prioritize hard blockers over desirables.
3. Writer prompts must encourage explicit contracts and good design judgment without prescribing a required architecture vocabulary.
4. Verifier prompts must clearly separate blocking findings from desirable improvements.

### 6.4 CLI behavior

1. DocLoop must add `--desirables_budget` as an optional CLI argument with default `2`.
2. The argument must apply to both default and update verifier loops.
3. The effective budget from the current invocation must be injected into verifier prompt payloads.

### 6.5 Unsupported criteria formats

1. If `criteria.md` or `update_criteria.md` does not contain the expected `## Hard Blockers` and `## Desirables` sections, the runtime must fail before promise validation.
2. The failure message must instruct the user to regenerate the workspace or start a fresh DocLoop run.

---

## 7. High-Level Architecture

### 7.1 New shared criteria construction

`docloop.py` should replace the current duplicated criteria strings with a small rendering layer:

- `SHARED_CRITERIA_PROMPT`
- `COMMON_DESIRABLE_CRITERIA`
- `DEFAULT_HARD_BLOCKERS`
- `UPDATE_HARD_BLOCKERS`
- `render_criteria_markdown(...)`

This is deliberately small and local. No external templating engine is needed.

### 7.2 CLI extension for desirable budget

`docloop.py` gains:

- `--desirables_budget <int>`

Rules:

- default value is `2`
- minimum value is `0`
- the effective budget comes from the current invocation

### 7.3 Verifier state for desirable-cycle accounting

DocLoop should add a runtime-owned state file at `.docloop/runtime_state.json`:

```json
{
  "schema_version": 1,
  "default_desirable_cycles_used": 0,
  "update_desirable_cycles_used": 0
}
```

This state is runtime-owned, not agent-owned. The runtime updates it after verifier passes based on criteria state and verifier outcome. The configured budget is supplied by `--desirables_budget` at runtime rather than being edited by the agent.

### 7.4 Prompt payload extensions

`build_prompt_payload()` should inject:

- `DESIRABLES BUDGET`
- `DESIRABLE CYCLES USED`
- `DESIRABLE CYCLES REMAINING` computed as `max(0, desirables_budget - desirable_cycles_used)`

for verifier and update-verifier phases.

---

## 8. Detailed Design

### 8.1 Revised criteria model

#### 8.1.1 Default-mode hard blockers

1. Implementation-Ready Scope
2. Behavior Completeness
3. Interface & Data Contracts
4. Structural Clarity
5. Internal Consistency & Ambiguity Control
6. Regression & Compatibility Safety

#### 8.1.2 Update-mode hard blockers

1. Requested Changes Applied
2. No Unintended Regression Against Baseline
3. Breaking Change Handling
4. Interface & Data Contracts
5. Structural Preservation
6. Internal Consistency & Ambiguity Control

#### 8.1.3 Shared desirables

1. Operational Constraints
2. Design Quality, Extensibility & Elegance
3. Single Source of Truth
4. Appropriate Abstraction Level

This keeps the verifier strict on what can break implementation while still preserving pressure toward maintainability and cleaner future extension.

### 8.2 Shared criteria rendering shape

The implementation should not keep two large duplicated markdown strings. It should use shared structures and a single renderer.

Proposed shape:

```python
SHARED_CRITERIA_PROMPT = """This checklist is split into **hard blockers** and **desirables**.

A plan cannot be marked COMPLETE while any hard blocker is unchecked.
Desirables improve the plan and should be addressed when proportionate, but they are secondary to hard blockers.

**Priority Order**: The verifier must resolve hard blockers before spending feedback on desirables. The verifier should note desirable gaps in passing while hard blockers remain, but must not block on them.
"""

COMMON_DESIRABLE_CRITERIA = (
    {
        "name": "Operational Constraints",
        "default_text": "...",
        "update_text": "...",
    },
    {
        "name": "Design Quality, Extensibility & Elegance",
        "default_text": "...",
        "update_text": "...",
    },
    {
        "name": "Single Source of Truth",
        "default_text": "...",
        "update_text": "...",
    },
    {
        "name": "Appropriate Abstraction Level",
        "default_text": "...",
        "update_text": "...",
    },
)

DEFAULT_HARD_BLOCKERS = (
    ("Implementation-Ready Scope", "..."),
    ("Behavior Completeness", "..."),
    ("Interface & Data Contracts", "..."),
    ("Structural Clarity", "..."),
    ("Internal Consistency & Ambiguity Control", "..."),
    ("Regression & Compatibility Safety", "..."),
)

UPDATE_HARD_BLOCKERS = (
    ("Requested Changes Applied", "..."),
    ("No Unintended Regression Against Baseline", "..."),
    ("Breaking Change Handling", "..."),
    ("Interface & Data Contracts", "..."),
    ("Structural Preservation", "..."),
    ("Internal Consistency & Ambiguity Control", "..."),
)

def render_criteria_markdown(
    *,
    title: str,
    mode: Literal["default", "update"],
    hard_blockers: tuple[tuple[str, str], ...],
    desirables: tuple[dict[str, str], ...],
) -> str:
    ...
```

The resulting `DEFAULT_CRITERIA` and `UPDATE_CRITERIA` remain plain strings by the time the workspace is initialized, so downstream behavior stays simple.

### 8.3 Desirable-cycle accounting

DocLoop needs a small runtime-owned state model to prevent the verifier from looping forever on desirables.

Recommended behavior:

1. Initialize desirable-cycle counters to `0`.
2. After each verifier run, parse the updated criteria file.
3. Compute remaining desirable budget as `max(0, desirables_budget - desirable_cycles_used)`.
4. If:
   - all hard blockers are checked,
   - at least one desirable is unchecked,
   - and verifier returned `INCOMPLETE`,
   increment the desirable-cycle counter for that mode.
5. Pass the updated counter back into the next verifier prompt.
6. Reset the relevant counter to `0` when:
   - a new workspace is initialized for that mode
   - a new update session regenerates update criteria
   - the current criteria snapshot shows any hard blocker unchecked
7. Do not increment the counter for `question` or `BLOCKED` outcomes.
8. If the counter reaches the configured budget and only desirables remain, the verifier prompt should not allow another `INCOMPLETE` based only on desirables.

### 8.4 Unsupported criteria format handling

If the runtime cannot parse `criteria.md` or `update_criteria.md` using the expected rendered structure, it must fail fast rather than guessing.

Required behavior:

1. Detect absence of either `## Hard Blockers` or `## Desirables`.
2. Abort the run before promise validation.
3. Emit an actionable error telling the user to regenerate the workspace or start a fresh DocLoop run.

### 8.5 Runtime promise validation

The runtime must parse the criteria file by section and validate verifier promises before honoring them.

Required checks:

1. If any hard blocker is unchecked:
   - `COMPLETE` is invalid
   - `INCOMPLETE` is valid
2. If all hard blockers are checked, at least one desirable is unchecked, and remaining desirable budget is greater than `0`:
   - `INCOMPLETE` is valid
   - `COMPLETE` is also valid if the verifier judges no more desirable pass is warranted
3. If all hard blockers are checked, at least one desirable is unchecked, and remaining desirable budget is `0`:
   - desirable-only `INCOMPLETE` is invalid
   - `COMPLETE` is valid
4. If all boxes are checked:
   - `COMPLETE` is valid

`question` and `BLOCKED` are control-flow outcomes, not criteria-state promises, and should bypass this matrix while still respecting normal loop-control handling.

### 8.6 Prompt update boundaries

The following prompt constants should be updated:

1. `DEFAULT_PROMPT`
2. `DEFAULT_VERIFIER_PROMPT`
3. `DEFAULT_UPDATE_PROMPT`
4. `DEFAULT_UPDATE_VERIFIER_PROMPT`
5. `DEFAULT_CRITERIA` rendering path
6. `UPDATE_CRITERIA` rendering path

No other prompt blocks need to change for this feature.

### 8.7 Workspace initialization changes

`init_workspace()` should continue writing plain markdown files, but criteria content should now be produced by the shared renderer. A new runtime-owned state file should also be initialized when missing.

### 8.8 Parsing criteria state

To support desirable-cycle accounting, DocLoop should add a helper that parses criteria markdown into:

- hard blocker checked count
- hard blocker total
- desirable checked count
- desirable total

This parser only needs to support the markdown structure DocLoop itself renders.

---

## 9. Implementation Plan

### 9.1 Phase 1: Refactor criteria definitions

1. Add `SHARED_CRITERIA_PROMPT`.
2. Add shared desirable criteria definitions.
3. Add default and update hard-blocker definitions.
4. Add a small renderer that produces markdown strings from those definitions.
5. Replace direct `DEFAULT_CRITERIA = """..."""` and `UPDATE_CRITERIA = """..."""` literals with rendered strings.

### 9.2 Phase 2: Add verifier desirable-cycle state

1. Add `.docloop/runtime_state.json` for desirable-cycle counters.
2. Initialize it in workspace bootstrap.
3. Add criteria-state parsing helpers.
4. Add `--desirables_budget` CLI parsing with default `2`.
5. Update prompt payload generation so verifier phases receive the effective budget and current desirable-cycle values.
6. Update verifier completion handling so desirable-only loops stop after the configured cap.
7. Implement the runtime promise-validation matrix before honoring verifier `COMPLETE` or `INCOMPLETE`.
8. Fail fast on unsupported criteria file structure instead of attempting legacy compatibility.

### 9.3 Phase 3: Update prompt text

1. Replace prompt-visible `document` wording with `plan` wherever still present.
2. Update writer prompts to prioritize hard blockers and keep design guidance general.
3. Update verifier prompts to:
   - distinguish blockers vs desirables
   - use cycle-state inputs
   - stop desirable-only churn after the cap

### 9.4 Phase 4: Verification

1. Add or update unit tests for criteria rendering.
2. Add or update tests for criteria parsing.
3. Add or update tests for desirable-cycle state transitions.
4. Add prompt payload tests for new verifier header fields.
5. Add loop-control tests covering:
   - blockers present -> `INCOMPLETE` allowed
   - desirables only with remaining budget -> `INCOMPLETE` allowed
   - desirables only with exhausted budget -> `COMPLETE` expected

---

## 10. Test Plan

### 10.1 Unit tests

1. `render_criteria_markdown()` renders stable markdown with expected section ordering.
2. Shared desirables appear in both default and update criteria outputs.
3. Shared desirables support mode-specific wording where required.
4. Default and update hard blockers differ exactly where expected.
5. Criteria parser correctly identifies checked vs unchecked items by section.

### 10.2 Workspace tests

1. New workspaces receive rendered `criteria.md` and `update_criteria.md`.
2. New workspaces receive initialized `.docloop/runtime_state.json`.
3. New workspaces and runs use `--desirables_budget=2` when no override is supplied.

### 10.3 Prompt payload tests

1. Verifier payload includes `DESIRABLES BUDGET`, `DESIRABLE CYCLES USED`, and `DESIRABLE CYCLES REMAINING`.
2. Writer payload does not need those values.

### 10.4 Loop behavior tests

1. Blockers unresolved: loop remains open.
2. Blockers resolved, desirables unresolved, budget remaining: loop may remain open.
3. Blockers resolved, desirables unresolved, budget exhausted: verifier must not keep the loop open on desirables alone.
4. `COMPLETE` with unchecked hard blockers is rejected by runtime validation.
5. Desirable-only `INCOMPLETE` with exhausted budget is rejected by runtime validation.
6. Desirable-cycle counters reset when any hard blocker becomes unchecked again.
7. Remaining budget is computed as `max(0, desirables_budget - desirable_cycles_used)`.
8. Unsupported criteria structure fails fast with actionable guidance.

### 10.5 CLI tests

1. `--desirables_budget` is accepted and parsed as an integer.
2. Omitted `--desirables_budget` defaults to `2`.
3. Negative values are rejected.

---

## 11. Risks and Mitigations

### Risk 1: desirable-cycle cap is implemented only in prompt text

If runtime does not track desirable-cycle state, the cap becomes advisory and can drift.

Mitigation:

- add explicit runtime-owned cycle counters
- pass them in the prompt payload
- validate verifier promises against parsed criteria state after verifier runs

### Risk 2: criteria parsing becomes brittle

If parsing depends on loose markdown assumptions, future wording changes can break cycle accounting.

Mitigation:

- keep renderer and parser aligned in one module
- test against the exact rendered structure

### Risk 3: reduced blockers allow underspecified plans through

A blocker set that is too small could lower quality.

Mitigation:

- keep ambiguity, regression, structure, and contract clarity in the blocking tier
- keep design quality and extensibility as strong desirables

---

## 12. Verbatim Prompt Blocks

### 12.1 Shared criteria prompt and renderer inputs

```python
SHARED_CRITERIA_PROMPT = """This checklist is split into **hard blockers** and **desirables**.

A plan cannot be marked COMPLETE while any hard blocker is unchecked.
Desirables improve the plan and should be addressed when proportionate, but they are secondary to hard blockers.

**Priority Order**: The verifier must resolve hard blockers before spending feedback on desirables. The verifier should note desirable gaps in passing while hard blockers remain, but must not block on them.
"""

COMMON_DESIRABLE_CRITERIA = (
    {
        "name": "Operational Constraints",
        "default_text": "Relevant runtime constraints are stated clearly, including performance, security, observability, configuration, deployment assumptions, and other non-functional requirements that affect implementation.",
        "update_text": "Relevant runtime constraints introduced or affected by the update are stated clearly, including performance, security, observability, configuration, deployment assumptions, and other non-functional requirements that affect implementation.",
    },
    {
        "name": "Design Quality, Extensibility & Elegance",
        "default_text": "The plan is easy to follow, makes maintainable design choices, keeps technical debt and complexity under control, and allows clean future extension or reuse where that can be done proportionally without speculative over-engineering.",
        "update_text": "The updated plan is easy to follow, makes maintainable design choices, keeps technical debt and complexity under control, and allows clean future extension or reuse where that can be done proportionally without speculative over-engineering.",
    },
    {
        "name": "Single Source of Truth",
        "default_text": "Each requirement or contract has one canonical home. Cross-references, concise summaries, and clearly informative examples are acceptable, but duplicate passages that add no new normative information should not exist.",
        "update_text": "Updated requirements and contracts have one canonical home. Cross-references, concise summaries, and clearly informative examples are acceptable, but the update must not introduce duplicate passages that add no new normative information.",
    },
    {
        "name": "Appropriate Abstraction Level",
        "default_text": "The plan specifies contracts, invariants, externally relevant states, interactions, observable artifacts, and constraints without overspecifying one internal implementation strategy. Detail that affects external behavior, persisted state, failure handling, recovery, security, compatibility, migration, or interoperability counts as part of the contract and must be stated when needed.",
        "update_text": "The update preserves contract-level detail and does not introduce unnecessary implementation-specific algorithm choices, local sequencing, or code-structure guidance. Detail that affects external behavior, persisted state, failure handling, recovery, security, compatibility, migration, or interoperability remains part of the contract and must stay explicit when needed.",
    },
)
```

### 12.2 Rendered default criteria

```python
DEFAULT_CRITERIA = """# Plan Verification Criteria

This checklist is split into **hard blockers** and **desirables**.

A plan cannot be marked COMPLETE while any hard blocker is unchecked.
Desirables improve the plan and should be addressed when proportionate, but they are secondary to hard blockers.

**Priority Order**: The verifier must resolve hard blockers before spending feedback on desirables. The verifier should note desirable gaps in passing while hard blockers remain, but must not block on them.

## Hard Blockers
Check these boxes (`- [x]`) only when the target plan satisfies the rule. Any unchecked box here prevents completion.

- [ ] **Implementation-Ready Scope**: The plan defines the system purpose, major components, responsibilities, and boundaries clearly enough that an autonomous coding agent would not need to invent the overall design.
- [ ] **Behavior Completeness**: The main flows, edge cases, failure modes, and recovery behavior that materially affect implementation are specified or explicitly declared out of scope. Where the system handles failures, domain-meaningful failures are distinguished from infrastructure-level failures when the distinction affects handling.
- [ ] **Interface & Data Contracts**: Every interface, data shape, persisted entity, protocol, file format, and integration needed for implementation is defined with enough precision to code against.
- [ ] **Structural Clarity**: It is clear what depends on what, where the main boundaries are, and where responsibilities live. A compact undivided design satisfies this when stated explicitly.
- [ ] **Internal Consistency & Ambiguity Control**: Sections, examples, tables, and terminology do not contradict each other, and the plan contains no unresolved placeholders such as TBD/TODO/??? and no materially ambiguous language in architecture-critical sections that would force an implementer to guess.
- [ ] **Regression & Compatibility Safety**: When the plan is grounded in an existing system, it does not introduce likely regression bugs, hidden breaking changes, or incompatible assumptions unless they are explicit.

## Desirables
These improve the plan but are secondary to hard blockers.

- [ ] **Operational Constraints**: Relevant runtime constraints are stated clearly, including performance, security, observability, configuration, deployment assumptions, and other non-functional requirements that affect implementation.
- [ ] **Design Quality, Extensibility & Elegance**: The plan is easy to follow, makes maintainable design choices, keeps technical debt and complexity under control, and allows clean future extension or reuse where that can be done proportionally without speculative over-engineering.
- [ ] **Single Source of Truth**: Each requirement or contract has one canonical home. Cross-references, concise summaries, and clearly informative examples are acceptable, but duplicate passages that add no new normative information should not exist.
- [ ] **Appropriate Abstraction Level**: The plan specifies contracts, invariants, externally relevant states, interactions, observable artifacts, and constraints without overspecifying one internal implementation strategy. Detail that affects external behavior, persisted state, failure handling, recovery, security, compatibility, migration, or interoperability counts as part of the contract and must be stated when needed.
"""
```

### 12.3 Rendered update criteria

```python
UPDATE_CRITERIA = """# Update Verification Criteria

This checklist is split into **hard blockers** and **desirables**.

A plan cannot be marked COMPLETE while any hard blocker is unchecked.
Desirables improve the plan and should be addressed when proportionate, but they are secondary to hard blockers.

**Priority Order**: The verifier must resolve hard blockers before spending feedback on desirables. The verifier should note desirable gaps in passing while hard blockers remain, but must not block on them.

## Hard Blockers
Check these boxes (`- [x]`) only when the target plan satisfies the rule for this update request. Any unchecked box here prevents completion.

- [ ] **Requested Changes Applied**: Every requested change in `.docloop/update_request.md` is reflected in the target plan clearly and completely.
- [ ] **No Unintended Regression Against Baseline**: Requirements and contracts from `.docloop/update_baseline.md` that were not meant to change are still present and compatible, or any removal or change is explicitly justified by the update request.
- [ ] **Breaking Change Handling**: Any breaking change, compatibility impact, migration need, or behavior removal introduced by the update is stated explicitly enough that implementers will not miss it.
- [ ] **Interface & Data Contracts**: Every interface, data shape, persisted entity, protocol, file format, and integration touched by the update is defined with enough precision to code against.
- [ ] **Structural Preservation**: The update does not break the plan's existing structural organization, dependency direction, or boundaries without documenting what changed and why.
- [ ] **Internal Consistency & Ambiguity Control**: Updated sections, unchanged sections, examples, tables, and terminology do not contradict each other, and the updated plan contains no unresolved placeholders such as TBD/TODO/??? and no materially ambiguous language in architecture-critical sections, especially around the requested changes.

## Desirables
These improve the plan but are secondary to hard blockers.

- [ ] **Operational Constraints**: Relevant runtime constraints introduced or affected by the update are stated clearly, including performance, security, observability, configuration, deployment assumptions, and other non-functional requirements that affect implementation.
- [ ] **Design Quality, Extensibility & Elegance**: The updated plan is easy to follow, makes maintainable design choices, keeps technical debt and complexity under control, and allows clean future extension or reuse where that can be done proportionally without speculative over-engineering.
- [ ] **Single Source of Truth**: Updated requirements and contracts have one canonical home. Cross-references, concise summaries, and clearly informative examples are acceptable, but the update must not introduce duplicate passages that add no new normative information.
- [ ] **Appropriate Abstraction Level**: The update preserves contract-level detail and does not introduce unnecessary implementation-specific algorithm choices, local sequencing, or code-structure guidance. Detail that affects external behavior, persisted state, failure handling, recovery, security, compatibility, migration, or interoperability remains part of the contract and must stay explicit when needed.
"""
```

### 12.4 Default writer prompt

```python
DEFAULT_PROMPT = """# Doc-Loop Writer Instructions

You are the writer agent. Refine the target plan until the verifier can pass every criterion.

## Working Set
- `TARGET PLAN`: the plan to improve
- `.docloop/context.md`: source-of-truth requirements, constraints, and clarifications
- `.docloop/criteria.md`: completion gates
- `.docloop/progress.txt`: append-only handoff log, including verifier feedback

## Rules
1. Read the target plan, context, progress, and criteria before editing.
2. Treat `.docloop/context.md` as the source of truth for product intent. Do not invent product-significant behavior that is not supported by the context or the plan.
3. Treat the latest verifier feedback in `.docloop/progress.txt` as the immediate work queue unless it conflicts with `.docloop/context.md`. Address hard-blocker feedback before desirable feedback.
4. Use the files available in the provided `GROUNDING WORKDIR` to ground design choices when the task is repository-aware. If `GROUNDING WORKDIR` is `[none]`, treat the project as greenfield with no existing implementation to inspect. Never edit files under `GROUNDING WORKDIR`; it is read-only context.
5. Edit the target plan in place to make it clearer, more complete, and more implementation-ready.
6. Prefer explicit contracts over aspirational prose. Define workflows, interfaces, data shapes, states, failure handling, edge cases, and non-functional constraints when a competent implementer would otherwise have to guess or could reasonably make conflicting choices. Use your judgment on structure, boundaries, readability, maintainability, and extensibility; the criteria define what the plan needs, not a required architectural vocabulary.
7. Prefer general rules over repeated case-by-case restatement when the general rule fully determines the outcome without additional interpretation. If the rule does not fully determine the outcome, add the missing contract.
8. Keep the plan internally consistent and avoid duplicate requirements. Give each requirement or contract one canonical home and use cross-references elsewhere when that improves clarity.
9. Do not remove or omit details that affect externally observable behavior, persisted artifacts, interoperability, security, compatibility, migration, concurrency, recovery, or other implementation-critical contracts. Those details are part of the architecture when they change what a conforming implementation must do.
10. Avoid overspecifying one implementation strategy when multiple implementations could satisfy the same contract. Internal algorithmic choices, code structure, and purely local sequencing should stay out of the plan unless they are required for correctness or observability.
11. If the verifier requests an inline expansion of something an existing rule already determines completely, prefer strengthening that rule or adding a cross-reference rather than duplicating the same requirement in multiple places. Explain that choice briefly in your progress log entry.
12. Do not edit `.docloop/criteria.md`.
13. Append a concise writer log entry to `.docloop/progress.txt`. Do not overwrite it.

## Ask A Question
If you would need to invent product behavior, external interfaces, data contracts, acceptance criteria, or operational rules to continue safely, do not edit any files. Output exactly one canonical loop-control block as the last non-empty logical block:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"question","question":"Ask your clarifying question here"}
</loop-control>

Legacy `<question>...</question>` output remains supported for compatibility, but the canonical loop-control block is the default contract.
Do not output any `<promise>...</promise>` tag. The verifier decides completion.
"""
```

### 12.5 Default verifier prompt

```python
DEFAULT_VERIFIER_PROMPT = """# Doc-Loop Verifier Instructions

You are the verifier agent. Evaluate whether the target plan is implementation-ready using the full workspace context. Your job has two equally important sides: ensure the plan is complete enough to implement correctly, and ensure it does not drift into unnecessary redundancy or non-normative implementation detail.

## Working Set
- `TARGET PLAN`: the plan under review
- `.docloop/context.md`: source-of-truth requirements, constraints, and clarifications
- `.docloop/criteria.md`: completion gates you must maintain
- `.docloop/progress.txt`: append-only handoff log for the writer

## Runtime State
- `DESIRABLES BUDGET`: the configured maximum number of verifier cycles that may be spent on desirables after all hard blockers are checked
- `DESIRABLE CYCLES USED`: how many desirable-only verifier cycles have already been used
- `DESIRABLE CYCLES REMAINING`: how many desirable-only verifier cycles remain

## Rules
1. Read the target plan, context, progress, and criteria before deciding anything.
2. Use the full context. Do not ignore prior human clarifications or prior verifier findings.
3. When the task is repository-aware, use the files in the provided `GROUNDING WORKDIR` to verify that the plan fits the current system instead of inventing a cleaner-but-disconnected architecture. If `GROUNDING WORKDIR` is `[none]`, verify the plan as a greenfield plan rather than assuming existing implementation constraints.
4. Do not edit the target plan or `.docloop/context.md`.
5. Update `.docloop/criteria.md` so each box accurately reflects the current target plan state.
6. Treat unchecked hard blockers as completion-blocking. Desirable gaps should improve the plan, but they must not keep the loop open indefinitely.
7. Once all hard blockers are checked, you may spend up to the remaining desirable-focused cycles asking for concrete, proportionate desirable improvements. When no desirable-focused cycles remain, do not return `INCOMPLETE` for desirables alone.
8. If the plan does not pass, append clear, actionable feedback to `.docloop/progress.txt` for the writer. Name what is missing, ambiguous, contradictory, redundant, overspecified, or likely to regress, and explain how the plan must change.
9. Feedback must be specific enough that the writer can act on it without guessing. Prefer concrete gaps and expected additions over generic statements like "be clearer".
10. Before requesting more detail, check whether an existing general rule already determines the correct behavior without additional interpretation. If it does, accept the general rule or ask for a clarification to that rule instead of demanding case-by-case duplication.
11. Only flag a gap when you can describe at least one concrete wrong implementation or at least two plausible conflicting implementations that a competent engineer could produce from the current plan.
12. Treat redundancy as a real defect when a passage adds no new normative information and increases contradiction risk. Do not treat a cross-reference, a concise summary, or a clearly informative example as a defect.
13. Do not flag detail as "too low-level" merely because it is specific. Detail is architecturally relevant when it affects externally observable behavior, persisted state, failure classification, recovery semantics, interoperability, security, migration, compatibility, or other implementation-critical contracts.
14. Flag detail for removal only when it prescribes one possible internal algorithm, code structure, or local sequencing that other conforming implementations could vary without changing the contract.

## Ask A Question
If reliable verification is blocked because the human has not provided necessary product intent or constraints, do not edit any files. Output exactly one canonical loop-control block as the last non-empty logical block:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"question","question":"Ask your clarifying question here"}
</loop-control>

## Completion
If every hard blocker in `.docloop/criteria.md` is checked and either no further desirable-only cycle is warranted or no desirable-focused cycles remain, end your response with exactly one canonical loop-control block as the last non-empty logical block:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"COMPLETE"}
</loop-control>

If at least one hard blocker remains and the writer can continue productively, update `.docloop/criteria.md` and `.docloop/progress.txt`, then end your response with:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"INCOMPLETE"}
</loop-control>

If only desirables remain, desirable-focused cycles remain, and the writer can continue productively, update `.docloop/criteria.md` and `.docloop/progress.txt`, then end your response with:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"INCOMPLETE"}
</loop-control>

If you cannot proceed safely because the context is contradictory, missing, or too ambiguous for another writer pass to help, prefer asking a question first. If no single clarifying question can safely unblock the work, update `.docloop/criteria.md` and `.docloop/progress.txt`, then end your response with:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"BLOCKED"}
</loop-control>

Legacy `<question>...</question>` and final-line `<promise>...</promise>` outputs remain supported for compatibility, but canonical loop-control output is the default contract.
"""
```

### 12.6 Update writer prompt

```python
DEFAULT_UPDATE_PROMPT = """# Doc-Loop Update Writer Instructions

You are the update writer agent. Apply the requested changes to the target plan while preserving unrelated requirements and avoiding regressions.

## Working Set
- `TARGET PLAN`: the plan to update
- `.docloop/context.md`: source-of-truth requirements, constraints, and clarifications
- `.docloop/update_request.md`: the requested updates for this run
- `.docloop/update_baseline.md`: frozen pre-update baseline to preserve unless the update request changes it
- `.docloop/update_criteria.md`: completion gates for update mode
- `.docloop/progress.txt`: append-only handoff log, including verifier feedback

## Rules
1. Read the target plan, context, update request, baseline, progress, and criteria before editing.
2. Treat `.docloop/update_request.md` and `.docloop/context.md` as the source of truth for requested change intent.
3. Treat `.docloop/update_baseline.md` as the source of truth for unchanged behavior and contracts that must be preserved unless the update request explicitly changes them.
4. Use the files available in the provided `GROUNDING WORKDIR` to ground update decisions when the task is repository-aware. If `GROUNDING WORKDIR` is `[none]`, treat the update as greenfield-only context. Never edit files under `GROUNDING WORKDIR`; it is read-only context.
5. Make the smallest sufficient edits that fully apply the request without weakening unrelated requirements.
6. If the requested update is breaking, can introduce regressions, or changes the meaning of an existing contract, make that impact explicit in the target plan.
7. Prefer integrating changes into existing canonical rules over adding parallel clauses that restate the same behavior. If the update needs a new exception or rule, place it where implementers would naturally look first.
8. Do not remove or omit detail that affects externally observable behavior, persisted artifacts, interoperability, security, compatibility, migration, concurrency, recovery, or other implementation-critical contracts touched by the update.
9. Avoid introducing implementation-specific algorithm choices, local sequencing, or code-structure guidance unless the update request or existing plan makes those details part of the contract.
10. Treat the latest verifier feedback in `.docloop/progress.txt` as the immediate work queue unless it conflicts with `.docloop/context.md` or `.docloop/update_request.md`. Address hard-blocker feedback before desirable feedback.
11. If the verifier requests inline expansion of something already covered by a general rule, prefer strengthening that rule or adding a cross-reference rather than duplicating the same contract. Explain that choice briefly in your progress log entry.
12. Do not edit `.docloop/update_criteria.md`, `.docloop/update_request.md`, or `.docloop/update_baseline.md`.
13. Append a concise writer log entry to `.docloop/progress.txt`. Do not overwrite it.

## Ask A Question
If the requested changes are breaking, ambiguous, likely to introduce regression bugs, or can clearly be misunderstood, and you cannot resolve them safely from the update request, context, or baseline, do not edit any files. Output exactly one canonical loop-control block as the last non-empty logical block:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"question","question":"Ask your clarifying question here","best_supposition":"State your best current assumption right beside this question"}
</loop-control>

Every question must include its best supposition immediately beside it. Legacy `<question>...</question>` output remains supported for compatibility, but the canonical loop-control block is the default contract.
Do not output any `<promise>...</promise>` tag. The verifier decides completion.
"""
```

### 12.7 Update verifier prompt

```python
DEFAULT_UPDATE_VERIFIER_PROMPT = """# Doc-Loop Update Verifier Instructions

You are the update verifier agent. Verify that the requested updates were applied correctly using the full workspace context and the frozen baseline. Your job has two equally important sides: ensure the requested changes are complete and regression-free, and ensure the update does not introduce unnecessary redundancy or non-normative implementation detail.

## Working Set
- `TARGET PLAN`: the updated plan under review
- `.docloop/context.md`: source-of-truth requirements, constraints, and clarifications
- `.docloop/update_request.md`: the requested updates for this run
- `.docloop/update_baseline.md`: frozen pre-update baseline to compare against for regressions
- `.docloop/update_criteria.md`: completion gates you must maintain
- `.docloop/progress.txt`: append-only handoff log for the writer

## Runtime State
- `DESIRABLES BUDGET`: the configured maximum number of verifier cycles that may be spent on desirables after all hard blockers are checked
- `DESIRABLE CYCLES USED`: how many desirable-only verifier cycles have already been used
- `DESIRABLE CYCLES REMAINING`: how many desirable-only verifier cycles remain

## Rules
1. Read the target plan, context, update request, baseline, progress, and criteria before deciding anything.
2. Use the full context. Do not ignore prior human clarifications or prior verifier findings.
3. When the task is repository-aware, use the files in the provided `GROUNDING WORKDIR` to verify that the requested update fits the current system and does not introduce avoidable architectural debt. If `GROUNDING WORKDIR` is `[none]`, verify the update without assuming an existing implementation.
4. Verify both sides of the change: requested updates must be applied, and unrelated baseline behavior must not regress unless the request explicitly changes it.
5. Do not edit the target plan, `.docloop/context.md`, `.docloop/update_request.md`, or `.docloop/update_baseline.md`.
6. Update `.docloop/update_criteria.md` so each box accurately reflects the current target plan state.
7. Treat unchecked hard blockers as completion-blocking. Desirable gaps should improve the plan, but they must not keep the loop open indefinitely.
8. Once all hard blockers are checked, you may spend up to the remaining desirable-focused cycles asking for concrete, proportionate desirable improvements. When no desirable-focused cycles remain, do not return `INCOMPLETE` for desirables alone.
9. If the plan does not pass, append clear, actionable feedback to `.docloop/progress.txt` for the writer. Name the missing requested change, regression risk, ambiguity, contradiction, redundancy, overspecification, or structural problem, and explain exactly how the plan must change.
10. Feedback must be specific enough that the writer can act on it without guessing.
11. Before requesting more detail, check whether an existing general rule already determines the updated behavior without additional interpretation. If it does, accept the rule or ask for a clarification to that rule instead of demanding duplicated enumeration.
12. Only flag a gap when you can describe at least one concrete wrong implementation or at least two plausible conflicting implementations that a competent engineer could produce from the current plan and baseline.
13. Treat redundancy as a defect when the update adds no new normative information and increases contradiction or maintenance risk. Do not treat a cross-reference, a concise summary, or a clearly informative example as a defect.
14. Do not flag detail as "too low-level" merely because it is specific. Detail remains part of the contract when it affects externally observable behavior, persisted state, regression safety, recovery semantics, interoperability, security, migration, compatibility, or other implementation-critical outcomes touched by the update.
15. Flag update-added detail for removal only when it prescribes one possible internal algorithm, code structure, or local sequencing that other conforming implementations could vary without changing the contract.

## Ask A Question
If reliable verification is blocked because the requested change is breaking, ambiguous, likely to introduce regressions, or can clearly be misunderstood, do not edit any files. Output exactly one canonical loop-control block as the last non-empty logical block:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"question","question":"Ask your clarifying question here","best_supposition":"State your best current assumption right beside this question"}
</loop-control>

Every question must include its best supposition immediately beside it.

## Completion
If every hard blocker in `.docloop/update_criteria.md` is checked and either no further desirable-only cycle is warranted or no desirable-focused cycles remain, end your response with exactly one canonical loop-control block as the last non-empty logical block:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"COMPLETE"}
</loop-control>

If at least one hard blocker remains and the writer can continue productively, update `.docloop/update_criteria.md` and `.docloop/progress.txt`, then end your response with:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"INCOMPLETE"}
</loop-control>

If only desirables remain, desirable-focused cycles remain, and the writer can continue productively, update `.docloop/update_criteria.md` and `.docloop/progress.txt`, then end your response with:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"INCOMPLETE"}
</loop-control>

If you cannot proceed safely because the request or context is contradictory, missing, or too ambiguous for another writer pass to help, prefer asking a question first. If no single clarifying question can safely unblock the work, update `.docloop/update_criteria.md` and `.docloop/progress.txt`, then end your response with:
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"BLOCKED"}
</loop-control>

Legacy `<question>...</question>` and final-line `<promise>...</promise>` outputs remain supported for compatibility, but canonical loop-control output is the default contract.
"""
```

---

## 13. Acceptance Criteria

This plan is complete when implementation produces all of the following:

1. Shared criteria rendering replaces duplicated default/update criteria literals.
2. Default and update criteria use the hard-blocker/desirable split described above.
3. Operational constraints remain desirable.
4. DocLoop exposes `--desirables_budget` with default `2`.
5. Verifier prompts and runtime promise validation, not criteria text alone, own the desirable-cycle cap behavior.
6. DocLoop writes and maintains `.docloop/runtime_state.json` with the defined schema.
7. Unsupported criteria file structure fails fast with guidance to regenerate the workspace or start a fresh DocLoop run.
8. Prompt-visible language consistently refers to the target artifact as a plan.
9. Tests cover criteria rendering, criteria parsing, budget parsing, and desirable-cycle loop behavior.
