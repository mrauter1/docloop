# Superloop Prompt Guidelines

This document explains the *why* behind Superloop prompt structure so prompts can be improved, recreated, or extended for new loop pairs without breaking behavior quality.

## 1) Core design goals

Superloop prompts should optimize for four outcomes:

1. **High-signal progress per cycle** (avoid low-value churn).
2. **Low false-positive verifier feedback** (only material blockers loop).
3. **Safe autonomy** (agent acts independently, asks only when needed).
4. **Deterministic orchestration contracts** (`<question>` and `<promise>` behavior remains predictable).

## 2) Prompt architecture pattern (producer/verifier pair)

Every loop pair should contain:

- **Producer prompt**: creates or updates artifacts/code.
- **Verifier prompt**: evaluates producer output, updates criteria, and decides promise.

Recommended structure for every prompt:

1. Role
2. Goal
3. Working set / required outputs
4. Rules (ordered, concise, actionable)
5. Control-tag requirements

This keeps prompts DRY, reviewable, and consistent across pairs.

## 3) Producer prompt principles

Use these principles for all producer prompts (`plan`, `implement`, `test`, or new pairs):

1. **Scope-first analysis**
   - Analyze only request-relevant areas before editing.
   - Avoid whole-repo reanalysis unless explicitly needed.

2. **Single source of truth artifacts**
   - Consolidate canonical outputs into one main artifact when feasible (for example plan details in one `plan.md`).
   - Use auxiliary files only for workflow state (feedback/criteria/logs), not duplicate requirements.

3. **Regression-aware execution**
   - Require explicit check of likely regression surfaces before finalizing edits.
   - Ask producer to note assumptions and expected side effects.

4. **Clarification discipline**
   - If ambiguity, logical flaws, breaking-risk, or hidden-behavior risk exists, ask `<question>`.
   - Clarifying question must include best suggestion/supposition.

5. **No verifier-only control signals**
   - Producer must not emit `<promise>...</promise>`.

## 4) Verifier prompt principles

Verifier prompts should be strict on quality but selective on what causes loops.

1. **Materiality gating**
   - Require `blocking` vs `non-blocking` labels.
   - `INCOMPLETE` should only be used when at least one *blocking* finding exists.

2. **Evidence requirement for blockers**
   - Each blocking finding must include:
     - concrete location (file/section/symbol/test),
     - concrete failure/regression scenario,
     - minimal correction direction.
   - When substantial duplicated logic adds clear maintenance debt, verifier should flag it and recommend centralization under DRY/KISS principles.

3. **Scope discipline**
   - Review changed/request-relevant scope first.
   - Out-of-scope findings must include explicit justification.

4. **Stable finding identifiers**
   - Use stable IDs (`PLAN-001`, `IMP-001`, `TST-001`) to reduce repeated feedback churn and support cross-cycle tracking.

5. **Criteria ownership + completion integrity**
   - Verifier maintains criteria file truthfully.
   - `COMPLETE` must correspond to all criteria checks satisfied.

6. **Clarification discipline**
   - Use `<question>` only when missing user intent blocks safe evaluation.
   - Include best suggestion/supposition.

## 5) Control-tag contract (must stay stable)

Prompt text must preserve these interface rules:

- `<question>...</question>` for clarification handoff.
- Verifier final line promise: `<promise>COMPLETE|INCOMPLETE|BLOCKED</promise>`.
- Producer should never decide completion.

If extending prompts, keep this contract unchanged unless orchestrator code is explicitly updated too.

## 6) How to design a new Superloop pair

When adding a new pair (example: `security`, `migration`, `perf`):

1. Define one canonical producer artifact set.
2. Define verifier criteria around observable correctness and risk.
3. Use blocking/non-blocking severities.
4. Require evidence-backed blockers.
5. Keep clarification format consistent.
6. Keep the same control-tag protocol.

Template checklist for a new pair prompt set:

- [ ] Producer prompt has scope-first analysis rule.
- [ ] Producer prompt defines canonical artifact(s).
- [ ] Producer prompt has ambiguity/risk `<question>` rule with suggestion.
- [ ] Verifier prompt defines materiality threshold for blockers.
- [ ] Verifier prompt requires evidence triplet for blockers.
- [ ] Verifier prompt defines criteria ownership and `COMPLETE` integrity.
- [ ] Both prompts keep control tags consistent with Superloop runtime.

## 7) Anti-patterns to avoid

1. **Over-broad reviewer mandates** that encourage generic comments.
2. **Duplicate artifact requirements** that split source of truth.
3. **Blocking on stylistic nits** (creates loop churn).
4. **Missing evidence in findings** (high false-positive risk).
5. **Prompt drift in control tags** (breaks orchestration assumptions).

## 8) Prompt quality review rubric

When editing any Superloop prompt, review against this rubric:

- **Signal**: Does it push toward actionable, high-impact output?
- **Specificity**: Are required outputs and decision rules concrete?
- **Scope control**: Does it avoid unrelated work by default?
- **Risk control**: Are regressions/breaking behavior addressed explicitly?
- **Loop efficiency**: Does it reduce avoidable `INCOMPLETE` cycles?
- **Protocol safety**: Are control-tag rules unambiguous and consistent?

## 9) Change management guidance

For prompt-only changes:

1. Prefer small, incremental edits.
2. Run existing tests to ensure no behavioral regressions in git tracking/runtime helpers.
3. Record rationale in PR description (what loop inefficiency or false-positive pattern is targeted).
4. If possible, evaluate before/after loop metrics (cycles-to-complete, blocker rate, repeated finding rate).

---

Use this file as the baseline standard when creating or revising any Superloop prompt block.


## 10) When to broaden analysis scope

Default behavior is request-relevant, changed-scope-first analysis. Prompts should also explicitly permit broader analysis when justified, including:

1. **Pattern discovery**
   - Shared logic/patterns may exist across modules and must be inspected to avoid partial fixes.

2. **Dependency uncertainty**
   - Module or interface dependencies are unclear and broader inspection is needed to avoid regressions.

3. **Cross-cutting behavior risk**
   - Change may affect compatibility, persistence, security, orchestration flows, or other cross-cutting concerns.

4. **Small-repo economics**
   - Repository/files are small enough that full analysis is cheaper and safer than selective scanning.

When broader analysis is used, agent output should briefly justify why the broader scope was necessary.
