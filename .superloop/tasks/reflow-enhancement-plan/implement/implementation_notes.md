# Reflow Enhancement Implementation Notes

## Files Changed

- `reflow.py`
- `README.md`
- `reflow_runtime/__init__.py`
- `reflow_runtime/controller.py`
- `reflow_runtime/loaders.py`
- `reflow_runtime/models.py`
- `reflow_runtime/protocol.py`
- `reflow_runtime/scaffold.py`
- `reflow_runtime/storage.py`
- `reflow_runtime/templates/context.md.tmpl`
- `reflow_runtime/templates/target.md.tmpl`
- `reflow_runtime/templates/shared/base_rules.md.tmpl`
- `reflow_runtime/templates/prompts/write.md.tmpl`
- `reflow_runtime/templates/prompts/review.md.tmpl`
- `reflow_runtime/templates/prompts/execute.md.tmpl`
- `reflow_runtime/templates/prompts/full_auto.md.tmpl`
- `tests/test_reflow_runtime.py`

## Checklist Mapping

- Milestone 1:
  Added `Workflow.task_mode`, `RunState.task`, `ContextEntry`, `ProducesEntry`, and normalized `AgentStep.instructions` to `list[str]`.
  Updated workflow loading to accept optional `entry`, optional `task`, string-or-list instructions, declared `context` / `produces`, and default tagged transitions to `route`.
- Milestone 2:
  Persisted `task` in `run.json`.
  Composed instruction bodies in prompt rendering.
  Added task/context/expected-output footer lines.
  Recorded launch-time `context_present` in agent iteration `meta.json`.
- Milestone 3:
  Extended `reflow run` with positional task and `--task-file`.
  Added task-mode enforcement.
  Added `status --verbose`.
  Added `validate`.
- Milestone 4:
  Added `init` plus scaffold generation in `reflow_runtime/scaffold.py`.
  Added editable template assets for `write-verify` and `single-agent`.
- Milestone 5:
  Expanded `tests/test_reflow_runtime.py` for loader, protocol, controller, CLI, status, validate, and scaffold coverage.
  Updated the README Reflow section to document the new CLI and workflow schema.

## Assumptions

- Declared `context` and `produces` paths are repo-relative metadata: they are validated for absolute/escape attempts but are informational rather than enforced inputs.
- `status --verbose` resolves context presence from the latest recorded iteration for the current step, falling back to a live workspace existence check when no iteration metadata exists yet.
- `init` writes JSON-formatted YAML files (`config.yaml`, `workflow.yaml`) to remain compatible whether parsing happens through PyYAML or the JSON fallback path.

## Expected Side Effects

- Agent `request.txt` files now include composed instructions and a richer runtime footer.
- `run.json` contains a stable `task` field and agent iteration `meta.json` may contain `context_present`.
- `status --verbose` loads the workflow definition in addition to run state so it can render current-step metadata.
- Newly scaffolded workflows use composed instructions, `task: required`, declared context/produces metadata, and route-default tagged transitions.

## Deduplication / Centralization Decisions

- Centralized multi-file instruction composition in `load_instruction_body()` and reused it from `render_agent_request()`.
- Centralized scaffolding in `reflow_runtime/scaffold.py` with filesystem templates under `reflow_runtime/templates/` instead of inlining large prompt strings in the CLI.

## Deferred Items

- None.
