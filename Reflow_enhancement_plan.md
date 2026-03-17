# Reflow Enhancement Plan

## Overview

Five changes to maximize Reflow's utility as a standard workflow
definition for LLM agent orchestration. Ordered by implementation
dependency.

1. **Composable instructions** — eliminate prompt duplication across steps
2. **Task input** — give operators a natural per-run intent channel
3. **Transition tag default** — `<route>` as the standard default
4. **Declared context** — make workflows self-documenting
5. **Scaffolding and validation** — collapse setup time to minutes

Each change is backward-compatible. Existing workflows work without
modification.

---

## Change 1: Composable Instructions

### Problem

Every agent step has one `instructions` file. When multiple steps share
behavioral rules (persona, memory conventions, formatting), those rules
are duplicated across prompt files. Changing a shared rule means editing
every prompt that includes it.

### Design

`instructions` accepts either a string (current behavior) or an ordered
list of strings. When a list, Reflow reads each file in order and
concatenates them with a blank line separator. The Reflow footer is
appended after the last file.

```yaml
# Current — still valid:
review:
  kind: agent
  instructions: prompts/review.md

# New — also valid:
review:
  kind: agent
  instructions:
    - shared/base_rules.md
    - shared/repo_memory.md
    - prompts/review.md
```

#### Resolution rules

- Each entry is a path relative to the workflow directory.
- Each entry may point to a file or to a directory containing `SKILL.md`.
- Entries are concatenated in declared order with `\n\n` between bodies.
- An empty list is a validation error.
- A single-element list is equivalent to a plain string.

### Implementation

#### `models.py`

Change `AgentStep.instructions` type:

```python
@dataclass(frozen=True)
class AgentStep:
    name: str
    instructions: list[str]  # was: str
    # ... rest unchanged
```

#### `loaders.py`

In `_parse_step`, replace the single-path validation with list handling:

```python
raw = payload.get("instructions")
if isinstance(raw, list):
    if not raw:
        raise ConfigError(f"agent step {step_name!r} instructions list must not be empty.")
    instructions = [
        _validate_workflow_relative_instruction(workflow_root, entry, f"agent step {step_name!r} instructions[{i}]")
        for i, entry in enumerate(raw)
    ]
elif isinstance(raw, str):
    instructions = [
        _validate_workflow_relative_instruction(workflow_root, raw, f"agent step {step_name!r} instructions")
    ]
else:
    raise ConfigError(f"agent step {step_name!r} instructions must be a string or list of strings.")
```

Each entry goes through the existing `_validate_workflow_relative_instruction`
unchanged.

#### `protocol.py`

In `render_agent_request`, load and concatenate all entries:

```python
bodies = []
for relative_path in step.instructions:
    target = workflow.root / relative_path
    if target.is_dir():
        target = target / "SKILL.md"
    bodies.append(target.read_text(encoding="utf-8").rstrip())
body = "\n\n".join(bodies)
```

The rest of footer assembly is unchanged.

#### `loaders.py` — `load_instruction_body`

Update to accept `list[str]`:

```python
def load_instruction_body(workflow: Workflow, paths: list[str]) -> str:
    bodies = []
    for relative_path in paths:
        target = workflow.root / relative_path
        if target.is_dir():
            target = target / "SKILL.md"
        bodies.append(target.read_text(encoding="utf-8").rstrip())
    return "\n\n".join(bodies)
```

Update all call sites to pass `step.instructions` (now always a list).

### Tests

1. Single string `instructions` still works (backward compat).
2. List of one entry works identically to a plain string.
3. List of multiple entries concatenates in order with `\n\n` separator.
4. Empty list raises `ConfigError`.
5. List entry pointing to nonexistent file raises `ConfigError`.
6. List entry pointing to directory with `SKILL.md` resolves correctly.
7. List entry escaping workflow directory raises `ConfigError`.
8. `request.txt` in iteration directory contains the full concatenated
   prompt with footer.

---

## Change 2: Task Input

### Problem

The operator's per-run intent has no standard entry point. It is
currently mixed into `context.md` alongside persistent workspace
knowledge, requiring a file edit before every run.

