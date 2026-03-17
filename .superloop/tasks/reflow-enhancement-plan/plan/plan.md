# Reflow Enhancement Implementation Plan

## Scope and Goal

Implement the five changes described in `Reflow_enhancement_plan.md` against the current Reflow runtime in an order that preserves backward compatibility, keeps the runtime small, and avoids avoidable packaging churn. The implementation target is the current CLI/runtime surface in `reflow.py` and `reflow_runtime/`, not a fresh redesign.

## Codebase Findings

- `reflow.py` currently exposes `run`, `resume`, `reply`, `status`, `stop`, and `list`; there is no `init`, `validate`, task input, or `status --verbose`.
- `reflow_runtime.models.AgentStep.instructions` is a single `str`, `Workflow` has no task mode, and `RunState` has no persisted task field.
- `reflow_runtime.loaders.load_workflow()` requires explicit `entry`, validates only string `instructions`, and requires explicit `transitions.tag` whenever `map` is used.
- `reflow_runtime.protocol.render_agent_request()` reads exactly one instruction body and only renders workflow/step/loop/operator-input/transition footer data.
- `reflow_runtime.storage.RunStore.create_run()` persists run state plus `operator_inputs.md`, but `run.json` and iteration `meta.json` do not capture task or context presence.
- `reflow_runtime.controller.status_run()` and `list_runs()` print a minimal fixed surface; tests currently lock that behavior in `tests/test_reflow_runtime.py`.
- The repository already has a top-level importable module at `reflow.py`; adding Python code under a new `reflow/` package path would be fragile because `import reflow` currently resolves to the file, not the directory.

## Implementation Decisions

- Keep runtime changes inside the existing `reflow_runtime/` package plus `reflow.py`.
- Place scaffold logic in a new import-safe module such as `reflow_runtime/scaffold.py` rather than `reflow/scaffold.py`.
- Place template assets in a non-shadowed path such as `reflow_runtime/templates/`.
- Preserve all existing workflow files and CLI calls as valid inputs unless the enhancement spec explicitly adds new validation.
- Reuse existing validation helpers (`_normalize_repo_pattern`, `_validate_allowed_fields`, `_validate_workflow_relative_instruction`, `_validate_workflow_relative_file`) instead of inventing parallel parsers.

## Milestones

### Milestone 1: Extend core models and loader schema

Goal: land the shared data-shape changes first so later controller/CLI work builds on one stable contract.

Changes:
- Add `Workflow.task_mode`.
- Add `RunState.task`.
- Change `AgentStep.instructions` from `str` to `list[str]`.
- Add `ContextEntry` and `ProducesEntry` dataclasses and corresponding `AgentStep.context` / `AgentStep.produces` fields.
- Make workflow `entry` optional and default to the first declared step.
- Default tagged transitions to `tag="route"` when `map` is present and `tag` is omitted.

Acceptance criteria:
- Existing workflows with string `instructions`, explicit `entry`, and explicit `tag` still load unchanged.
- Workflows may omit `entry` and the first step becomes the entry.
- Agent steps accept either string or non-empty list `instructions`.
- Agent `context` and `produces` validate as optional list-of-mapping metadata.
- Tagged transitions without `tag` load as `route`.
- Task mode defaults to `optional` when absent and rejects values outside `required|optional|none`.

### Milestone 2: Add run/task persistence and prompt rendering changes

Goal: wire the new schema into real execution without changing the controller flow model.

Changes:
- Update `RunStore.create_run()` and `RunState.to_dict()/from_dict()` to persist `task`.
- Update `load_instruction_body()` and `render_agent_request()` to compose multiple instruction bodies in declared order.
- Add task, context, and produces lines to the agent footer.
- Compute context existence at iteration start and persist `context_present` into iteration `meta.json`.
- Thread `workspace` into prompt rendering using the existing controller/store workspace instead of adding a second workspace source.

Acceptance criteria:
- `request.txt` contains concatenated instruction bodies separated by blank lines.
- Footer emits `- task:` only when task is non-null.
- Footer emits `- context:` and `- expected output:` lines from metadata, marking missing context as `(not present)`.
- Missing context never fails a run by itself.
- `meta.json` records `context_present` only for agent iterations and only as launch-time booleans.
- Existing shell-step behavior and artifacts remain unchanged.

