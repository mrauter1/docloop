# Reflow v1 — Architectural Specification

## 1. Purpose and normative status

This document is the normative architecture for Reflow v1.

It defines the minimum structure required to implement Reflow as a thin workflow loop runner around provider CLIs. It covers repository layout, workflow and config contracts, provider invocation, storage, routing, resume, terminal behavior, testing, and implementation order.

Unless explicitly marked as informative or future work, every statement in this document is normative.

Reflow v1 is a single-process CLI that repeatedly invokes a provider in fresh one-shot mode, inspects the provider’s emitted route tag, checks required files, and either repeats the current step or advances the workflow. It does not maintain a synthetic conversation ledger, does not run a separate evaluator, and does not try to reconstruct provider memory inside its own state files.

Normative keywords mean:

* **MUST** = required
* **SHOULD** = recommended default
* **MAY** = optional

## 2. Design principles

Reflow v1 MUST follow these principles.

### 2.1 KISS

Reflow owns only the outer loop:

* current step
* loop counts
* provider invocation
* route parsing
* required-file checks
* logging
* resume at step/iteration granularity

### 2.2 DRY

There is one workflow schema, one provider config schema, one route-tag parser, and one run-control format.

### 2.3 YAGNI

Reflow v1 does not implement:

* synthetic message history as runtime truth
* semantic evaluator passes
* nested workflows
* graph execution
* provider-session replay
* elaborate checkpoint state machines
* broad failure taxonomies
* schema validation for normal step outputs

### 2.4 Repo-first memory

Memory lives in repository files, optional `.reflow/context.md`, git history, and per-run logs. Reflow does not mirror memory into `run.json`.

### 2.5 Fresh invocation model

Each agent iteration is a fresh provider process. Reflow does not rely on provider-native resume or hidden session continuity for correctness.

## 3. Scope

### 3.1 In scope

* ordered workflows with `agent` and `shell` steps
* route-tag-based control flow
* required-file existence checks
* per-step loop caps
* thin wrappers for Codex CLI and Claude Code
* per-iteration prompt/output logging
* simple run control and resume
* operator stop / escalation

### 3.2 Out of scope

* nested workflows
* skill systems as a required abstraction
* provider-agnostic workflow indirection layers beyond named provider profiles
* parallel branches
* semantic success/failure DSLs
* output schema validation for ordinary step files
* mid-iteration resume
* service / daemon mode
* web UI

### 3.3 Platform assumption

Reflow v1 assumes a POSIX-like shell environment for `shell` steps.

## 4. Provider model

Reflow integrates with provider CLIs as external tools.

Provider-native instruction and memory systems remain provider-owned:

* Codex may use `AGENTS.md` and related project behavior.
* Claude Code may use `CLAUDE.md`, project settings, and optional memory behavior.

Reflow does not duplicate those systems.

Reflow v1 MUST follow these provider-integration rules:

1. Reflow MUST use fresh one-shot provider invocations for correctness.
2. Reflow MUST NOT rely on provider-native resume or session continuity for correctness.
3. Reflow MUST NOT manually append `AGENTS.md`, `CLAUDE.md`, or provider-native skills into prompts.
4. Reflow MUST NOT force-disable provider web search by default.
5. Reflow MUST NOT force Codex `--ephemeral` in v1.
6. Reflow MAY expose provider-native flags through configuration, subject to the reserved-flag rules in this document.

## 5. Canonical repository layout