### Design

#### Workflow declaration

Add an optional `task` field at the workflow top level:

```yaml
name: docloop
task: required
entry: write
steps: ...
```

Values:
- `optional` (default): task is injected if provided, omitted if not.
- `required`: `reflow run` fails without a task argument.
- `none`: workflow ignores any provided task.

When omitted, `task` defaults to `optional`. This means every existing
workflow automatically accepts task input with zero configuration
changes.

#### CLI

```bash
reflow run <workflow> [TASK] [--task-file <path>] [--workspace <path>]
```

- `TASK`: positional argument, natural language task description.
- `--task-file`: read task from a file. Mutually exclusive with `TASK`.
- If both absent and `task: required`, fail with:
  `Error: workflow 'docloop' requires a task. Usage: reflow run docloop "your task description"`

#### Persistence

`run.json` gains a `task` field:

```json
{
  "run_id": "run_...",
  "workflow": "docloop",
  "task": "Refine the networking section for production readiness",
  "status": "running",
  ...
}
```

- `task` is `null` when not provided or when `task: none`.
- Set once at run creation. Never modified by resume, reply, or any
  controller operation.

#### Prompt injection

Task appears in the Reflow footer as the first runtime field, before
workflow name, step, context, and transitions:

```
[composed instruction bodies]

## Reflow Runtime
- task: Refine the networking section for production readiness
- workflow: docloop
- step: write
- loop: 1
- operator_inputs: .reflow/runs/.../operator_inputs.md
...
```

When `task` is `null`, the `- task:` line is omitted entirely.

#### Status display

`reflow status` shows the task when present:

```
run_id: run_20260316T...
workflow: docloop
task: Refine the networking section for production readiness
status: running
current_step: write
```

### Implementation

#### `models.py`

Add `task_mode` to `Workflow`:

```python
@dataclass(frozen=True)
class Workflow:
    name: str
    root: Path
    entry: str
    steps: dict[str, Step]
    task_mode: str  # "required", "optional", "none"
    # ... rest unchanged
```

Add `task` to `RunState`:

```python
@dataclass
class RunState:
    run_id: str
    workflow: str
    task: str | None  # NEW
    status: str
    current_step: str
    # ... rest unchanged
```

Update `RunState.to_dict` and `RunState.from_dict` to include `task`.

#### `loaders.py`

In `load_workflow`:

```python
WORKFLOW_TOP_LEVEL_FIELDS = {
    "version", "name", "entry", "steps", "default_provider",
    "budgets", "operator_input", "task",  # NEW
}

task_mode = payload.get("task", "optional")
if task_mode not in {"required", "optional", "none"}:
    raise ConfigError("workflow task must be 'required', 'optional', or 'none'.")
```

Pass `task_mode` to the `Workflow` constructor.

#### `controller.py`

In `run_new_workflow`, accept and validate task:

```python
def run_new_workflow(workspace, workflow_name, full_auto, task=None):
    config = load_config(workspace)
    workflow = load_workflow(workspace, workflow_name, config)

    if workflow.task_mode == "required" and not task:
        raise ConfigError(
            f"workflow '{workflow_name}' requires a task. "
            f"Usage: reflow run {workflow_name} \"your task description\""
        )
    if workflow.task_mode == "none":
        task = None

    store = RunStore(workspace)
    _refuse_if_active_conflict(store)
    run = store.create_run(workflow.name, list(workflow.steps), workflow.entry, task=task)
    # ... rest unchanged
```

#### `storage.py`

In `create_run`, accept `task`:

```python
def create_run(self, workflow_name, steps, entry, task=None):
    run = RunState(
        run_id=run_id,
        workflow=workflow_name,
        task=task,
        # ... rest unchanged
    )
```

#### `protocol.py`

In `render_agent_request`, inject task into footer:

```python
footer_parts = ["## Reflow Runtime"]
if run.task:
    footer_parts.append(f"- task: {run.task}")
footer_parts.extend([
    f"- workflow: {workflow.name}",
    f"- step: {step.name}",
    f"- loop: {loop}",
    # ... rest unchanged
])
```

