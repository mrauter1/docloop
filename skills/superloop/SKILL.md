---
name: superloop
description: Use when the user wants repository-level strategy-to-execution orchestration with Superloop. Covers running `superloop` with `plan`, `implement`, and `test` pairs, seeding task intent, resuming runs, and inspecting `.superloop/` artifacts and run history.
---

# Superloop

Use this skill when the user wants a repo-oriented producer/verifier workflow that can plan, implement, and test changes against a codebase.

## Preconditions

- The `superloop` executable is installed and available on `PATH`.
- The workspace is the repository root or is passed explicitly with `--workspace`.
- `codex` must be available. `git` is recommended unless the user intentionally chooses `--no-git`.

## Use

Run `superloop --help` first if the invocation shape is unclear.

Common patterns:

```bash
superloop --workspace . --task-id fix-logging --intent "Implement the requested logging changes." --pairs plan,implement,test
```

```bash
superloop --workspace . --task-id reflow-enhancement-plan --intent "$(cat Reflow_enhancement_plan.md)" --intent-mode replace --pairs plan,implement,test
```

```bash
superloop --workspace . --resume --run-id run-YYYYMMDDTHHMMSSZ-xxxxxxxx
```

## Key options

- `--workspace` selects the repo root.
- `--task-id` gives the task a stable workspace under `.superloop/tasks/`.
- `--intent` seeds the task request.
- `--intent-mode {replace,append,preserve}` controls how new intent updates the task request.
- `--pairs` selects any subset of `plan,implement,test`.
- `--resume` and `--run-id` continue an existing run.
- `--full-auto-answers` lets Superloop answer agent questions through an extra Codex pass.
- `--no-git` disables git checkpointing and change detection.

## Artifacts

Superloop stores task state under `.superloop/tasks/<task-id>/`.

Important task-level files:

- `task.json`
- `run_log.md`
- `raw_phase_log.md`
- `plan/plan.md`
- `implement/implementation_notes.md`
- `test/test_strategy.md`

Important run-level files:

- `runs/<run-id>/request.md`
- `runs/<run-id>/session.json`
- `runs/<run-id>/run_log.md`
- `runs/<run-id>/raw_phase_log.md`
- `runs/<run-id>/events.jsonl`
- `runs/<run-id>/summary.md`

## Operating guidance

- Use `plan,implement,test` unless the task is already tightly planned.
- Prefer explicit `--task-id` values so related runs stay grouped.
- Resume by `--run-id` when possible.
- Read the run-scoped `raw_phase_log.md` to understand what the agent actually did across phases.
- Read `events.jsonl` when precise checkpoint status matters.
- If `--no-git` is used, expect reduced change-detection visibility in logs.
- Superloop runs can stay quiet for long stretches while a nested Codex phase waits on a slow server-side response. Silence by itself is not evidence of a hang. Do not terminate the process unless you have clear proof that it failed or exited.
