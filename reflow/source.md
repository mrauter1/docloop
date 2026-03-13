# Reflow v1 — Architectural Specification

## 1. Purpose and normative status

This document is the normative architecture for Reflow v1.

It defines the minimum structure required to implement Reflow as a thin workflow loop runner around provider CLIs. It covers repository layout, workflow and config contracts, provider invocation, storage, routing, resume, terminal behavior, testing, and implementation order.

Unless explicitly marked as future work, every statement in this document is normative.

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
            prompt.txt
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

## 6. One active run per workspace

Reflow v1 supports **one active run per workspace**.

Rules:

* `active.json` exists only while a run is `running`.
* `reflow run <workflow>` MUST fail if `active.json` already points to a running run.
* Historical completed, failed, or escalated runs remain in `.reflow/runs/`.

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

### 7.2 Step kinds

Reflow v1 supports exactly two step kinds:

* `agent`
* `shell`

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
* `provider` names a configured provider profile from `.reflow/config.yaml`.
* `max_loops` is a positive integer.
* `routes` is a non-empty list of allowed route values.
* `required_files`, if present, is a list of repo-relative file paths.

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

* `cmd` is a shell command string.
* `on_success` and `on_failure` are transition targets.
* `max_loops` is a positive integer.

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

* `name`, `entry`, or `steps` is missing
* `entry` is not a declared step
* a step name is duplicated
* a step kind is not `agent` or `shell`
* an `agent` step is missing required fields
* a `shell` step is missing required fields
* `max_loops < 1`
* `prompt` file does not exist
* `provider` does not exist in config
* any route target is not:

  * a declared step
  * `done`
  * `retry` for agent steps
  * `escalate`
* any `required_files` path is absolute
* any `required_files` path contains parent traversal (`..`)

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

## 10. Minimal run state

Each run has one control file:

```text
.reflow/runs/<run_id>/run.json
```

### 10.1 Required fields