#### CLI

Add task arguments to the `run` subcommand:

```python
run_parser.add_argument("task", nargs="?", default=None, help="Task description")
run_parser.add_argument("--task-file", default=None, help="Read task from file")
```

In the CLI handler:

```python
task = args.task
if args.task_file:
    if task:
        raise ConfigError("cannot provide both a positional task and --task-file.")
    task = Path(args.task_file).read_text(encoding="utf-8").strip()
```

### Tests

1. `task: required` without task fails with helpful error message.
2. `task: required` with positional task succeeds, persisted in `run.json`.
3. `task: optional` (default) without task succeeds, `task` is `null`.
4. `task: optional` with task succeeds, task persisted.
5. `task: none` ignores provided task, `task` is `null`.
6. `--task-file` reads task from file.
7. Positional task + `--task-file` is a validation error.
8. Task appears in prompt footer when present.
9. Task line omitted from footer when `null`.
10. `reflow status` displays task when present.
11. `resume` and `reply` inherit task from existing `run.json`.
12. Task is never modified after run creation.
13. Workflow without `task` field defaults to `optional` (backward compat).

---

## Change 3: Transition Tag Default

### Problem

Every workflow that uses tag-based transitions must declare `tag: route`
even though `<route>` is the obvious standard convention. This is
unnecessary boilerplate for the common case.

### Design

When a `transitions` block includes `map` but omits `tag`, the tag
defaults to `"route"`. The agent emits `<route>VALUE</route>`.

Minimal tagged workflow:

```yaml
transitions:
  default: verify
  map:
    verify: verify
    retry: "@retry"
    done: "@done"
```

No `tag` field needed. Agent emits `<route>verify</route>`.

Custom tag (explicit override):

```yaml
transitions:
  tag: promise
  default: INCOMPLETE
  map:
    COMPLETE: "@done"
    INCOMPLETE: write
    BLOCKED: "@blocked"
```

Agent emits `<promise>COMPLETE</promise>`.

Tagless (no agent decision):

```yaml
transitions:
  default: review
```

No `tag`, no `map`. Step always transitions to the default target.

### Implementation

#### `loaders.py`

In `_parse_transitions`, when `map` is present:

```python
if "tag" not in payload and "map" not in payload:
    default_target = _validate_transition_target(...)
    return AgentTransitions(default_target=default_target, tag=None, default_decision=None, mapping={})

tag = payload.get("tag")
if tag is None:
    tag = "route"
else:
    tag = _require_non_empty_string(tag, f"agent step {label!r} transitions.tag")
```

No other code changes. The tag is already used generically throughout
`protocol.py` for parsing and footer rendering.

### Tests

1. `map` present without `tag` defaults to `"route"`.
2. `map` present with explicit `tag` uses that tag.
3. Neither `tag` nor `map` uses default target directly.
4. Existing workflows with explicit `tag` are unchanged.

---

## Change 4: Declared Context

### Problem

The workflow definition describes control flow (which step runs next)
but not information flow (what files each step reads, what it produces).
An operator reading `workflow.yaml` cannot trace data dependencies
without reading every prompt file.

### Design

Add two optional fields to agent steps: `context` and `produces`. Both
are informational. They enrich the prompt footer and appear in operator
tools. They do not gate execution or enforce behavior — that remains
the job of `policy`.

```yaml
write:
  kind: agent
  instructions:
    - shared/base_rules.md
    - prompts/write.md
  context:
    - path: SAD.md
      as: "target document to refine"
    - path: .reflow/context.md
      as: "source-of-truth requirements and constraints"
    - path: progress.txt
      as: "writer/verifier handoff log"
  produces:
    - path: SAD.md
      as: "refined target document"
    - path: progress.txt
      as: "appended progress log entry"
```

#### `context` entries

Each entry has:
- `path` (required): repo-relative path to a file or directory.
- `as` (required): short human-readable role description.

At iteration launch, Reflow checks whether each context path exists
and includes the result in the prompt footer:

