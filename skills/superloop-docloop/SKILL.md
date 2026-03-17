---
name: superloop-docloop
description: Run and troubleshoot Docloop/Superloop workflows for iterative document and implementation loops; use when users ask to plan work, run loop passes, resume tasks, interpret loop-control outputs, or stabilize completion criteria.
---

# Superloop + Docloop Skill

Use this skill when the user asks to:
- run `docloop.py` or `superloop.py`,
- resume/recover a stuck loop,
- interpret `<loop-control>` outputs,
- plan a task and execute plan/implement/test passes,
- or improve loop prompts/criteria for better convergence.

## Install locally

```bash
mkdir -p "$CODEX_HOME/skills"
cp -R skills/superloop-docloop "$CODEX_HOME/skills/"
```

## Quick workflow

1. **Pick orchestrator**
   - `docloop.py`: single-document refinement (`SAD`/`PRD`).
   - `superloop.py`: repo task orchestration (`plan,implement,test`) under `.superloop/tasks/...`.

2. **Preflight checks**
   - Confirm command options with `python <tool>.py --help`.
   - Check existing state:
     - `git status --short`
     - `python superloop.py --list-tasks` (for Superloop)

3. **Start or resume safely**
   - Prefer explicit `--workspace` and `--task-id` for Superloop.
   - Use `--resume` to continue prior runs.
   - Keep loops deterministic by setting `--model` and limiting scope in intent/context.

4. **Validate after each run**
   - Review run logs under `.superloop/tasks/<task-id>/` or `.docloop/`.
   - Execute project tests relevant to touched files.
   - Verify git diff contains only intended artifacts.

5. **Recover blocked loops**
   - If agent asks questions, answer with concrete constraints.
   - Tighten criteria and context, then rerun.
   - If repeated malformed loop-control appears, enforce canonical tagged JSON format from references.

## Command templates

See `references/commands.md` for copy/paste commands.

## Loop-control contract

See `references/loop-control.md` for accepted canonical and legacy formats, plus failure modes.

## Planning rubric for requests

When user asks to “plan and write”:
1. Capture objective and success metrics.
2. Define personas and operator workflows.
3. Map to Superloop/Docloop command sequences.
4. Add verification checkpoints and rollback strategy.
5. Produce concise artifact(s) in-repo (`docs/` or feature folder).

For structure and rollout milestones, use `references/roadmap.md`.