```text
.reflow/
  config.yaml
  context.md                  # optional shared notes
  active.json                 # present only while a run is active
  workflows/
    <workflow_name>/
      workflow.yaml
      prompts/
        <step_name>.md
  runs/
    <run_id>/
      run.json
      history.jsonl
      steps/
        <step_name>/
          001/
            prompt.txt            # agent steps only
            command.txt           # shell steps only
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
* Per-run logs live under `.reflow/runs/`.
* `context.md` is optional shared note space. Reflow may mention it to providers, but it is not required.

### 5.1 Shared file and path conventions

Unless a section says otherwise, the workspace root is the path passed by `--workspace`, or the current working directory when `--workspace` is omitted.

Rules:

* All repo-relative paths in workflow files, config files, `run.json`, `active.json`, `history.jsonl`, and `meta.json` are resolved against the workspace root.
* Paths explicitly described as workflow-relative are resolved against `.reflow/workflows/<workflow_name>/`.
* Reflow-owned JSON, YAML, Markdown, `prompt.txt`, and `command.txt` files MUST be UTF-8 encoded.
* JSON timestamps MUST use UTC RFC 3339 format with a trailing `Z`.
* Persisted repo-relative paths MUST use forward slashes, MUST NOT be absolute, and MUST NOT escape the workspace after normalization.
* Reflow MUST create parent directories as needed under `.reflow/` and MUST NOT write Reflow-owned state outside the workspace.

## 6. One active run per workspace

Reflow v1 supports **one active run per workspace**.

Rules:

* `active.json` exists only while a run is `running`.
* `reflow run <workflow>` and `reflow resume <run_id>` MUST evaluate `active.json` before taking controller ownership of the workspace.
* `reflow run <workflow>` MUST fail if `active.json` already points to a running run.
* Historical completed, failed, or escalated runs remain in `.reflow/runs/`.

### 6.1 `active.json` contract

```json
{
  "run_id": "run_20260311T120000Z_review_fix_verify",
  "workflow": "review_fix_verify",
  "status": "running",
  "started_at": "2026-03-11T12:00:00Z",
  "updated_at": "2026-03-11T12:15:21Z",
  "controller_pid": 48123
}
```

Rules:

* `active.json` MUST be a JSON object with the fields shown above.
* `controller_pid` is the PID of the Reflow process that currently owns the workspace lock.
* `run_id` MUST reference an existing run directory whose `run.json` status is `running`.
* `run` and `resume` MUST treat `active.json` as stale if the referenced `run.json` is missing or terminal, or if `controller_pid` is no longer alive.
* A stale `active.json` lock MUST be removed or replaced before a new controller process continues.
* If `active.json` is non-stale, `reflow run <workflow>` MUST fail as a command-state error without modifying `active.json`, any existing `run.json`, or any `history.jsonl`.
* If `active.json` is non-stale, `reflow resume <run_id>` MUST fail as a command-state error without modifying `active.json`, any `run.json`, or any `history.jsonl`, regardless of whether the live lock belongs to `<run_id>` itself or to some other running run.
* `status` and `list` MUST NOT create or modify `active.json`.

## 7. Workflow contract

Each workflow lives in:

```text
.reflow/workflows/<workflow_name>/workflow.yaml
```

### 7.1 Required top-level fields

```yaml
name: review_fix_verify
entry: review
steps: ...
```

Required:

* `name`
* `entry`
* `steps`

Rules:

* `workflow.yaml` MUST parse to a YAML mapping.
* `name` MUST exactly match the workflow directory name `<workflow_name>`.
* `steps` MUST be a non-empty mapping from step names to step definitions.
* Unknown top-level workflow fields MUST cause validation failure.

### 7.2 Step kinds

Reflow v1 supports exactly two step kinds:

* `agent`
* `shell`

Step names are case-sensitive and MUST be non-empty strings that are not `done`, `retry`, or `escalate`.

### 7.3 Agent step contract

```yaml
review:
  kind: agent
  prompt: prompts/review.md
  provider: claude
  max_loops: 3
  routes: [screen, done, retry, escalate]
  required_files:
    - reports/review-findings.md
```

Required fields for `agent`:

* `kind: agent`
* `prompt`
* `provider`
* `max_loops`
* `routes`

Optional:

* `required_files`

Rules:

* `prompt` is a file path relative to the workflow directory.
* `prompt` MUST NOT be absolute and MUST NOT contain parent traversal after normalization.
* `provider` names a configured provider profile from `.reflow/config.yaml`.
* `max_loops` is a positive integer.
* `routes` is a non-empty list of unique allowed route values.
* Route values are case-sensitive strings.
* `required_files`, if present, is a list of unique repo-relative file paths.
* Unknown fields on an `agent` step MUST cause validation failure.

### 7.4 Shell step contract

```yaml
verify:
  kind: shell
  cmd: ./scripts/verify.sh
  max_loops: 5
  on_success: done
  on_failure: implement
```

Required fields for `shell`:

* `kind: shell`
* `cmd`
* `max_loops`
* `on_success`
* `on_failure`

Rules:

* `cmd` is a non-empty shell command string.
* `on_success` and `on_failure` are transition targets.
* `max_loops` is a positive integer.
* Unknown fields on a `shell` step MUST cause validation failure.

### 7.5 Transition targets

A transition target may be:

* another step name
* `done`
* `escalate`

Additionally, agent steps may emit:

* `retry`

`retry` means rerun the same step.

## 8. Workflow validation

Workflow validation MUST fail before execution if:

* `workflow.yaml` is missing or cannot be parsed as YAML
* `name`, `entry`, or `steps` is missing
* `name` does not match the workflow directory name
* `entry` is not a declared step
* `steps` is empty or is not a mapping
* a step name is duplicated
* a step name is empty or is one of `done`, `retry`, or `escalate`
* a step kind is not `agent` or `shell`
* an `agent` step is missing required fields
* a `shell` step is missing required fields
* `max_loops < 1`
* `prompt` file does not exist
* `prompt` is absolute
* `prompt` contains parent traversal (`..`)
* `provider` does not exist in config
* `routes` is empty, contains duplicates, or contains an empty value
* any route target is not:

  * a declared step
  * `done`
  * `retry` for agent steps
  * `escalate`
* `cmd` is empty
* any `required_files` path is absolute
* any `required_files` path contains parent traversal (`..`)
* `required_files` contains duplicates or empty values
* unknown workflow-level or step-level fields are present

## 9. Provider configuration contract

Reflow config lives in:

```text
.reflow/config.yaml
```

### 9.1 Canonical shape

```yaml
providers:
  claude:
    kind: claude
    command: claude
    model: sonnet
    timeout_sec: 1800
    args: []
    env: {}

  codex:
    kind: codex
    command: codex
    model: gpt-5.4
    timeout_sec: 1800
    args: []
    env: {}