```
- context: SAD.md — target document to refine
- context: .reflow/context.md — source-of-truth requirements and constraints
- context: progress.txt (not present) — writer/verifier handoff log
```

Missing context entries do NOT cause iteration failure. The agent sees
what is available and works with it. Enforcement of required files
belongs in `policy.required_files`.

#### `produces` entries

Each entry has:
- `path` (required): repo-relative path the step is expected to modify.
- `as` (required): short description of what the step writes.

Produces entries appear in the prompt footer:

```
- expected output: SAD.md — refined target document
- expected output: progress.txt — appended progress log entry
```

Produces is informational only. Reflow does NOT validate that the step
actually wrote to these paths. Enforcement belongs in `policy`.

#### `meta.json` recording

Each iteration's `meta.json` records `context_present`: a mapping from
each context path to a boolean indicating whether the file existed at
launch time. `produces` is not recorded in `meta.json` because it is
static workflow metadata, not per-iteration state.

#### Status display

`reflow status <run_id> --verbose` displays context and produces for
the current step, showing which context files currently exist.

### Implementation

#### `models.py`

Add dataclasses and update `AgentStep`:

```python
@dataclass(frozen=True)
class ContextEntry:
    path: str
    as_description: str

@dataclass(frozen=True)
class ProducesEntry:
    path: str
    as_description: str

@dataclass(frozen=True)
class AgentStep:
    name: str
    instructions: list[str]
    max_loops: int
    transitions: AgentTransitions
    context: list[ContextEntry] = field(default_factory=list)
    produces: list[ProducesEntry] = field(default_factory=list)
    # ... rest unchanged
```

#### `loaders.py`

Add parsing functions:

```python
AGENT_STEP_FIELDS = {
    "kind", "instructions", "provider", "max_loops",
    "count_toward_cycles", "transitions", "policy",
    "context", "produces",
}

def _parse_context_entries(payload, label):
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ConfigError(f"{label} context must be a list.")
    entries = []
    for i, entry in enumerate(payload):
        if not isinstance(entry, dict):
            raise ConfigError(f"{label} context[{i}] must be a mapping.")
        _validate_allowed_fields(entry, {"path", "as"}, f"{label} context[{i}]")
        path = _normalize_repo_pattern(entry.get("path"), f"{label} context[{i}].path")
        as_desc = _require_non_empty_string(entry.get("as"), f"{label} context[{i}].as")
        entries.append(ContextEntry(path=path, as_description=as_desc))
    return entries

def _parse_produces_entries(payload, label):
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ConfigError(f"{label} produces must be a list.")
    entries = []
    for i, entry in enumerate(payload):
        if not isinstance(entry, dict):
            raise ConfigError(f"{label} produces[{i}] must be a mapping.")
        _validate_allowed_fields(entry, {"path", "as"}, f"{label} produces[{i}]")
        path = _normalize_repo_pattern(entry.get("path"), f"{label} produces[{i}].path")
        as_desc = _require_non_empty_string(entry.get("as"), f"{label} produces[{i}].as")
        entries.append(ProducesEntry(path=path, as_description=as_desc))
    return entries
```

Call from `_parse_step` in the agent branch.

#### `protocol.py`

In `render_agent_request`, add context and produces to footer. The
function signature gains `workspace: Path`:

```python
context_lines = []
for entry in step.context:
    exists = (workspace / entry.path).exists()
    if exists:
        context_lines.append(f"- context: {entry.path} — {entry.as_description}")
    else:
        context_lines.append(f"- context: {entry.path} (not present) — {entry.as_description}")

produces_lines = []
for entry in step.produces:
    produces_lines.append(f"- expected output: {entry.path} — {entry.as_description}")
```

Insert `context_lines` and `produces_lines` into the footer after the
step/loop fields and before the transition line.

Thread `workspace` from `controller.py` where `store.workspace` is
available.

#### `controller.py`

In `_execute_agent_step`, compute context presence for `meta.json`:

```python
context_present = {}
for entry in step.context:
    context_present[entry.path] = (store.workspace / entry.path).exists()
```

Pass `context_present` to `store.finalize_iteration` for recording
in `meta.json`.