### Milestone 3: Extend CLI and operator-visible status surfaces

Goal: expose the new runtime contract to operators with minimal CLI expansion.

Changes:
- Extend `reflow run` to accept `TASK` and `--task-file`, with mutual exclusion and `task_mode` enforcement.
- Pass task into `run_new_workflow()` and `RunStore.create_run()`.
- Extend `status` with `--verbose`.
- Show task in `status` when present.
- Show verbose current-step context/produces in `status --verbose`.
- Keep `list` sorted by `started_at` descending; do not broaden its columns unless implementation work proves necessary.
- Add `validate` command that reports config/workflow validation using existing loaders.

Acceptance criteria:
- `task: required` fails without task input and prints a concrete usage message.
- `task: none` ignores CLI task input and persists `null`.
- Positional task and `--task-file` together fail fast before runtime mutation.
- `resume` and `reply` continue using the task persisted in `run.json`; they do not accept replacement task input.
- `status --verbose` prints current-step context/produces using current workspace existence checks.
- `validate` exits `0` on valid workflow, `25` on invalid config/workflow, and prints a short summary.

### Milestone 4: Add workflow scaffolding

Goal: provide a low-friction path to create workflows that already use the new contracts.

Changes:
- Add `init` subcommand to `reflow.py`.
- Implement scaffold writer in `reflow_runtime/scaffold.py`.
- Add editable template assets under `reflow_runtime/templates/`.
- Generate:
  - `.reflow/config.yaml` when absent
  - `.reflow/context.md` when absent
  - workflow template files under `.reflow/workflows/<workflow_name>/`
  - target document stub when absent
- Support `write-verify` and `single-agent` templates plus provider defaults for `codex` and `claude`.

Acceptance criteria:
- `init` refuses to overwrite an existing workflow directory.
- Existing config/context files are skipped, not overwritten.
- Generated templates use composed instructions, route-default transitions, task mode, and declared context/produces metadata.
- Generated workflow validates successfully with the new `validate` command.
- Scaffold output clearly lists created and skipped files plus next steps.

### Milestone 5: Regression coverage and docs alignment

Goal: lock behavior with focused tests and keep the human-facing docs aligned with the runtime contract.

Changes:
- Extend `tests/test_reflow_runtime.py` for loader, protocol, controller, status/list, validate, and scaffold coverage.
- Add focused helper tests if the scaffold module warrants its own file.
- Update README or runtime-facing usage docs if they mention CLI syntax affected by task, init, validate, or verbose status.

Acceptance criteria:
- Tests cover each new backward-compatible branch and at least one end-to-end generated workflow path.
- Existing runtime tests still pass after interface changes.
- User-facing docs no longer describe obsolete CLI syntax or omit the new commands.

## Interface Definitions

### Workflow model

`Workflow`
- `task_mode: Literal["required", "optional", "none"]`
- `entry: str` remains materialized after loading even when omitted in YAML

`AgentStep`
- `instructions: list[str]`
- `context: list[ContextEntry] = []`
- `produces: list[ProducesEntry] = []`

`ContextEntry`
- `path: str`
- `as_description: str`

`ProducesEntry`
- `path: str`
- `as_description: str`

### Run persistence

`RunState`
- add `task: str | None = None`

`RunStore.create_run(workflow_name, steps, entry, task=None) -> RunState`
- persists `task` once at run creation

Iteration `meta.json`
- add optional `context_present: { "<repo-relative path>": true|false, ... }`

### Loader contracts

`load_workflow()`
- accepts top-level `task`
- accepts omitted top-level `entry`
- accepts agent-step `instructions` as string or non-empty list of strings
- accepts optional agent-step `context` and `produces`
- defaults `transitions.tag` to `"route"` when `map` exists and `tag` is omitted

`load_instruction_body(workflow, paths)`
- accepts the normalized `list[str]` instruction contract and returns a blank-line-joined string

### Protocol/controller contracts

`render_agent_request(workflow, run, step, loop, warning, workspace) -> str`
- renders composed instructions followed by runtime footer
- footer order: task when present, workflow, step, loop, context lines, produces lines, operator input path, transition guidance, policy lines, warning when present