```

Required provider fields:

* `kind`
* `command`

Optional:

* `model`
* `timeout_sec`
* `args`
* `env`

Rules:

* `.reflow/config.yaml` MUST parse to a YAML mapping.
* `providers` MUST be a non-empty mapping from provider profile name to provider configuration.
* Provider profile names are case-sensitive strings and are the values referenced by workflow `provider` fields.
* `command` is a non-empty executable name or absolute path.
* `model`, if present, is a non-empty string.
* `timeout_sec`, if present, is a positive integer. If omitted, the default is `1800`.
* `args`, if present, is an ordered list of strings. If omitted, the default is `[]`.
* `env`, if present, is a mapping of string keys to string values. If omitted, the default is `{}`.
* Unknown top-level config fields and unknown provider fields MUST cause validation failure.

### 9.2 Supported provider kinds

Supported kinds are:

* `claude`
* `codex`

### 9.3 Reserved flags

Reflow manages a small set of wrapper-critical flags.

Reserved flags that MUST NOT appear in provider `args`:

For `codex`:

* `exec`
* `--cd`
* `--output-last-message`

For `claude`:

* `-p`
* `--print`
* `--output-format`

Reserved-flag validation applies only to flags that would break Reflow’s wrapper contract. It does not attempt to restrict every provider-specific flag.

If reserved flags appear in provider `args`, validation MUST fail.

### 9.4 Invocation environment

Rules:

* Provider wrappers MUST execute the configured `command` directly as an argv vector, not through a shell.
* If `command` is not absolute, it is resolved via the controller process `PATH`.
* Provider child processes MUST run with the workspace root as their current working directory.
* Provider child processes inherit the controller environment merged with provider `env`, with provider `env` overriding inherited keys of the same name.
* If `model` is omitted, Reflow MUST omit the provider-specific model flag and use the provider CLI default.

### 9.5 Config validation

Config validation MUST fail before execution if:

* `.reflow/config.yaml` is missing or cannot be parsed as YAML
* `providers` is missing, empty, or is not a mapping
* a provider profile is missing `kind` or `command`
* a provider `kind` is not one of the supported kinds
* `command` is empty
* `model` is present but empty
* `timeout_sec < 1`
* `args` is not a list of strings
* `env` is not a mapping of string keys to string values
* reserved flags appear in `args`
* unknown config-level or provider-level fields are present

## 10. Minimal run state

Each run has one control file:

```text
.reflow/runs/<run_id>/run.json
```

### 10.1 Required fields

```json
{
  "run_id": "run_20260311T120000Z_review_fix_verify",
  "workflow": "review_fix_verify",
  "status": "running",
  "current_step": "implement",
  "step_loops": {
    "review": 1,
    "screen": 1,
    "implement": 3
  },
  "started_at": "2026-03-11T12:00:00Z",
  "updated_at": "2026-03-11T12:15:21Z",
  "failure_type": null,
  "failure_reason": null
}
```

Required fields:

* `run_id`
* `workflow`
* `status`
* `current_step`
* `step_loops`
* `started_at`
* `updated_at`

Optional failure fields:

* `failure_type`
* `failure_reason`

Rules:

* `run_id` MUST be unique within `.reflow/runs/`. The recommended format is `run_<UTC basic timestamp>_<workflow_name>`, with an additional suffix if needed for uniqueness.
* `current_step` MUST always be the step whose next iteration would run if the status is `running`, or the step whose transition or failure produced the current terminal status otherwise.
* `step_loops` contains only visited steps. An absent step key means zero iterations.
* `failure_type` and `failure_reason` MUST both be null or absent unless `status` is `failed`.
* `updated_at` MUST be rewritten every time `run.json` changes.

### 10.2 Allowed statuses

* `running`
* `completed`
* `failed`
* `escalated`

### 10.3 Run state rule

`run.json` is control plane only.

It MUST NOT be used to mirror:

* provider memory
* full context
* synthetic message history
* semantic evaluation results

### 10.4 Write and recovery rules

Rules:

* Reflow MUST write the initial `run.json` before starting the first step iteration.
* `run.json` and `active.json` MUST be written atomically using replace-on-success semantics such as temp-file plus rename.
* Starting any step iteration is a persistence boundary. Before launching a provider or shell child, Reflow MUST:

  1. compute the next loop number `n = step_loops[current_step] + 1`
  2. create the iteration directory for that exact loop number
  3. write all launch-independent iteration artifacts required by Section 11
  4. atomically rewrite `run.json` with `current_step` unchanged and `step_loops[current_step] = n`

* The child process MUST NOT be launched until the step-start rewrite above succeeds.
* If a controller later observes that the highest existing iteration directory number for `current_step` is greater than the persisted `step_loops[current_step]`, it MUST reconcile by treating that highest directory as a reserved interrupted iteration, finalizing it per Section 11, and rewriting `run.json` so `step_loops[current_step]` matches before any new iteration starts.
* After each iteration reaches a local terminal state (`ok`, `failed`, or `interrupted`) and after each terminal run transition, Reflow MUST persist the updated `run.json` before removing `active.json` or exiting the controller process.

## 11. History and per-iteration records

Each run also stores:

```text
.reflow/runs/<run_id>/history.jsonl
```

This is an append-only event log for operator visibility, not provider memory.

### 11.1 Record format and event types

`history.jsonl` is UTF-8 JSON Lines: one JSON object per line, newline terminated, appended in execution order. Existing records MUST NOT be rewritten.

Every history record MUST include:

* `ts`
* `type`
* `run_id`

Required event types are:

* `run_started`
* `resume_started`
* `iteration_finished`
* `run_terminal`

Type-specific required fields:

* `run_started`: `workflow`, `entry_step`
* `resume_started`: `current_step`
* `iteration_finished`: `step`, `loop`, `kind`, `status`, `exit_code`, `transition_target`, `iteration_dir`
* `run_terminal`: `status`, `failure_type`, `failure_reason`

Rules:

* `iteration_finished.status` MUST be one of `ok`, `failed`, or `interrupted`.
* `iteration_finished.exit_code` MUST be an integer when Reflow observed a child-process exit status, and `null` otherwise.
* `iteration_finished.transition_target` MUST be a step name, `done`, `escalate`, or `null`.
* Every created iteration directory MUST have exactly one corresponding `iteration_finished` record.
* If an iteration causes the run to become terminal, its `iteration_finished` record MUST be appended before the `run_terminal` record.

Example `iteration_finished` record:

```json
{
  "ts": "2026-03-11T12:15:21Z",
  "type": "iteration_finished",
  "run_id": "run_20260311T120000Z_review_fix_verify",
  "step": "implement",
  "loop": 3,
  "kind": "agent",
  "status": "ok",
  "exit_code": 0,
  "transition_target": "verify",
  "iteration_dir": ".reflow/runs/run_.../steps/implement/003"
}
```

### 11.2 Iteration directory

Each iteration directory contains:

* `final.txt`
* `stdout.txt`
* `stderr.txt`
* `meta.json`
* `prompt.txt` for `agent` steps
* `command.txt` for `shell` steps

Rules:

* The iteration directory name is the zero-padded decimal loop number for that step, starting at `001`.
* `prompt.txt` contains the exact rendered prompt sent to the provider.
* `command.txt` contains the exact `cmd` string from the workflow definition.
* `stdout.txt`, `stderr.txt`, `final.txt`, and `meta.json` MUST exist for every iteration directory, including interrupted iterations and iterations whose child process never started.
* If no bytes were captured for one of `stdout.txt`, `stderr.txt`, or `final.txt`, that file MUST still exist as an empty file.
* `final.txt` MUST exist for every iteration.
* For `agent` steps, `final.txt` is the text routed into the route-tag parser.
* For `shell` steps, `final.txt` MUST be byte-for-byte identical to `stdout.txt`.
* If a provider exits before producing a final message, or if the child process never starts, Reflow MUST still create `final.txt` as an empty file unless bytes were already captured into it.

### 11.3 `meta.json` minimum contract

```json
{
  "step": "implement",
  "loop": 3,
  "kind": "agent",
  "command_argv": ["codex", "exec", "--cd", "/repo", "--output-last-message", "...", "..."],
  "provider": "codex",
  "started_at": "2026-03-11T12:14:10Z",
  "ended_at": "2026-03-11T12:15:21Z",
  "exit_code": 0,
  "route": "verify",
  "transition_target": "verify",
  "required_files_missing": [],
  "status": "ok"
}
```

`meta.json` MUST include these common fields:

* `step`
* `loop`
* `kind`
* `command_argv`
* `started_at`
* `ended_at`
* `exit_code`
* `status`
* `transition_target`

`status` MUST be one of:

* `ok`
* `failed`
* `interrupted`

Additional required fields for `agent` iterations:

* `provider`
* `route`
* `required_files_missing`

Additional required fields for `shell` iterations:

* `command_text`

Rules:

* `meta.json` MUST exist for every iteration directory, including interrupted iterations and launch-failure iterations.
* Reflow MUST write an initial `meta.json` before child launch using the interrupted-form defaults defined below, with `started_at` equal to the reservation time and `ended_at` initially equal to the same timestamp. Reflow MUST rewrite `meta.json` when the iteration later reaches its final local state.
* `command_argv` MUST record the exact argv Reflow attempted to execute. For shell steps, this is the shell argv, not just the workflow `cmd` string.
* `exit_code` MUST be an integer when Reflow observed a child-process exit status, and `null` otherwise.
* `transition_target` records the actual accepted workflow target after applying route parsing, required-file checks, or shell-step success/failure mapping. It MUST be the current step name for an accepted `retry` route.
* `transition_target` MUST be `null` when the iteration ended without producing an accepted workflow transition.
* `route` MUST be `null` when an `agent` iteration ended before a valid route tag was accepted.
* `required_files_missing` is an empty list when no required-file check applied or when all required files existed.
* `status: ok` means the iteration produced an accepted `transition_target`.
* `status: failed` means the iteration reached a local terminal state without an accepted transition because of provider failure, shell-launch failure, missing or invalid route tags, missing required files, or another launch/finalization failure that still reserved an iteration.
* `status: interrupted` means the iteration was reserved and counted, but the controller stopped or lost control before the iteration reached a local `ok` or `failed` state.
* For interrupted iterations, `exit_code` MUST be `null`, `transition_target` MUST be `null`, and `route` MUST be `null`.
* If Reflow attempts to launch a reserved iteration and no child process is created, Reflow MUST finalize it as `status: failed` with `exit_code: null`, `transition_target: null`, `route: null` for `agent` steps, and empty output files unless bytes had already been captured.
* If a controller crash or external interruption leaves behind an iteration directory without its required `iteration_finished` record, the next successful `resume` or `stop` reconciliation for that run MUST finalize that iteration as `status: interrupted`, rewrite `meta.json` if needed, append the missing `iteration_finished` record, and only then continue.

### 11.4 Observability and sensitivity

Rules:

* Reflow MUST persist prompt, command, stdout, stderr, and final-output artifacts verbatim. It MUST NOT redact or rewrite child-process output.
* These artifacts may contain secrets. Reflow MUST rely on normal workspace filesystem permissions and MUST NOT make Reflow-owned files more permissive than the current process default.
* Reflow SHOULD stream child stdout and stderr directly to their log files rather than buffering full outputs in memory.

## 12. Step loop semantics

`max_loops` is the total number of times a step may run within a single run.

Important rule:

* loop counts do **not** reset when a step is revisited later in the workflow
* loop counts increment as part of the step-start persistence boundary defined in Section 10.4
* any iteration whose numbered directory has been reserved by that boundary counts toward `max_loops`, including retries, required-file failures, launch failures, and interrupted iterations

Example:

* `implement` runs once
* `verify` sends flow back to `implement`
* the next `implement` run increments the same `implement` loop counter

This is the simplest way to cap infinite bouncing.

## 13. Route tag contract

Every `agent` step must end with exactly one final route tag on its own line:

```text
<route>VALUE</route>
```

`VALUE` must be one of the current step’s declared `routes`.

Route matching is case-sensitive.

Examples:

```text
<route>retry</route>
<route>screen</route>
<route>done</route>
<route>escalate</route>
```

### 13.1 Parsing rule

Reflow MUST:

* scan the provider’s final text
* find all lines matching the route-tag pattern
* use the **last** valid matching line
* extract `VALUE`
* validate `VALUE` against the step’s declared routes

A valid route-tag line is:

```regex
^\s*<route>([^<]+)</route>\s*$
```

### 13.2 Missing or invalid route tags

If the final text contains no valid route tag, or if the value is not allowed for the step:

* the iteration is a failed step iteration
* the step is rerun if `max_loops` has not been reached
* otherwise the run fails with `max_loops_exceeded`
* a missing or unreadable `final.txt` is treated the same as no valid route tag

## 14. Prompt assembly

For an `agent` step, Reflow builds the actual prompt from:

1. the step prompt file contents
2. a small Reflow-owned footer

The Reflow footer MUST include:

* current workflow name
* current step name
* allowed route values
* required files, if any
* the exact route-tag contract

A conforming footer is:

```text
Workflow: review_fix_verify
Step: implement