```json
{
  "run_id": "run_20260311T120000_review_fix_verify",
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

Optional terminal fields:

* `failure_type`
* `failure_reason`

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

## 11. History and per-iteration records

Each run also stores:

```text
.reflow/runs/<run_id>/history.jsonl
```

This is an append-only event log for operator visibility, not provider memory.

### 11.1 Minimum history record

```json
{
  "ts": "2026-03-11T12:15:21Z",
  "type": "iteration",
  "step": "implement",
  "loop": 3,
  "provider": "codex",
  "route": "verify",
  "required_files_ok": true,
  "iteration_dir": ".reflow/runs/run_.../steps/implement/003"
}
```

### 11.2 Iteration directory

Each iteration directory contains:

* `prompt.txt`
* `final.txt`
* `stdout.txt`
* `stderr.txt`
* `meta.json`

### 11.3 `meta.json` minimum contract

```json
{
  "step": "implement",
  "loop": 3,
  "kind": "agent",
  "provider": "codex",
  "started_at": "2026-03-11T12:14:10Z",
  "ended_at": "2026-03-11T12:15:21Z",
  "exit_code": 0,
  "route": "verify",
  "required_files_missing": [],
  "status": "ok"
}
```

`meta.json` SHOULD include:

* provider command actually run
* model if set
* elapsed seconds
* failure reason if any

## 12. Step loop semantics

`max_loops` is the total number of times a step may run within a single run.

Important rule:

* loop counts do **not** reset when a step is revisited later in the workflow

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
* that iteration counts as `step_failed`
* the same step is rerun if loops remain
* otherwise the run fails with `max_loops_exceeded`

## 16. Provider wrappers

Reflow has thin wrappers for Codex and Claude.

### 16.1 Codex wrapper

For `codex` providers, Reflow MUST invoke `codex exec` in one-shot mode and MUST set the working directory with `--cd`. It SHOULD capture the provider’s final message using `--output-last-message`. Reflow MUST NOT require `codex exec resume` or `--ephemeral` for correctness.

Recommended invocation shape:

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

`on_success` and `on_failure` may each be:

* another step name
* `done`
* `escalate`

A shell step does not use route tags.

## 18. Failure model

Keep the failure taxonomy minimal.

Allowed terminal `failure_type` values are:

* `provider_unavailable`
* `step_failed`
* `max_loops_exceeded`
* `internal_error`

### 18.1 Classification rules

`provider_unavailable`

* executable missing
* provider cannot initialize or authenticate before doing work

`step_failed`

* provider exits nonzero after startup
* provider times out
* missing route tag
* invalid route tag
* required files missing
* shell command failure

`max_loops_exceeded`

* current step has reached `max_loops` and still has not produced an acceptable transition

`internal_error`

* config loading failure
* workflow validation failure
* storage failure
* unexpected runtime bug

Free-form `failure_reason` text carries the details.

## 19. Runtime algorithm

This is the authoritative loop algorithm.

### 19.1 Agent step

For an `agent` step:

1. load the step definition
2. check whether `step_loops[step] + 1 > max_loops`
3. if exceeded, fail the run with `max_loops_exceeded`
4. increment the step loop count
5. create a new iteration directory
6. write `prompt.txt`
7. invoke the provider
8. capture `stdout.txt`, `stderr.txt`, and `final.txt`
9. parse the last valid route tag from `final.txt`
10. if route missing or invalid:

* rerun same step if loops remain
* else fail with `max_loops_exceeded`

11. if route is `retry`:

* rerun same step if loops remain
* else fail with `max_loops_exceeded`

12. if route is `escalate`:

* mark run `escalated`
* stop

13. if route is a next step or `done`:

* check required files
* if missing:

  * rerun same step if loops remain
  * else fail with `max_loops_exceeded`

14. if route is `done` and files are okay:

* mark run `completed`
* stop

15. if route is another step and files are okay:

* set `current_step` to that step
* continue loop

### 19.2 Shell step

For a `shell` step:

1. load the step definition
2. check whether `step_loops[step] + 1 > max_loops`
3. if exceeded, fail the run with `max_loops_exceeded`
4. increment the step loop count
5. create a new iteration directory
6. invoke the shell command
7. capture logs
8. map exit code:

   * `0` -> `on_success`
   * nonzero -> `on_failure`
9. apply the target:

   * `done` -> completed
   * `escalate` -> escalated
   * step name -> move to that step

## 20. Resume model

Resume is deliberately simple.

### 20.1 Command

```text
reflow resume <run_id> [--workspace <path>]
```

### 20.2 Semantics

On resume, Reflow:

1. loads `run.json`
2. verifies status is `running`
3. logs that resume is starting a fresh iteration of `current_step`
4. starts a new iteration of `current_step`
5. continues normally

### 20.3 Important rule

Reflow v1 does **not** resume inside a partially completed provider invocation.

If the previous iteration was interrupted mid-run:

* Reflow does not try to recover inside that iteration
* it simply starts a fresh iteration of the current step

This is intentional.

## 21. Operator stop

`reflow stop <run_id>` or Ctrl+C during a running loop MUST:

1. stop the active subprocess if one exists
2. mark the run `escalated`
3. write the final `run.json`
4. remove `active.json`

`escalated` is not a failure.

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

## 24. Minimal module layout

Keep the implementation small.

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

## 26. Implementation sequence

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

## 27. Explicit deletions from the heavier design

Reflow v1 explicitly does **not** include:

* a canonical message ledger as runtime truth
* a separate route-evaluator pass
* success/failure condition DSLs
* nested workflows
* child-run linkage
* attempt checkpoint state machines
* broad failure enums
* a mandatory skill abstraction

Those are intentionally left out to preserve KISS, DRY, and YAGNI.

## 28. Final architectural position

Reflow v1 is a thin workflow loop runner.

Its architecture is:

* workflow file
* small config file
* one-shot provider wrappers
* simple route-tag parser
* file-existence checks
* minimal run control
* per-iteration logs

The provider does the work.
The repository holds the memory.
Reflow owns only the loop.
