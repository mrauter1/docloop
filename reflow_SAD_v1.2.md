# Reflow v1.2 -- Architectural Specification

## 1. Purpose and normative status

This document is the normative architecture for Reflow v1.2.

It defines the minimum architecture required to implement Reflow as a thin, repeatable workflow loop runner around provider CLIs such as Codex CLI and Claude Code. It covers repository layout, workflow and config contracts, provider invocation, storage, human-in-the-loop behavior, policy enforcement, deterministic shell steps, resume, terminal behavior, testing, and implementation order.

Unless explicitly marked as informative or future work, every statement in this document is normative.

Reflow v1.2 is a single-controller CLI that repeatedly invokes providers in fresh one-shot mode, interprets structured step outcomes, enforces workspace policy, records operator inputs, and advances ordered workflows. It does not maintain a synthetic conversation ledger, does not replay provider sessions for correctness, and does not try to replace provider-native project behavior such as `AGENTS.md`, `CLAUDE.md`, or provider-owned skill systems.

Normative keywords mean:

* **MUST** = required
* **SHOULD** = recommended default
* **MAY** = optional

## 2. Design principles

Reflow v1.2 MUST follow these principles.

### 2.1 KISS

Reflow owns only the outer loop:

* workflow loading
* current step
* loop and cycle counts
* provider and shell invocation
* structured outcome parsing
* operator-input handling
* workspace policy checks
* logging
* run control and resume

### 2.2 DRY

There is one workflow schema, one provider config schema, one run-control format, one operator-input format, and one control-footing strategy for agent requests.

### 2.3 YAGNI

Reflow v1.2 does not implement:

* synthetic conversation history as runtime truth
* nested workflows
* graph execution
* provider-session replay
* plugin systems
* broad hook/event DSLs
* mandatory orchestrator-managed git commits
* built-in semantic validators beyond file-existence checks and workspace policy
* service or daemon mode
* web UI

### 2.4 Repo-first memory

Memory lives in repository files, provider-native project files, optional `.reflow/context.md`, the per-run `operator_inputs.md` log, and per-run history artifacts. Reflow does not mirror full working memory into `run.json`.

### 2.5 Fresh invocation model

Each agent iteration is a fresh provider process. Reflow MUST NOT rely on provider-native resume or hidden session continuity for correctness.

### 2.6 Provider-owned behavior

Provider-native instruction and memory systems remain provider-owned:

* Codex MAY use `AGENTS.md`, repository context, and provider-owned skills.
* Claude Code MAY use `CLAUDE.md`, repository context, and provider-owned project behavior.

Reflow MUST NOT attempt to recreate those systems in its own state files.

### 2.7 Human in the loop is first-class

Operator input is a first-class runtime invariant. Any `agent` step MAY request operator input. Reflow MUST support:

* inline interactive answering in the same controller process when possible
* explicit persisted waiting state when inline answering is not used
* `--full-auto` answering through a dedicated provider-driven answer pass

## 3. Scope

### 3.1 In scope

* ordered workflows with `agent` and `shell` steps
* workspace-root task isolation through `--workspace`
* provider defaults with optional per-step override
* file-backed step instructions
* simple transition contracts and reserved outcomes
* first-class operator-input requests
* workflow cycle budgets and per-step loop budgets
* per-step workspace policy with allowed writes, forbidden writes, and required files
* per-run operator-input logging
* per-iteration prompt/output logging
* resume at step and operator-input boundaries
* thin wrappers for Codex CLI and Claude Code
* shell steps for deterministic checks or scripts

### 3.2 Out of scope

* portable provider-native skill injection as a required cross-provider abstraction
* automatic git commits as a Reflow core behavior
* arbitrary post-step hooks
* graph branches or fan-out
* semantic success DSLs
* mid-provider-call resume
* long-running background controllers

### 3.3 Platform assumption

Reflow v1.2 assumes a POSIX-like shell environment for `shell` steps.

## 4. Provider model

Reflow integrates with provider CLIs as external tools.

Reflow v1.2 MUST follow these provider-integration rules:

1. Reflow MUST use fresh one-shot provider invocations for correctness.
2. Reflow MUST NOT rely on provider-native resume or session continuity for correctness.
3. Reflow MUST NOT manually append `AGENTS.md`, `CLAUDE.md`, or provider-native project skills into agent requests.
4. Reflow MUST NOT force-disable provider web search by default.
5. Reflow MUST NOT force Codex `--ephemeral` for correctness.
6. Reflow MAY expose provider-native flags through configuration, subject to reserved-flag rules in this document.
7. Reflow MUST treat provider-owned project behavior as ambient workspace context, not as workflow schema.