Allowed routes:
- verify
- retry
- escalate

Required files before selecting a non-retry, non-escalate route:
- reports/implementation-summary.md

When you are finished, end your response with exactly one route tag on its own line:
<route>VALUE</route>
```

Reflow MAY also mention:

* `.reflow/context.md` if it exists
* that the provider should use repo files as working memory

Rules:

* Reflow MUST append the footer after the step prompt contents and MUST persist the exact rendered prompt to `prompt.txt`.
* Aside from the footer and optional references already allowed in this section, Reflow MUST NOT inject synthetic conversation history, provider-session replay data, or generated summaries of prior iterations.

## 15. Required-file checks

`required_files` are checked by existence only.

Rules:

* checks are repo-relative
* checks happen after a valid route tag is parsed
* checks apply only when the route is:

  * another step name
  * `done`

Checks do **not** apply when the route is:

* `retry`
* `escalate`

If required files are missing for a non-`retry`, non-`escalate` route:

* the iteration is treated as a failed step iteration
* that iteration is recorded with failed iteration status in `meta.json` and `history.jsonl`
* the same step is rerun if loops remain
* otherwise the run fails with `max_loops_exceeded`

Additional rules:

* A required file is considered present when the normalized path exists in the workspace at check time.
* Files are checked for existence only; content, type, and schema are out of scope for v1.
* An I/O error while checking a path, other than simple not-found, is an `internal_error`.

## 16. Provider wrappers

Reflow has thin wrappers for Codex and Claude.

### 16.1 Codex wrapper

For `codex` providers, Reflow MUST invoke `codex exec` in one-shot mode, MUST set the working directory with `--cd`, and MUST capture the provider’s final message using `--output-last-message <iteration_dir/final.txt>`. Reflow MUST NOT require `codex exec resume` or `--ephemeral` for correctness.

Required invocation shape:

```bash
codex exec \
  --cd <workspace> \
  [--model <model>] \
  [<provider args...>] \
  --output-last-message <iteration_dir/final.txt> \
  "<prompt>"