#### `storage.py`

In `finalize_iteration`, record context presence:

```python
if context_present is not None:
    meta["context_present"] = context_present
```

Add `context_present` parameter to `finalize_iteration`.

### Tests

1. Step with no `context` or `produces` works unchanged (backward compat).
2. Context file present: footer shows path and role.
3. Context file absent: footer shows "(not present)" with role.
4. Missing context does NOT cause iteration failure.
5. Produces entries appear in footer.
6. `meta.json` records `context_present` mapping.
7. Context paths are validated (no absolute, no `..`, no escape).
8. Produces paths are validated (no absolute, no `..`, no escape).
9. `reflow status --verbose` displays context and produces.

---

## Change 5: Scaffolding and Validation

### Problem

Creating a new workflow requires authoring 3-7 files across a specific
directory structure. A first-time user must understand file layout,
config schema, workflow schema, transition model, and prompt footer
before getting a working loop.

### Design: `reflow init`

```bash
reflow init <workflow_name> [--template <name>] [--provider <kind>] [--target <file>] [--workspace <path>]
```

Arguments:
- `workflow_name` (required): name for the new workflow directory.
- `--template` (default: `write-verify`): built-in template.
- `--provider` (default: `codex`): provider kind for generated config.
- `--target` (default: `document.md`): target document path.
- `--workspace` (default: cwd): workspace root.

Rules:
- If the workflow directory already exists, refuse and exit with error.
- If `.reflow/config.yaml` exists, skip config creation, print message.
- If `.reflow/context.md` exists, skip context creation.
- If the target document does not exist, create it with a stub.

#### Built-in templates

**`write-verify`**: Two-step write/verify loop. Writer refines a
document, verifier checks it. Standard doc-loop pattern.

**`single-agent`**: One agent step that runs until `@done` or
`max_loops`. Simplest possible wrapper around a prompt.

#### Template storage

Templates live as actual files in `reflow/templates/<template_name>/`.
Each template directory contains the files to be generated, with
`{placeholder}` markers for substitution. This keeps templates
editable, syntax-highlightable, and separate from Python code.

```
reflow/templates/
  write-verify/
    workflow.yaml
    shared/
      base_rules.md
    prompts/
      write.md
      verify.md
  single-agent/
    workflow.yaml
    shared/
      base_rules.md
    prompts/
      agent.md
```

Substitution variables: `{workflow_name}`, `{target}`,
`{provider_kind}`, `{provider_command}`, `{provider_model}`,
`{extra_args}`.

Provider defaults:

| Kind | Command | Model | Extra args |
|------|---------|-------|------------|
| codex | codex | o4-mini | `["--full-auto"]` |
| claude | claude | sonnet | `[]` |

#### Generated `workflow.yaml` for `write-verify`

```yaml
version: 1
name: {workflow_name}
task: required
entry: write

steps:
  write:
    kind: agent
    instructions:
      - shared/base_rules.md
      - prompts/write.md
    max_loops: 20
    count_toward_cycles: true
    context:
      - path: {target}
        as: "target document to refine"
      - path: .reflow/context.md
        as: "source-of-truth requirements and constraints"
    produces:
      - path: {target}
        as: "refined target document"
    transitions:
      default: verify
      map:
        verify: verify
        retry: "@retry"
        done: "@done"
        blocked: "@blocked"

  verify:
    kind: agent
    instructions:
      - shared/base_rules.md
      - prompts/verify.md
    max_loops: 20
    count_toward_cycles: true
    context:
      - path: {target}
        as: "target document under review"
      - path: .reflow/context.md
        as: "source-of-truth requirements and constraints"
    produces: []
    transitions:
      default: write
      map:
        write: write
        done: "@done"
        retry: "@retry"
        blocked: "@blocked"
```

Note: no `tag` field on either step. Both default to `<route>`.
Note: no `entry` field. First declared step (`write`) is the entry.

#### Generated `shared/base_rules.md`