### 4.1 Default provider resolution

Reflow resolves the provider for an `agent` step in this order:

1. the step `provider`, if present
2. the workflow `default_provider`, if present
3. the config `default_provider`, if present

Validation MUST fail if no provider can be resolved for an `agent` step.

## 5. Canonical repository layout

```text
.reflow/
  config.yaml
  context.md                        # optional shared notes
  active.json                       # present while a controller owns the workspace
  workflows/
    <workflow_name>/
      workflow.yaml
      prompts/
        ...
      skills/
        ...
  runs/
    <run_id>/
      run.json
      history.jsonl
      operator_inputs.md
      steps/
        <step_name>/
          001/
            request.txt             # agent steps only
            command.txt             # shell steps only
            final.txt
            stdout.txt
            stderr.txt
            meta.json
          002/
            ...
```

Rules:

* `.reflow/` contains Reflow-owned assets only.
* Workflow definitions live under `.reflow/workflows/`.
* Per-run state lives under `.reflow/runs/`.
* Reflow MUST create `.reflow/runs/<run_id>/operator_inputs.md` for every run before the first iteration starts.
* The workspace root is the path passed by `--workspace`, or the current working directory when `--workspace` is omitted.

### 5.1 Shared path and encoding rules

Rules:

* All repo-relative paths in workflow files, config files, `run.json`, `active.json`, `history.jsonl`, and `meta.json` are resolved against the workspace root unless explicitly described as workflow-relative.
* Workflow-relative paths are resolved against `.reflow/workflows/<workflow_name>/`.
* Persisted repo-relative paths MUST use forward slashes.
* Persisted paths MUST NOT be absolute and MUST NOT escape the workspace after normalization.
* Reflow-owned JSON, YAML, Markdown, `request.txt`, and `command.txt` files MUST be UTF-8 encoded.
* JSON timestamps MUST use UTC RFC 3339 with a trailing `Z`.

### 5.2 Task isolation model

Task isolation is provided by the workspace directory, not by dynamic target-document naming.

Rules:

* A workflow run is scoped to one workspace.
* Multiple tasks SHOULD use separate workspace folders.
* A workflow MAY assume stable filenames inside the workspace such as `SAD.md`.
* Reflow MUST NOT require dynamic filename templating merely to avoid collisions between different tasks.

## 6. One active controller per workspace

Reflow v1.2 supports one active controller per workspace.

Rules:

* `active.json` exists only while a live controller process owns the workspace lock.
* `run`, `resume`, and `reply` MUST evaluate `active.json` before taking controller ownership.
* Historical completed, failed, blocked, or stopped runs remain under `.reflow/runs/`.

### 6.1 `active.json` contract

```json
{
  "run_id": "run_20260313T180000Z_docloop_refine",
  "workflow": "docloop_refine",
  "status": "running",
  "started_at": "2026-03-13T18:00:00Z",
  "updated_at": "2026-03-13T18:04:12Z",
  "controller_pid": 48123
}
```

Rules:

* `active.json` MUST be a JSON object with the fields shown above.
* `status` MUST be either `running` or `awaiting_input`.
* `run_id` MUST reference an existing run directory whose `run.json` status is `running` or `awaiting_input`.
* `controller_pid` is the PID of the Reflow process that currently owns the workspace lock.
* `run`, `resume`, and `reply` MUST treat `active.json` as stale if the referenced `run.json` is missing, terminal, or the controller PID is no longer alive.
* A non-stale `active.json` lock MUST cause a command-state refusal.

## 7. Workflow contract

Each workflow lives in:

```text
.reflow/workflows/<workflow_name>/workflow.yaml
```

### 7.1 Required top-level fields

```yaml
version: 1
name: docloop_refine
entry: write
steps: ...
```

Required:

* `version`
* `name`
* `entry`
* `steps`

Optional:

* `default_provider`
* `budgets`
* `operator_input`

Rules:

* `workflow.yaml` MUST parse to a YAML mapping.
* `version` MUST be the integer `1`.
* `name` MUST exactly match the workflow directory name.
* `steps` MUST be a non-empty mapping from step names to step definitions.
* Unknown top-level workflow fields MUST cause validation failure.

### 7.2 Step kinds

Reflow v1.2 supports exactly two step kinds:

* `agent`
* `shell`

Step names are case-sensitive and MUST be non-empty strings that do not start with `@`.

### 7.3 Workflow budgets

```yaml
budgets:
  max_cycles: 15
```

Optional fields:

* `max_cycles`

Rules:

* `max_cycles`, if present, MUST be a positive integer.
* If `max_cycles` is omitted, Reflow imposes no workflow-level cycle cap.
* `max_cycles` counts accepted non-input, non-`@retry` iterations for steps whose `count_toward_cycles` is true.
* Input-request iterations MUST NOT increment the workflow cycle count.
* If `max_cycles` is exceeded, the run MUST fail with `max_cycles_exceeded`.

### 7.4 Operator-input settings

```yaml
operator_input:
  full_auto_instructions: prompts/full_auto_answer.md
  max_auto_rounds: 3
```

Optional fields:

* `full_auto_instructions`
* `max_auto_rounds`

Rules:

* `full_auto_instructions`, if present, is a workflow-relative Markdown file path.
* If `full_auto_instructions` is omitted, Reflow MUST use a built-in default full-auto answer prompt.
* `max_auto_rounds`, if present, MUST be a positive integer. If omitted, the default is `3`.
* The path for resolved operator input is fixed in v1.2: `.reflow/runs/<run_id>/operator_inputs.md`.

### 7.5 Agent step contract

Simple form:

```yaml
write:
  kind: agent
  instructions: skills/write/
  max_loops: 30
  transitions:
    default: verify
```

Tagged-decision form:

```yaml
verify:
  kind: agent
  instructions: skills/verify/
  provider: codex
  max_loops: 30
  count_toward_cycles: true
  transitions:
    tag: promise
    default: INCOMPLETE
    map:
      COMPLETE: @done
      INCOMPLETE: write
      BLOCKED: @blocked
  policy:
    allow_write:
      - .docloop/criteria.md
      - .docloop/progress.txt
    required_files:
      - SAD.md
      - .docloop/context.md
      - .docloop/criteria.md
      - .docloop/progress.txt
```

Required fields for `agent`:

* `kind: agent`
* `instructions`
* `max_loops`
* `transitions`

Optional:

* `provider`
* `count_toward_cycles`
* `policy`

Rules:

* `instructions` is a workflow-relative path.
* `instructions` MAY point to a Markdown file.
* `instructions` MAY point to a directory containing `SKILL.md`.
* If `instructions` points to a directory, Reflow MUST load `SKILL.md` from that directory as the step instruction body.
* `provider`, if present, names a configured provider profile.
* `max_loops` MUST be a positive integer.
* `count_toward_cycles`, if omitted, defaults to `false`.
* Unknown fields on an `agent` step MUST cause validation failure.

### 7.6 Shell step contract

```yaml
criteria_gate:
  kind: shell
  cmd: ./scripts/check_criteria.sh .docloop/criteria.md
  max_loops: 30
  on_success: @done
  on_failure: write
```

Required fields for `shell`:

* `kind: shell`
* `cmd`
* `max_loops`
* `on_success`
* `on_failure`

Optional:

* `count_toward_cycles`
* `policy`

Rules:

* `cmd` is a non-empty shell command string.
* `max_loops` MUST be a positive integer.
* `count_toward_cycles`, if omitted, defaults to `false`.
* Unknown fields on a `shell` step MUST cause validation failure.

### 7.7 Transition targets and reserved outcomes

Transition targets MAY be:

* another step name
* `@done`
* `@retry`
* `@blocked`

Rules:

* Step names MUST NOT begin with `@`.
* Reserved outcomes are identified only by the `@` prefix.
* Reflow MUST treat any target beginning with `@` other than the reserved outcomes above as invalid.

## 8. Transitions contract

### 8.1 Simple default transition form

```yaml
transitions:
  default: verify
```

Rules:

* `default` is required.
* If no valid input request is emitted, the iteration accepts `default` as its transition target.
* No decision tag is required in this form.

### 8.2 Tagged-decision form

```yaml
transitions:
  tag: promise
  default: INCOMPLETE
  map:
    COMPLETE: @done
    INCOMPLETE: write
    BLOCKED: @blocked
```

Rules:

* `tag` names the final decision tag without angle brackets.
* `map` is a non-empty mapping from decision values to transition targets.
* `default` is the decision value used when no valid final decision tag is found.
* `default` MUST exist as a key in `map`.
* Decision values are case-sensitive strings.
* Reflow MUST parse the last valid matching line from `final.txt` using this regex shape, with the configured tag name substituted literally:

```regex
^\s*<TAG>([^<]+)</TAG>\s*$
```

* If a matching tag is found but its value is not present in `map`, the iteration is a protocol error.
* If no matching tag is found, Reflow MUST use the configured default decision value.

### 8.3 Questions block contract

A valid input request is a final `<questions>` block containing one or more `<question>` elements:

```text
<questions>
<question>Question 1</question>
<question>Question 2</question>
</questions>
```

Rules:

* The `<questions>` block MUST be the final non-empty structured control block in `final.txt`.
* If a valid `<questions>` block is present, no transition target is accepted from that iteration.
* The questions are processed in the order they appear.
* If `final.txt` contains `<question>` tags outside a valid final `<questions>` block, the iteration is a protocol error.
* If a valid `<questions>` block and a decision tag are both emitted in the same iteration, the iteration is a protocol error.
* Protocol errors are classified as `step_failed`.
* When retrying after a protocol error, Reflow MUST append a short runtime warning to the next rendered request explaining the required control structure.

## 9. Policy contract

Step policy is optional and controller-enforced.

```yaml
policy:
  allow_write:
    - SAD.md
    - .docloop/progress.txt
  forbid_write:
    - .docloop/criteria.md
  required_files:
    - SAD.md
    - .docloop/context.md
```

Optional policy fields:

* `allow_write`
* `forbid_write`
* `required_files`

Rules:

* Each field, if present, is a non-empty list of unique repo-relative path literals or glob patterns.
* Globs use normalized forward-slash paths and MAY include `**`.
* `allow_write` constrains non-Reflow workspace writes to matching paths only.
* `forbid_write` prohibits writes to matching paths.
* `forbid_write` wins on overlap with `allow_write`.
* `required_files` are checked only after an iteration has produced an accepted non-input transition target other than `@retry` or `@blocked`.
* Reflow-owned writes under `.reflow/` are excluded from write-policy evaluation.

### 9.1 Write-policy semantics

Rules:

* A write includes create, modify, delete, and rename.
* Reflow MUST compare workspace state immediately before child launch and immediately after local iteration completion.
* If a policy violation is detected, the run MUST fail terminally with `step_failed`.
* Reflow MUST NOT silently rerun a step after a policy violation, because the workspace may already be contaminated.

### 9.2 Required-file semantics

Rules:

* Required files are checked for existence only.
* A required file is present when the normalized path exists at check time.
* If required files are missing for an accepted transition target other than `@retry` or `@blocked`, the iteration is a failed step iteration.
* Required-file failure MAY rerun the same step if loops remain; otherwise the run fails with `max_loops_exceeded`.
* Content, schema, and semantic validation are out of scope for built-in required-file checks in v1.2.

## 10. Provider configuration contract

Reflow config lives in:

```text
.reflow/config.yaml
```

### 10.1 Canonical shape

```yaml
version: 1

default_provider: codex

providers:
  codex:
    kind: codex
    command: codex
    model: gpt-5.4
    timeout_sec: 1800
    args: []
    env: {}

  claude:
    kind: claude
    command: claude
    model: sonnet
    timeout_sec: 1800
    args: []
    env: {}
```

Required top-level fields:

* `version`
* `providers`

Optional top-level fields:

* `default_provider`

Required provider fields:

* `kind`
* `command`

Optional provider fields:

* `model`
* `timeout_sec`
* `args`
* `env`

Rules:

* `version` MUST be the integer `1`.
* `providers` MUST be a non-empty mapping.
* `default_provider`, if present, MUST reference a configured provider profile.
* `timeout_sec`, if omitted, defaults to `1800`.
* `args`, if omitted, defaults to `[]`.
* `env`, if omitted, defaults to `{}`.
* Unknown top-level or provider-level fields MUST cause validation failure.

### 10.2 Supported provider kinds

Supported kinds are:

* `codex`
* `claude`

### 10.3 Reserved flags

Reserved flags that MUST NOT appear in provider `args`:

For `codex`:

* `exec`
* `--cd`
* `--output-last-message`

For `claude`:

* `-p`
* `--print`
* `--output-format`

Validation MUST fail if reserved flags appear in provider args.

### 10.4 Invocation environment

Rules:

* Provider wrappers MUST execute the configured command directly as an argv vector, not through a shell.
* Provider child processes MUST run with the workspace root as current working directory.
* Provider child processes inherit the controller environment merged with provider `env`, with provider `env` overriding inherited keys.
* If `model` is omitted, Reflow MUST omit the provider-specific model flag and use the provider CLI default.

## 11. Minimal run state

Each run has one control file:

```text
.reflow/runs/<run_id>/run.json
```

### 11.1 Required fields

```json
{
  "run_id": "run_20260313T180000Z_docloop_refine",
  "workflow": "docloop_refine",
  "status": "running",
  "current_step": "verify",
  "step_loops": {
    "write": 2,
    "verify": 2
  },
  "cycle_count": 2,
  "started_at": "2026-03-13T18:00:00Z",
  "updated_at": "2026-03-13T18:04:12Z",
  "failure_type": null,
  "failure_reason": null,
  "pending_input": null
}
```

Required fields:

* `run_id`
* `workflow`
* `status`
* `current_step`
* `step_loops`
* `cycle_count`
* `started_at`
* `updated_at`

Optional fields:

* `failure_type`
* `failure_reason`
* `pending_input`

Rules:

* `current_step` is the step whose next iteration would run if the controller continues.
* `cycle_count` is the number of counted workflow cycles already consumed.
* `failure_type` and `failure_reason` MUST both be null or absent unless `status` is `failed`.
* `pending_input` MUST be null or absent unless `status` is `awaiting_input`.

### 11.2 Allowed statuses

* `running`
* `awaiting_input`
* `completed`
* `failed`
* `blocked`
* `stopped`

### 11.3 `pending_input` contract

When present, `pending_input` MUST be a JSON object with:

* `requested_at`
* `step`
* `loop`
* `questions`
* `auto_round`

Rules:

* `questions` is an ordered list of non-empty strings.
* `auto_round` is the number of full-auto answer passes already attempted for the current pending input request.
* `pending_input` is control-plane state only. Resolved answers belong in `operator_inputs.md`, not in `run.json`.

### 11.4 Write and recovery rules

Rules:

* Reflow MUST write the initial `run.json` before starting the first step iteration.
* `run.json` and `active.json` MUST be written atomically.
* Starting any step iteration is a persistence boundary.
* Before launching a provider or shell child, Reflow MUST reserve the next step loop number, create the iteration directory, write all pre-launch artifacts, and persist the updated `run.json`.
* If a controller later finds a reserved iteration without finalization, it MUST reconcile it before starting a new iteration.

## 12. History and per-iteration records

Each run also stores:

```text
.reflow/runs/<run_id>/history.jsonl
```

This is an append-only event log for operator visibility and recovery.

### 12.1 Required event types

Required event types are:

* `run_started`
* `resume_started`
* `reply_started`
* `input_requested`
* `input_resolved`
* `iteration_finished`
* `run_terminal`

Every history record MUST include:

* `ts`
* `type`
* `run_id`

Type-specific minimum fields:

* `run_started`: `workflow`, `entry_step`
* `resume_started`: `current_step`
* `reply_started`: `current_step`
* `input_requested`: `step`, `loop`, `question_count`
* `input_resolved`: `step`, `loop`, `mode`, `question_count`, `operator_inputs_file`
* `iteration_finished`: `step`, `loop`, `kind`, `status`, `exit_code`, `transition_target`, `iteration_dir`
* `run_terminal`: `status`, `failure_type`, `failure_reason`

### 12.2 Iteration directory

Each iteration directory contains:

* `final.txt`
* `stdout.txt`
* `stderr.txt`
* `meta.json`
* `request.txt` for `agent` steps
* `command.txt` for `shell` steps

Rules:

* The iteration directory name is the zero-padded decimal loop number, starting at `001`.
* `request.txt` contains the exact rendered request sent to the provider.
* `final.txt` is the text routed into decision parsing or question parsing for `agent` steps.
* For `shell` steps, `final.txt` MUST be identical to `stdout.txt`.

### 12.3 `meta.json`

Every iteration directory MUST contain `meta.json`.

Minimum shape:

```json
{
  "step": "verify",
  "loop": 3,
  "kind": "agent",
  "command_argv": ["codex", "exec", "--cd", "/repo", "--output-last-message", "...", "..."],
  "started_at": "2026-03-13T18:40:00Z",
  "ended_at": "2026-03-13T18:42:10Z",
  "exit_code": 0,
  "status": "ok",
  "transition_target": "@done",
  "input_requested": false,
  "question_count": 0,
  "decision_value": "COMPLETE",
  "required_files_missing": []
}
```

Required common fields:

* `step`
* `loop`
* `kind`
* `command_argv`
* `started_at`
* `ended_at`
* `exit_code`
* `status`
* `transition_target`
* `input_requested`
* `question_count`

Additional required fields for `agent` iterations:

* `decision_value`
* `required_files_missing`

Additional required fields for `shell` iterations:

* `command_text`

Rules:

* `status` MUST be one of `ok`, `failed`, or `interrupted`.
* `exit_code` MUST be an integer when Reflow observed a child-process exit status, and `null` otherwise.
* `transition_target` MUST be a step name, `@done`, `@retry`, `@blocked`, or `null`.
* `input_requested` is true when the iteration ended by emitting a valid questions block.
* `question_count` is `0` unless `input_requested` is true.
* `decision_value` MUST be `null` for simple default-transition steps and for agent iterations that ended by input request or failure before decision acceptance.
* `required_files_missing` is an empty list when no required-file check applied or when all required files existed.
* Reflow MUST write an initial `meta.json` before child launch and rewrite it when the iteration reaches its final local state.
* For interrupted iterations, `exit_code` MUST be `null`, `transition_target` MUST be `null`, and `input_requested` MUST be `false`.