`finalize_iteration(..., context_present: dict[str, bool] | None = None)`
- records launch-time context presence in `meta.json`

### CLI contracts

`reflow run <workflow> [TASK] [--task-file PATH] [--workspace PATH] [--full-auto]`
- `TASK` and `--task-file` are mutually exclusive

`reflow status <run_id> [--workspace PATH] [--verbose]`

`reflow validate <workflow> [--workspace PATH]`

`reflow init <workflow_name> [--template NAME] [--provider KIND] [--target FILE] [--workspace PATH]`

## Test Plan

- Loader tests:
  - string instructions still work
  - single-item instruction list behaves identically
  - multi-item instruction list preserves order
  - empty instruction list fails
  - `task` mode parsing and invalid value rejection
  - omitted `entry` defaults to first step
  - `context`/`produces` validation rejects absolute and escaping paths
  - missing `tag` with `map` defaults to `route`
- Protocol/controller tests:
  - task line appears/omits correctly
  - context and produces lines render correctly
  - missing context does not fail execution
  - `meta.json` records `context_present`
  - `status` prints task and `status --verbose` prints context/produces
  - `resume`/`reply` preserve task
- CLI tests:
  - `run` rejects positional task plus `--task-file`
  - `task: required` without task fails with usage message
  - `validate` success and failure paths
  - `init` success, existing workflow refusal, skip-existing config/context behavior
- End-to-end tests:
  - scaffolded `write-verify` workflow validates
  - scaffolded workflow can complete with the fake provider using `<route>` tags

## Risk Register

### R1: Packaging conflict for scaffold code

Risk:
- The design doc references `reflow/scaffold.py`, but `import reflow` currently resolves to `/home/marcelo/code/docloop/reflow.py`.

Impact:
- New scaffold code could become non-importable or could force an unnecessary package refactor.

Mitigation:
- Keep scaffold logic under `reflow_runtime/` and templates under `reflow_runtime/templates/`.
- Only consider package refactoring if later work requires it; do not bundle that refactor into this task.

### R2: Backward-compatibility regressions in workflow loading

Risk:
- Converting `instructions` to `list[str]` and making `entry` optional can break call sites that still assume a string or always-present YAML field.

Impact:
- Existing workflows could fail to run or render malformed requests.

Mitigation:
- Normalize to the new shape at load time only.
- Update all call sites in the same milestone.
- Keep explicit regression tests for current single-string workflows.

### R3: Status output drift breaking tests or operators

Risk:
- Extending `status` and adding `--verbose` may unintentionally change the default output shape relied on by current tests or scripts.

Impact:
- Existing automation may break on output parsing.

Mitigation:
- Keep default `status` additive and minimal.
- Put extra context/produces detail behind `--verbose`.
- Preserve `list` formatting unless there is a strong implementation reason to change it.

### R4: Metadata semantics drifting from policy semantics

Risk:
- Declared `context` and `produces` are informational only, while `policy.required_files` is enforcement. Mixing those concerns in code would create hidden behavior changes.

Impact:
- Runs could start failing or passing for reasons not expressed in the workflow contract.

Mitigation:
- Restrict context/produces handling to loader validation, request rendering, verbose status, and `meta.json` recording.
- Do not route them through `evaluate_policy()`.

### R5: Scaffold templates going stale against runtime behavior

Risk:
- `init` can generate workflows that no longer reflect the real request/footer/runtime contract.

Impact:
- First-run experience degrades and generated workflows may validate but behave poorly.

Mitigation:
- Make generated workflows use the same current defaults the runtime expects.
- Add a validate-and-run regression test for generated templates.
- Update docs in the same task rather than deferring template guidance.

## Implementation Checklist

- Update dataclasses and persistence models first.
- Normalize loader outputs before touching controller logic.
- Update request rendering and iteration metadata next.
- Extend CLI parsing and command handlers after the runtime contract is stable.
- Implement scaffold module and templates after `validate` exists so scaffold verification is trivial.
- Finish with regression tests and docs updates.

## Out of Scope

- Refactoring the top-level CLI into a new Python package layout.
- Changing shell-step semantics beyond preserving compatibility with the new metadata model.
- Enforcing `produces` writes or failing runs on missing `context`.
