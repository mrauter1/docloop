# Superloop Phase Execution and Resume Fixes PRD

## Summary

This change set fixes phased Superloop execution so explicit phase plans can run end-to-end without a required `--phase-id`, resumed runs land on the correct incomplete phase, phase pair completion is tracked per phase, and phase lifecycle events do not duplicate across resume when the same transition was already recorded.

## Problem

The current phased execution path has four user-visible issues:

1. Explicit `plan/phase_plan.yaml` incorrectly forces `--phase-id`, which blocks the common case of running the full ordered phase plan.
2. Resume can restart from a stale stored phase index instead of the first incomplete phase.
3. Resume checkpoint parsing treats pair completion globally by pair name, so `implement` completed in one phase can incorrectly suppress `implement` in a later phase.
4. Lifecycle events such as `phase_scope_resolved`, `phase_started`, `phase_completed`, and `phase_deferred` can be emitted again on resume even when no new transition occurred.

## Goals

- Allow explicit phase plans to execute all phases in order when `--phase-id` is omitted.
- Preserve explicit `--phase-id` and `--phase-mode up-to` behavior.
- Resume phased runs from the first incomplete phase in the active ordered selection.
- Track pair completion per phase during resume reconstruction.
- Keep phase lifecycle event emission idempotent across resume where prior transitions are already known.
- Ship aligned docs and regression tests for the changed behavior.

## Non-goals

- Adding new CLI flags or a new phase mode enum.
- Refactoring unrelated orchestration paths.
- Changing git checkpoint behavior outside the phased resume path.
- Introducing parallel or multi-run phase scheduling.

## Users and use cases

- A user with a valid `plan/phase_plan.yaml` wants `--pairs implement,test` to run the whole plan without manually naming each phase.
- A user resumes an interrupted phased run and expects execution to continue from the phase still in progress or the next untouched phase, not from the beginning.
- A user expects phase completion in one phase to have no effect on later phases with the same enabled pairs.
- Observability consumers expect phase lifecycle events to represent transitions, not duplicate replay noise after resume.

## Requirements

### CLI behavior

- With an explicit `plan/phase_plan.yaml`, omitted `--phase-id` must resolve the full ordered phase list.
- `--phase-id <id>` with `--phase-mode single` must continue to run only `<id>`.
- `--phase-id <id>` with `--phase-mode up-to` must continue to run the ordered prefix ending at `<id>`.
- `--phase-mode up-to` without `--phase-id` must still fail fast.
- Without an explicit phase plan, phased pairs must continue to use the implicit single-phase fallback.

### Resume behavior

- Resume without an explicit `--phase-id` must start at the first incomplete phase in the stored or newly resolved ordered selection.
- Durable run `events.jsonl` state is the source of truth for phase/pair completion within a run.
- `task.json` continues to persist phase lifecycle selection/status metadata, while completion of `(phase_id, pair)` is reconstructed from run events.
- Pair completion must be reconstructed per `(phase_id, pair)` when phase IDs are present in the event stream.

### Lifecycle behavior

- `phase_scope_resolved` should not re-emit on resume when the same selection was already recorded for the run.
- `phase_started` should not re-emit for a phase already started in the run.
- `phase_deferred` should not re-emit for the same `(phase_id, pair)` transition.
- `phase_completed` should not re-emit for a phase already completed in the run.

## Design notes

- Keep `selection.phase_ids` as the authoritative ordered selection.
- Do not add a new persisted `phase_mode`; the resolved phase list defines what will run.
- Compute resume landing from run-scoped `(phase_id, pair)` completion reconstructed from `events.jsonl`.
- Continue to run `implement` before `test` inside each phase and only advance after the enabled pair set for that phase is satisfied.

## Files expected to change

- `superloop.py`
- `tests/test_superloop_observability.py`
- `README.md`
- `skills/superloop/SKILL.md`

## Verification plan

- Update unit coverage so explicit plans without `--phase-id` run all phases in order.
- Verify `--phase-mode up-to` still requires `--phase-id`.
- Verify resume checkpoint parsing distinguishes `("phase-1", "implement")` from `("phase-2", "implement")`.
- Verify resume starts at the first incomplete phase and continues into later untouched phases.
- Verify repeated resume does not duplicate prior `phase_scope_resolved`, `phase_started`, `phase_deferred`, or `phase_completed` events for already recorded transitions.
- Run `python3 -m pytest tests/test_superloop_observability.py`.