### 12.4 `operator_inputs.md`

`operator_inputs.md` is append-only and compact.

Each resolved input entry MUST use this shape:

```text
## 2026-03-13T18:42:10Z | verify | loop 3 | human

Q1: ...
A1: ...

Q2: ...
A2: ...
```

Rules:

* `mode` MUST be either `human` or `auto`.
* The timestamp MUST be the resolution time, not merely the request time.
* The step and loop MUST identify the iteration that requested the input.

## 13. Agent request assembly

For an `agent` step, Reflow builds the actual provider request from:

1. the step instruction body
2. a small Reflow-owned control footer
3. an optional runtime protocol warning note when retrying after malformed control output

### 13.1 Instruction loading

Rules:

* If `instructions` points to a file, Reflow MUST load that file body.
* If `instructions` points to a directory, Reflow MUST load `SKILL.md` from that directory.
* Reflow MUST NOT recursively load arbitrary referenced files as part of instruction loading.
* Provider-owned ambient project files such as `AGENTS.md` or `CLAUDE.md` are not loaded through this mechanism.

### 13.2 Required footer content

The control footer MUST include:

* current workflow name
* current step name
* current loop number
* the path to `operator_inputs.md`
* the questions-block contract
* the transition contract for the step
* allowed and forbidden write summaries when policy is present
* required files when present

For tagged transitions, the footer MUST include the exact tag name and valid decision values.

## 14. Input-request lifecycle

### 14.1 Request detection

For every `agent` iteration, Reflow MUST inspect `final.txt` for a valid final `<questions>` block before accepting a transition.

### 14.2 Inline interactive mode

If Reflow is running interactively, stdin is available, and `--full-auto` is not set:

1. Reflow MUST persist `pending_input` and append an `input_requested` history record.
2. Reflow SHOULD prompt the operator inline within the same controller process.
3. After collecting answers, Reflow MUST append them to `operator_inputs.md`, clear `pending_input`, append an `input_resolved` history record, and start a fresh iteration of the same step.

### 14.3 Explicit waiting state

If inline answers are not collected immediately:

1. Reflow MUST persist `status: awaiting_input` with `pending_input`.
2. Reflow MUST update `active.json` if the same controller process is still waiting.
3. If the controller exits while awaiting input, it MUST remove `active.json`.
4. A later `reflow reply <run_id>` MUST provide the answers, append them to `operator_inputs.md`, clear `pending_input`, switch the run back to `running`, and start a fresh iteration of the same step.

### 14.4 Full-auto mode

If `--full-auto` is set and an input request is emitted:

1. Reflow MUST persist `pending_input` and append `input_requested`.
2. Reflow MUST invoke a fresh provider pass using the workflow `full_auto_instructions` file, or the built-in default if none is configured.
3. The full-auto answer pass MUST use the same resolved provider profile as the step that emitted the questions unless an implementation explicitly documents a different fixed rule.
4. The full-auto answer request MUST include the pending questions, workspace context, and a strict answer-only contract.
5. The full-auto answer pass MAY mention that repository inspection and web search are allowed when the provider and operator configuration permit them.
6. Reflow MUST append the resulting answers to `operator_inputs.md` with `mode: auto`, clear `pending_input`, append `input_resolved`, and start a fresh iteration of the same step.
7. If `max_auto_rounds` would be exceeded, the run MUST enter `awaiting_input` instead of auto-answering again.

## 15. Runtime algorithm

### 15.1 Run start

For `reflow run <workflow>`:

1. resolve the workspace root
2. load and validate `.reflow/config.yaml`
3. load and validate `.reflow/workflows/<workflow>/workflow.yaml`
4. refuse on any non-stale workspace lock conflict
5. create a unique `run_id` and run directory
6. create `operator_inputs.md`
7. write initial `run.json` with `status: running`
8. write `active.json`
9. append `run_started`
10. enter the step loop at `entry`

### 15.2 Agent step

For an `agent` step:

1. resolve the provider
2. check whether `step_loops[step] + 1 > max_loops`
3. if exceeded, fail the run with `max_loops_exceeded`
4. reserve the next iteration and persist pre-launch artifacts
5. render `request.txt`
6. invoke the provider
7. if the provider process cannot be created, finalize the iteration as failed and fail the run with `provider_unavailable`
8. if the provider child exists but exits nonzero or times out, finalize the iteration as failed and fail the run with `step_failed`
9. parse `final.txt` for a valid final `<questions>` block
10. if questions are present, tentatively select the control outcome `input_request`
11. otherwise parse transitions according to the step contract
12. if transition parsing hits a protocol error, finalize the iteration as failed; rerun if loops remain, else fail the run with `max_loops_exceeded`
13. apply write-policy checks before accepting either an input request or a transition target
14. if the selected control outcome is `input_request`, enter the input-request lifecycle in Section 14
15. apply required-file checks when applicable
16. if the accepted transition is `@retry`, rerun the same step if loops remain, else fail with `max_loops_exceeded`
17. if the step counts toward cycles and the accepted transition is not `@retry`, increment `cycle_count`
18. if a workflow `max_cycles` cap is configured and `cycle_count > max_cycles`, fail the run with `max_cycles_exceeded`
19. if the accepted transition is another step, update `current_step` and continue
20. if the accepted transition is `@done`, mark the run `completed`
21. if the accepted transition is `@blocked`, mark the run `blocked`

### 15.3 Shell step

For a `shell` step:

1. check whether `step_loops[step] + 1 > max_loops`
2. if exceeded, fail the run with `max_loops_exceeded`
3. reserve the next iteration and persist pre-launch artifacts
4. invoke `/bin/sh -lc "<cmd>"`
5. if the shell process cannot be created, finalize the iteration as failed and fail the run with `internal_error`
6. capture logs and mirror `stdout.txt` into `final.txt`
7. apply write-policy checks
8. map exit code `0` to `on_success`, nonzero to `on_failure`
9. if the accepted transition is `@retry`, rerun the same step if loops remain, else fail with `max_loops_exceeded`
10. if the step counts toward cycles and the accepted transition is not `@retry`, increment `cycle_count`
11. if a workflow `max_cycles` cap is configured and `cycle_count > max_cycles`, fail the run with `max_cycles_exceeded`
12. if the accepted transition is another step, update `current_step` and continue
13. if the accepted transition is `@done`, mark the run `completed`
14. if the accepted transition is `@blocked`, mark the run `blocked`

### 15.4 Terminalization

On any terminal outcome (`completed`, `failed`, `blocked`, or `stopped`):

1. write the final `run.json`
2. append `run_terminal`
3. remove `active.json` if it still points to this run
4. exit with the mapped CLI exit code

## 16. Failure model

Allowed terminal `failure_type` values are:

* `provider_unavailable`
* `step_failed`
* `max_loops_exceeded`
* `max_cycles_exceeded`
* `internal_error`

Classification rules:

* `provider_unavailable`: the controller cannot create or exec the configured provider process at all.
* `step_failed`: provider exited nonzero after startup, provider timed out, malformed control output, required files missing, or shell-step failure.
* `max_loops_exceeded`: current step exhausted its loop budget without an acceptable continuation.
* `max_cycles_exceeded`: workflow cycle budget was exceeded.
* `internal_error`: config loading failure, workflow validation failure, storage failure, or unexpected runtime bug.

## 17. Resume, reply, stop

### 17.1 Commands

Required commands:

```text
reflow run <workflow> [--workspace <path>] [--full-auto]
reflow resume <run_id> [--workspace <path>] [--full-auto]
reflow reply <run_id> [--workspace <path>] [--full-auto]
reflow status <run_id> [--workspace <path>]
reflow stop <run_id> [--workspace <path>]
reflow list [--workspace <path>]
```

### 17.2 Resume semantics

`resume` is for a run whose status is still `running` after controller interruption.

On resume, Reflow:

1. validates the run exists and is `running`
2. reacquires the workspace lock
3. reconciles any interrupted reserved iteration
4. appends `resume_started`
5. starts a fresh iteration of `current_step`

### 17.3 Reply semantics

`reply` is for a run whose status is `awaiting_input`.

Rules:

* `reply` MUST fail if `pending_input` is absent.
* In normal mode, `reply` SHOULD prompt the operator for answers inline.
* In `--full-auto`, `reply` MUST use the full-auto answer path.
* After resolving input, `reply` MUST append to `operator_inputs.md`, clear `pending_input`, set status back to `running`, append `reply_started`, and start a fresh iteration of the same step.

### 17.4 Stop semantics

`reflow stop <run_id>` or Ctrl+C during a live controller MUST:

1. locate the controller from `active.json` if present
2. stop the active subprocess if one exists
3. finalize any reserved current iteration as interrupted if necessary
4. mark the run `stopped` if it is not already terminal
5. complete terminalization

`stopped` is operator-driven and is not a workflow transition.

## 18. Provider wrappers

### 18.1 Codex wrapper

For `codex` providers, Reflow MUST invoke `codex exec` in one-shot mode, MUST set the working directory with `--cd`, and MUST capture the provider final message using `--output-last-message`.