```

Rules:

* stdout and stderr are still captured to files
* if Codex exits without writing the `--output-last-message` target, Reflow MUST leave `final.txt` present as an empty file
* if the workspace is not a Git repo and the deployment wants to allow that, the operator may include `--skip-git-repo-check` in provider args

### 16.2 Claude wrapper

For `claude` providers, Reflow MUST invoke `claude -p` in one-shot print mode. Plain-text print mode is the default Reflow path in v1. JSON and stream-JSON modes are optional provider capabilities, but they are not required for route parsing.

Recommended invocation shape:

```bash
claude -p "<prompt>" \
  [--model <model>] \
  [<provider args...>]
```

Rules:

* stdout is written to both `stdout.txt` and `final.txt`
* stderr is written to `stderr.txt`

### 16.3 Provider output rule

The route parser always runs against `final.txt`.

* for Codex, `final.txt` comes from `--output-last-message`
* for Claude, `final.txt` is the captured plain-text stdout

### 16.4 Common wrapper rules

Rules:

* Provider wrappers MUST execute with the workspace root as their current working directory.
* If `timeout_sec` elapses, Reflow MUST terminate the provider process, capture any remaining output, record the iteration with `exit_code: null`, and classify the run as `step_failed`.
* `provider_unavailable` applies only when the controller cannot create or exec the configured provider process at all, such as OS-level `exec` failures for the configured `command`.
* Once the provider child process exists, any CLI-reported rejection or nonzero exit, including authentication errors, invalid model errors, repo-check failures, unsupported-flag errors, quota errors, or ordinary provider/tool failures, MUST be classified as `step_failed`.
* `meta.json.command_argv` MUST record the exact argv used for the child process.

## 17. Shell steps

A `shell` step runs its `cmd` as a shell command string.

To keep v1 simple, Reflow assumes a POSIX shell environment for `shell` steps.

Recommended execution:

```bash
/bin/sh -lc "<cmd>"
```

Rules:

* stdout and stderr are captured to iteration files
* exit code `0` transitions to `on_success`
* nonzero exit transitions to `on_failure`
* the command executes with the workspace root as current working directory
* shell steps inherit the controller environment unchanged; workflow-defined shell-step env overrides are out of scope for v1
* `command.txt` MUST be written before the shell command is launched
* v1 has no built-in shell-step timeout

`on_success` and `on_failure` may each be:

* another step name
* `done`
* `escalate`

A shell step does not use route tags.

If Reflow cannot start `/bin/sh` or cannot create the shell child process at all, the reserved iteration MUST be finalized as `failed` with `exit_code: null`, and the run MUST fail with `internal_error`.

## 18. Failure model

Keep the failure taxonomy minimal.

Allowed terminal `failure_type` values are:

* `provider_unavailable`
* `step_failed`
* `max_loops_exceeded`
* `internal_error`

### 18.1 Classification rules

`provider_unavailable`

* the controller cannot create or exec the configured provider command at all
* this covers OS-level launch failures such as missing executables or permission/format errors on the configured provider command

`step_failed`

* a provider child process was created but the iteration did not reach an accepted workflow transition
* this includes provider nonzero exits, provider timeouts, authentication failures reported by the provider CLI, invalid model errors, repo-check failures, quota failures, and other provider-side request rejections

`max_loops_exceeded`

* current step has reached `max_loops` and still has not produced an acceptable transition
* repeated `retry` routes, missing or invalid route tags, or missing required files eventually exhaust the current step loop budget

`internal_error`

* config loading failure
* workflow validation failure
* storage failure
* required-file check I/O failure
* shell launch failure
* unexpected runtime bug

Free-form `failure_reason` text carries the details.

### 18.2 Failure recording rules

Rules:

* If `reflow run <workflow>` fails during config or workflow preflight, the command MUST exit with the mapped error code and MUST NOT create a run directory or `active.json`.
* Once a run directory exists, any terminal failure that arose from a reserved iteration MUST finalize that iteration and append its `iteration_finished` record before the `run_terminal` record is appended.
* Once a run directory exists, any terminal failure MUST set `run.json.status` to `failed`, populate `failure_type`, update `updated_at`, append a `run_terminal` history record, and remove `active.json`.
* `completed` and `escalated` runs MUST leave `failure_type` and `failure_reason` null or absent.

## 19. Runtime algorithm

This is the authoritative loop algorithm.

### 19.1 Run start

For `reflow run <workflow>`:

1. resolve the workspace root
2. load and validate `.reflow/config.yaml`
3. load and validate `.reflow/workflows/<workflow>/workflow.yaml`
4. if preflight validation fails, exit without creating a run directory or `active.json`
5. evaluate the workspace lock under Section 6.1 and refuse on any non-stale lock conflict
6. create a unique `run_id` and run directory
7. write the initial `run.json` with `status: running`, `current_step: <entry>`, and an empty `step_loops` map
8. write `active.json` for the new controller PID
9. append a `run_started` record to `history.jsonl`
10. enter the step loop at the workflow entry step

### 19.2 Agent step

For an `agent` step:

1. load the step definition
2. check whether `step_loops[step] + 1 > max_loops`
3. if exceeded, fail the run with `max_loops_exceeded`
4. reserve the next iteration and persist its pre-launch artifacts and loop count as required by Sections 10.4 and 11
5. invoke the provider
6. if the provider command could not be created or exec'd, finalize the reserved iteration as `failed` and fail the run with `provider_unavailable`
7. if the provider child was created but exits nonzero or times out, finalize the reserved iteration as `failed` and fail the run with `step_failed`
8. parse the last valid route tag from `final.txt`
9. if route missing or invalid:

* rerun same step if loops remain
* else fail with `max_loops_exceeded`

10. if route is `retry`:

* rerun same step if loops remain
* else fail with `max_loops_exceeded`

11. if route is `escalate`:

* mark run `escalated`
* stop

12. if route is a next step or `done`:

* check required files
* if missing:

  * rerun same step if loops remain
  * else fail with `max_loops_exceeded`

13. if route is `done` and files are okay:

* mark run `completed`
* stop

14. if route is another step and files are okay:

* set `current_step` to that step
* continue loop

### 19.3 Shell step

For a `shell` step:

1. load the step definition
2. check whether `step_loops[step] + 1 > max_loops`
3. if exceeded, fail the run with `max_loops_exceeded`
4. reserve the next iteration and persist its pre-launch artifacts and loop count as required by Sections 10.4 and 11
5. invoke the shell command
6. if the shell process cannot be created, finalize the reserved iteration as `failed` and fail the run with `internal_error`
7. capture logs and mirror `stdout.txt` into `final.txt`
8. map exit code:

   * `0` -> `on_success`
   * nonzero -> `on_failure`
9. apply the target:

   * `done` -> completed
   * `escalate` -> escalated
   * step name -> move to that step

### 19.4 Terminalization

On any terminal outcome (`completed`, `failed`, or `escalated`):

1. write the final `run.json`
2. append a `run_terminal` history record
3. remove `active.json` if it still points to this run
4. exit with the mapped CLI exit code

## 20. Resume model

Resume is deliberately simple.

### 20.1 Command

```text
reflow resume <run_id> [--workspace <path>]
```

### 20.2 Semantics

On resume, Reflow:

1. loads `run.json`
2. verifies the run directory exists, `run.json` is readable, and status is `running`
3. evaluates `active.json` under Section 6.1:

* stale locks are repaired or replaced before the resume controller proceeds
* any non-stale live lock causes `resume` to refuse without modifying `active.json`, any `run.json`, or any `history.jsonl`

4. writes a fresh `active.json` for the resuming controller PID
5. reconciles the latest reserved iteration for `current_step` per Sections 10.4 and 11 before starting anything new
6. appends a `resume_started` history record naming `current_step`
7. starts a new iteration of `current_step`
8. continues normally

### 20.3 Important rule

Reflow v1 does **not** resume inside a partially completed provider invocation.

If the previous iteration was interrupted mid-run:

* Reflow does not try to recover inside that iteration
* it first preserves that prior iteration as `interrupted` if its history/meta finalization is still incomplete
* it then starts a fresh iteration of the current step
* it does not delete or rewrite child-output artifacts from the interrupted iteration

This is intentional.

## 21. Operator stop

`reflow stop <run_id>` or Ctrl+C during a running loop MUST:

1. locate the controller from `active.json` if it still exists
2. stop the active subprocess if one exists
3. finalize any reserved current iteration as `interrupted` if it has not already reached a local terminal state
4. mark the run `escalated` if it was still `running`
5. complete terminalization using the same final `run.json`, `run_terminal`, and `active.json` rules defined elsewhere in this document

`escalated` is not a failure.

Additional rules:

* If a stop request reaches a live controller, the controller SHOULD forward a termination signal to the active child process first and MAY escalate to a stronger signal after a short grace period.
* `reflow stop <run_id>` is idempotent. If the run is already terminal, it MUST leave the terminal state unchanged.
* If `run.json` says `running` but `active.json` is missing or stale, `reflow stop <run_id>` MUST reconcile the state by marking the run `escalated` and ensuring `active.json` is absent.

## 22. CLI contract

Required commands:

```text
reflow run <workflow> [--workspace <path>]
reflow resume <run_id> [--workspace <path>]
reflow status <run_id> [--workspace <path>]
reflow stop <run_id> [--workspace <path>]
reflow list [--workspace <path>]
```

Optional future commands:

* `tail`
* `inspect`

### 22.1 Workspace resolution and identifiers

Rules:

* `--workspace <path>` defaults to the current working directory.
* `<workflow>` is the workflow directory name under `.reflow/workflows/`.
* `<run_id>` is the run directory name under `.reflow/runs/`.

### 22.2 Command semantics

Rules:

* `run` validates config and workflow state, acquires the workspace lock under Section 6, creates a new run, starts the controller loop, and MUST print the `run_id` somewhere in stdout.
* `resume` validates that the named run exists, is still `running`, and can reacquire the workspace lock under Section 6 before restarting the controller loop from `current_step`. It MUST print the `run_id` somewhere in stdout.
* `status` reads persisted state only and MUST report at least `run_id`, `workflow`, `status`, `current_step`, `step_loops`, and failure fields when present.
* `stop` MUST NOT invoke providers or shell steps directly. It only requests or reconciles escalation for an existing run.
* `list` reads persisted state only and MUST enumerate known runs with at least `run_id`, `workflow`, `status`, and `updated_at`.
* Output formatting for these commands MAY be human-readable text; v1 does not define a machine-stable JSON CLI output mode.

## 23. Exit codes

Recommended exit codes:

| Code | Meaning               |
| ---- | --------------------- |
| 0    | completed             |
| 20   | provider unavailable  |
| 21   | step failed           |
| 22   | max loops exceeded    |
| 24   | escalated             |
| 25   | internal/config error |

Stable differentiation matters more than exact numbers.

Additional rules:

* `run` and `resume` MUST return the terminal run exit code when they drive a run to completion, failure, or escalation.
* Preflight or command-state errors that occur before a controller takes ownership of a run or workspace, such as invalid workflow names, malformed config, missing run directories, unreadable `run.json`, non-`running` run status, or non-stale workspace-lock conflicts, MUST return `25`.
* On those refusal paths, Reflow MUST NOT create or modify `active.json`, and MUST leave any existing `run.json` and `history.jsonl` files unchanged.
* `status`, `list`, and `stop` MUST return `0` on success and `25` on command/state errors.

## 24. Informative implementation sketch

This section is informative only. It suggests one small module split that would satisfy the normative contracts above, but other internal layouts are equally valid.

```text
reflow/
  __main__.py
  cli.py
  config.py
  workflow.py
  providers.py
  storage.py
  loop.py