```markdown
# Base Rules

1. Read all context files listed in the Reflow Runtime footer before
   making changes.
2. Treat `.reflow/context.md` as the source of truth for product intent.
   Do not invent behavior not supported by the context.
3. Prefer explicit contracts over vague descriptions.
4. State each requirement once. Cross-reference rather than duplicate.
```

#### Generated `prompts/write.md`

```markdown
# Writer Instructions

You are the writer agent. Your task is described in the Reflow Runtime
footer below. Refine the target document to accomplish that task.

## Rules
- Edit the target document in place.
- Address the most recent verifier feedback first.

## When finished
End your response with one of:
- `<route>verify</route>` — ready for verification
- `<route>retry</route>` — need another editing pass
- `<route>done</route>` — task is complete without verification
- `<route>blocked</route>` — cannot proceed without human input
```

#### Generated `prompts/verify.md`

```markdown
# Verifier Instructions

You are the verifier agent. Evaluate whether the target document
satisfies the task described in the Reflow Runtime footer.

## Rules
- Do NOT edit the target document.
- If the document needs improvement, explain what is missing or wrong.
- Be specific: name the section, the gap, and what must change.

## When finished
End your response with one of:
- `<route>done</route>` — document is complete and satisfies the task
- `<route>write</route>` — document needs more work (include feedback)
- `<route>retry</route>` — need another verification pass
- `<route>blocked</route>` — cannot verify without human input
```

#### Generated `config.yaml` (if absent)

```yaml
version: 1
providers:
  {provider_kind}:
    kind: {provider_kind}
    command: {provider_command}
    model: {provider_model}
    timeout_sec: 3600
    args: {extra_args}
```

#### Generated `context.md` (if absent)

```markdown
# Context and Requirements

<!-- Describe persistent product intent and constraints here. -->
<!-- The agents treat this file as the source of truth. -->
<!-- Per-run tasks are provided via the CLI, not this file. -->
```

#### Post-init output

```
Workflow 'myworkflow' initialized.

  Created .reflow/config.yaml
  Created .reflow/context.md
  Created .reflow/workflows/myworkflow/workflow.yaml
  Created .reflow/workflows/myworkflow/shared/base_rules.md
  Created .reflow/workflows/myworkflow/prompts/write.md
  Created .reflow/workflows/myworkflow/prompts/verify.md
  Created document.md

Next steps:
  1. Edit .reflow/context.md with your requirements
  2. Edit document.md with initial content (or leave empty)
  3. Run: reflow run myworkflow "describe what you want done"
```

### Design: `reflow validate`

```bash
reflow validate <workflow_name> [--workspace <path>]
```

Loads config and workflow through the existing `load_config` and
`load_workflow` functions. Reports success or all validation errors.
Does not create any files or state.

```
$ reflow validate myworkflow
Config: ok
Workflow 'myworkflow': ok
  Steps: write, verify
  Entry: write
  Providers: codex

$ reflow validate broken
Config: ok
Workflow 'broken': FAILED
  - agent step 'review' references unknown provider 'gpt'
  - shell step 'test' on_failure references unknown step 'fixup'
```

### Implementation: `reflow init`

#### New file: `reflow/scaffold.py`