Required shape:

```bash
codex exec \
  --cd <workspace> \
  [--model <model>] \
  [<provider args...>] \
  --output-last-message <iteration_dir/final.txt> \
  "<request>"
```

### 18.2 Claude wrapper

For `claude` providers, Reflow MUST invoke `claude -p` in one-shot print mode.

Recommended shape:

```bash
claude -p "<request>" \
  [--model <model>] \
  [<provider args...>]
```

Rules:

* For Codex, `final.txt` comes from `--output-last-message`.
* For Claude, `final.txt` is the captured plain-text stdout.
* Stdout and stderr MUST always be captured to files.

## 19. Shell steps and runtime environment

Shell steps are the v1.2 mechanism for deterministic checks or external scripts.

Rules:

* Reflow MUST execute shell steps as `/bin/sh -lc "<cmd>"`.
* The shell current working directory MUST be the workspace root.
* The shell environment MUST include:
  * `REFLOW_RUN_ID`
  * `REFLOW_WORKFLOW`
  * `REFLOW_STEP`
  * `REFLOW_LOOP`
  * `REFLOW_WORKSPACE`
  * `REFLOW_ITERATION_DIR`
* `command.txt` MUST contain the exact `cmd` string from the workflow.
* v1.2 does not define a generic trigger or hook system. Deterministic checks SHOULD be modeled as explicit `shell` steps.

## 20. Validation rules

Workflow validation MUST fail before execution if:

* required workflow fields are missing
* `name` does not match the workflow directory
* `entry` is not a declared step
* `default_provider`, if present, does not reference a configured provider
* `max_cycles < 1`
* `full_auto_instructions` is absolute, missing, or invalid
* `max_auto_rounds < 1`
* step kind is not `agent` or `shell`
* a step name begins with `@`
* `max_loops < 1`
* `count_toward_cycles` is not boolean
* `instructions` path is missing, absolute, invalid, or a directory without `SKILL.md`
* resolved provider does not exist
* transitions contain invalid targets
* tagged transitions omit `map` or use a `default` decision not present in `map`
* shell `on_success` or `on_failure` contains an invalid target
* policy paths are absolute, empty, duplicated, or escape the workspace
* config contains reserved provider flags
* unknown top-level or step-level fields are present

## 21. Exit codes

Recommended exit codes:

| Code | Meaning |
| ---- | ------- |
| 0 | completed |
| 20 | provider unavailable |
| 21 | step failed |
| 22 | max loops exceeded |
| 23 | max cycles exceeded |
| 24 | blocked |
| 25 | internal/config error |
| 26 | awaiting input |
| 27 | stopped |

Rules:

* `run`, `resume`, and `reply` MUST return the terminal or waiting exit code they reach.
* `status`, `list`, and `stop` MUST return `0` on success and `25` on command-state errors.

## 22. Testing requirements

### 22.1 Unit tests

Minimum unit tests:

* config validation
* workflow validation
* instruction loading from file and `SKILL.md`
* decision-tag parsing
* questions-block parsing
* protocol-error handling for malformed question output
* write-policy matching for literals and globs
* required-file checks
* loop counting
* cycle counting
* operator-input file formatting
* provider wrapper command construction
* exit-code mapping

### 22.2 Integration tests

Minimum integration tests:

* happy-path multi-step workflow
* inline interactive question handling
* deferred `reply` handling
* `--full-auto` answer flow
* malformed questions block
* missing decision tag with tagged-transition default
* invalid decision tag value
* required-files missing behavior
* write-policy violation
* shell success/failure routing
* provider unavailable
* max-loops failure
* max-cycles failure
* resume starts a fresh iteration of the current step
* stop marks the run `stopped`

## 23. Informative example: Doc-Loop style workflow

This section is informative.

The intended v1.2 shape for a Doc-Loop-like workflow is:

* a `write` agent step with a simple default transition to `verify`
* a `verify` agent step with tagged transitions on `<promise>...`
* optional shell gates such as a criteria-check script between verifier completion and `@done`
* shared run-level operator-input memory in `.reflow/runs/<run_id>/operator_inputs.md`
* workspace policy preventing writer and verifier from mutating the wrong files

## 24. Implementation sequence

### Phase 1

* config loading and validation
* workflow loading and validation
* storage layout and run control

### Phase 2

* provider wrappers
* request rendering
* transitions parsing

### Phase 3

* operator-input lifecycle
* `reply`
* `--full-auto`

### Phase 4

* policy enforcement
* shell-step runtime
* cycle accounting

### Phase 5

* end-to-end workflows
* integration tests with fixture-based provider outputs