```

### `cli.py`

Command parsing and top-level exit-code mapping.

### `config.py`

Load and validate `.reflow/config.yaml`.

### `workflow.py`

Load and validate workflow files.

### `providers.py`

Thin Codex and Claude wrappers.

### `storage.py`

Run directories, run control files, history writing, iteration file writes.

### `loop.py`

The core runtime loop.

## 25. Validation and testing

### 25.1 Unit tests

Minimum unit tests:

* config validation
* workflow validation
* route-tag parsing
* required-file checks
* loop counting
* run control read/write
* provider wrapper command construction
* exit-code mapping

### 25.2 Integration tests

Minimum integration tests:

* happy-path multi-step workflow
* missing route tag
* invalid route tag
* `retry` loop behavior
* required-file missing behavior
* shell success / failure routing
* provider unavailable
* max-loops failure
* resume starts a fresh iteration of the current step
* operator stop escalates run

### 25.3 Provider-contract regression tests

Include fixture-based tests for:

* Codex final-message capture
* Claude plain-text capture

These should use saved fixture outputs, not live provider calls.

## 26. Informative delivery sequence

This section is informative only. It suggests one order for building the system, but it does not constrain a conforming implementation.

### Phase 1

* `workflow.py`
* `config.py`
* `storage.py`

### Phase 2

* `providers.py`

### Phase 3

* `loop.py`

### Phase 4

* `cli.py`
* `__main__.py`

### Phase 5

* first real workflow
* end-to-end tests with real providers
