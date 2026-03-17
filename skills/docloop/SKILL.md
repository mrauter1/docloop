---
name: docloop
description: Use when the user wants iterative document refinement or controlled document updates with DocLoop. Covers running `docloop`, choosing SAD vs PRD targets, seeding inputs, using update mode, and interpreting `.docloop/` artifacts and loop-control behavior.
---

# DocLoop

Use this skill when the task is document refinement in a local workspace and the user wants the DocLoop writer/verifier workflow rather than ad hoc editing.

## Preconditions

- The `docloop` executable is installed and available on `PATH`.
- The workspace is the directory where the target document should live, or `--output` is used explicitly.
- `git` and `codex` should be available unless the user intentionally runs with `--no-git`.

## Use

Run `docloop --help` first if the invocation shape is unclear.

Common patterns:

```bash
docloop
```

```bash
docloop --type PRD --input-file notes.md --output ./docs/
```

```bash
docloop --update --update-text "Clarify backward compatibility and offline deployment constraints." --output ./SAD.md
```

## Key options

- `--type {SAD,PRD}` chooses the default target filename.
- `--input-text` or `--input-file` seeds the target document.
- `--update` with `--update-text` applies a controlled change request to an existing document.
- `--output` chooses the target file or directory.
- `--max-iterations` limits loop count.
- `--model` selects the Codex model.
- `--no-git` disables repo initialization and checkpoint commits.

## Artifacts

DocLoop creates a `.docloop/` directory next to the target document. Important files:

- `.docloop/prompt.md`
- `.docloop/verifier_prompt.md`
- `.docloop/criteria.md`
- `.docloop/progress.txt`
- `.docloop/context.md`

Update mode also uses:

- `.docloop/update_prompt.md`
- `.docloop/update_verifier_prompt.md`
- `.docloop/update_criteria.md`
- `.docloop/update_request.md`
- `.docloop/update_baseline.md`

## Operating guidance

- Prefer `--update` when the user is changing an existing document against explicit requirements.
- Inspect `.docloop/progress.txt` and `.docloop/criteria.md` to understand why a run is still incomplete.
- If the run stops on a question, answer it and continue from the same workspace state.
- Treat `.docloop/context.md` as the durable clarification log for the current document workflow.
- DocLoop runs can remain silent for extended periods while the nested Codex call is waiting on a long server-side response. Lack of terminal output does not mean the process is hung. Do not kill the process unless you have direct evidence that it exited or failed.