```python
from pathlib import Path

PROVIDER_DEFAULTS = {
    "codex": {"command": "codex", "model": "o4-mini", "extra_args": '["--full-auto"]'},
    "claude": {"command": "claude", "model": "sonnet", "extra_args": "[]"},
}

TEMPLATES_DIR = Path(__file__).parent / "templates"

def init_workflow(workspace, workflow_name, template_name, provider_kind, target):
    reflow_dir = workspace / ".reflow"
    workflow_dir = reflow_dir / "workflows" / workflow_name
    template_dir = TEMPLATES_DIR / template_name

    if workflow_dir.exists():
        raise ValueError(f"workflow directory already exists: {workflow_dir}")
    if not template_dir.is_dir():
        raise ValueError(f"unknown template: {template_name}")
    if provider_kind not in PROVIDER_DEFAULTS:
        raise ValueError(f"unknown provider kind: {provider_kind}")

    subs = {
        "workflow_name": workflow_name,
        "target": target,
        "provider_kind": provider_kind,
        **PROVIDER_DEFAULTS[provider_kind],
    }

    created = []

    # Config (if absent)
    config_path = reflow_dir / "config.yaml"
    if not config_path.exists():
        _write_template(template_dir / "_config.yaml", config_path, subs)
        created.append(str(config_path.relative_to(workspace)))
    else:
        print(f"  Skipped {config_path.relative_to(workspace)} (already exists)")

    # Context (if absent)
    context_path = reflow_dir / "context.md"
    if not context_path.exists():
        _write_template(template_dir / "_context.md", context_path, subs)
        created.append(str(context_path.relative_to(workspace)))

    # Workflow files
    for source in sorted(template_dir.rglob("*")):
        if source.name.startswith("_") or source.is_dir():
            continue
        relative = source.relative_to(template_dir)
        dest = workflow_dir / relative
        _write_template(source, dest, subs)
        created.append(str(dest.relative_to(workspace)))

    # Target document (if absent)
    target_path = workspace / target
    if not target_path.exists():
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(f"# {target_path.stem}\n\nDraft.\n", encoding="utf-8")
        created.append(target)

    return created


def _write_template(source, dest, subs):
    text = source.read_text(encoding="utf-8")
    for key, value in subs.items():
        text = text.replace("{" + key + "}", value)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
```

Files prefixed with `_` (like `_config.yaml`, `_context.md`) are
workspace-level files placed outside the workflow directory. All other
files are placed inside the workflow directory preserving their relative
path.

### Implementation: `reflow validate`

#### Addition to CLI

```python
validate_parser = subparsers.add_parser("validate")
validate_parser.add_argument("workflow", help="Workflow name")
```

Handler:

```python
def handle_validate(args):
    workspace = resolve_workspace(args)
    errors = []
    try:
        config = load_config(workspace)
        print("Config: ok")
    except ConfigError as e:
        print(f"Config: FAILED — {e}")
        return 25
    try:
        workflow = load_workflow(workspace, args.workflow, config)
        steps = ", ".join(workflow.steps)
        providers = ", ".join(
            set(s.provider or workflow.default_provider or config.default_provider
                for s in workflow.steps.values() if hasattr(s, "provider"))
        )
        print(f"Workflow '{args.workflow}': ok")
        print(f"  Steps: {steps}")
        print(f"  Entry: {workflow.entry}")
        print(f"  Providers: {providers}")
        return 0
    except ConfigError as e:
        print(f"Workflow '{args.workflow}': FAILED")
        print(f"  - {e}")
        return 25
```

### Scaffold tests

1. `reflow init myworkflow` creates all expected files.
2. Existing workflow directory causes error, no files written.
3. Existing `config.yaml` is skipped, not overwritten.
4. `--template single-agent` creates single-agent template files.
5. `--provider claude` generates Claude-specific config.
6. `--target spec.md` substitutes target path in workflow and creates
   stub file.
7. Generated workflow passes `reflow validate` without errors.
8. Generated workflow runs end-to-end with a mock provider that emits
   the expected `<route>` tags.

### Validate tests

1. Valid workflow reports success with step and provider summary.
2. Invalid config reports config error.
3. Invalid workflow reports workflow error with specific message.
4. Missing workflow directory reports clear error.

---

## Loader change: `entry` is optional

### Current behavior

`entry` is a required top-level field in `workflow.yaml`. Omitting it
is a validation error.

### New behavior

`entry` is optional. When omitted, the entry step is the first key in
the `steps` mapping. When provided, it must reference a declared step.

### Implementation

#### `loaders.py`

```python
entry = payload.get("entry")
if entry is None:
    entry = next(iter(steps_payload))
else:
    entry = _require_non_empty_string(entry, "workflow entry")
    if entry.startswith("@"):
        raise ConfigError("workflow entry must not begin with '@'.")
```

The validation that `entry` references a declared step remains unchanged
and runs after all steps are parsed.

### Tests

1. Workflow with explicit `entry` works unchanged.
2. Workflow without `entry` uses first declared step.
3. Workflow with `entry` referencing undeclared step fails validation.

---
