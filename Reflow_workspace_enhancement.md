PRD: Reflow v1.A runtime-owned .reflow workspace, workflow task→input rename, and controller cleanup
Status

Proposed

Objective

Update Reflow v1.A to make the runtime simpler and more reliable by:

treating the full .reflow directory as runtime-owned workspace

excluding .reflow from snapshot-based policy checks

renaming the workflow YAML field task to input

removing controller logic that is no longer needed once .reflow is excluded

centralizing command output persistence

preserving existing stop behavior and existing non-runtime policy behavior

Product decisions
1. .reflow is runtime-owned

.reflow is not part of the workflow-controlled workspace. It is the runtime workspace.

Anything under .reflow is internal runtime state and must be ignored by snapshot-based policy enforcement.

2. Workflow YAML uses input, not task

The workflow YAML field currently named task is renamed to input.

input is the only supported name going forward.

To keep the change simple and explicit:

input must be accepted

task must be rejected with a clear error telling the user to rename it to input

No dual-field compatibility layer is required.

Background

In v1.A, policy evaluation compares a before and after workspace snapshot around each step execution.

Today, runtime-managed files under .reflow can appear in those snapshots, except for the current iteration directory. That creates policy noise and makes workflows sensitive to internal runtime bookkeeping.

Separately, the workflow YAML field name task should be renamed to input for clarity and consistency.

Goals

Ignore the full .reflow tree during workspace snapshotting.

Ensure runtime-created files under .reflow never affect write-policy evaluation.

Rename workflow YAML field task to input.

Reject task with a clear validation error.

Remove per-iteration snapshot-ignore plumbing that becomes unnecessary once .reflow is fully ignored.

Deduplicate controller output-file writes.

Preserve existing signal handling and non-.reflow policy behavior.

Non-goals

This PR does not:

change CLI commands or flags

change exit codes

change workflow transition semantics

change operator input behavior

change allow/forbid/required policy semantics outside .reflow

tighten or loosen escape-path semantics

add schema aliases or deprecation windows for task

Scope
In scope

reflow_runtime/policy.py

reflow_runtime/controller.py

reflow_runtime/loaders.py

reflow_runtime/models.py

any user-facing workflow-schema references or tests that still use task

Out of scope

reflow.py

reflow_runtime/__init__.py

reflow_runtime/providers.py

reflow_runtime/storage.py

reflow_runtime/protocol.py, unless it contains user-facing references to task

Requirements
Functional requirement 1: exclude .reflow from snapshots

snapshot_workspace() must exclude the entire top-level .reflow tree from traversal and from recorded snapshot entries.

As a result:

no .reflow path may appear in WorkspaceSnapshot.entries

no .reflow path may appear in changed_paths

no .reflow path may trigger allow_write or forbid_write violations

runtime-created mutable files anywhere under .reflow must be ignored automatically

Functional requirement 2: remove per-iteration ignore plumbing

Because the full .reflow tree is excluded, the controller must no longer construct or pass ignored paths for the current iteration directory.

This older mechanism becomes redundant and should be removed.

Functional requirement 3: preserve non-.reflow policy behavior

Outside .reflow, policy behavior must remain equivalent to v1.A.

That includes:

changed-path detection

allow_write

forbid_write

required_files

current escape-path behavior

Functional requirement 4: rename workflow YAML field task to input

Where the workflow schema currently defines a top-level task field, it must be renamed to input.

The runtime must treat input as the canonical field name.

The meaning, validation rules, and runtime behavior of the field must stay the same unless a separate product decision changes them. This PR changes the name only.

Functional requirement 5: reject task with a clear error

If a workflow YAML file contains task, loading must fail with a clear ConfigError that instructs the user to rename task to input.

Preferred error text:

workflow field 'task' has been renamed to 'input'

If both task and input are present, loading must also fail with the same rename guidance.

Functional requirement 6: centralize output persistence

In both _execute_agent_step() and _execute_shell_step():

write stdout.txt and stderr.txt exactly once immediately after invocation returns

for shell steps, write final.txt from shell stdout exactly once immediately after invocation returns

remove repeated output writes from later branches

This must not change success or failure semantics.

Functional requirement 7: preserve signal handling

Keep v1.A’s explicit stop-signal handling unchanged.

Do not remove:

_install_stop_signal_handlers()

the SIGINT/SIGTERM to KeyboardInterrupt mapping

_run_with_stop_guard() behavior

Design
Design decision 1: hardcode .reflow exclusion in policy.py

The simplest correct design is to make .reflow exclusion a built-in rule of snapshot_workspace().

No dynamic ignored-path argument is needed for this purpose.

Design decision 2: preserve path correctness for top-level dotpaths

Do not use string trimming like .lstrip("./") to derive relative paths.

Relative paths must preserve leading dots correctly.

Examples:

.env must remain .env

.gitignore must remain .gitignore

.github/workflows/ci.yml must remain .github/workflows/ci.yml

Design decision 3: keep schema rename strict

To keep the change simple:

support input

reject task

Do not support both names simultaneously.

Design decision 4: do not change escape-path policy in this PR

Keep current escape-path semantics as they are in v1.A.

This PR is about runtime workspace exclusion, schema rename, and controller cleanup only.

Detailed implementation requirements
File: reflow_runtime/policy.py
Change 1: exclude runtime-owned paths

Update snapshot_workspace() so that it excludes the full .reflow tree.

Add a small helper such as:

_is_runtime_owned(path: Path) -> bool

It must return True only when the first path component is exactly .reflow.

Change 2: simplify function signature

If ignored_paths exists only to support selective .reflow exclusions, remove it.

Preferred signature:

def snapshot_workspace(workspace: Path) -> WorkspaceSnapshot:
Change 3: preserve safe relative-path construction

Use explicit root-path handling so top-level dotpaths remain exact.

Do not use broad string stripping on relative paths.

Change 4: leave evaluate_policy() behavior unchanged outside .reflow

Other than the absence of .reflow paths in snapshots, evaluate_policy() must keep v1.A behavior.

File: reflow_runtime/controller.py
Change 1: remove per-iteration snapshot-ignore logic

Remove logic that computes and passes ignored paths for the current iteration directory.

Remove helper functions that exist only for that purpose, such as _relative_path(...), if no longer used.

Change 2: centralize output persistence in _execute_agent_step()

Immediately after invoke_provider(...) returns:

write ctx.stdout_path

write ctx.stderr_path

Remove repeated writes from later branches.

Change 3: centralize output persistence in _execute_shell_step()

Immediately after invoke_shell(...) returns:

write ctx.stdout_path

write ctx.stderr_path

write ctx.final_path from invocation.stdout

Remove repeated writes from later branches.

Change 4: preserve stop behavior

Do not change signal handling, stop handling, or controller cleanup flow.

File: reflow_runtime/loaders.py
Change 1: rename schema field

Update workflow schema handling so the workflow field is named input, not task.

This includes:

allowed-field validation

parsing logic

error handling

any schema-specific validation tied to that field

Change 2: reject old field name

If task is present, raise a ConfigError with explicit rename guidance.

Change 3: preserve semantics

The runtime meaning of the field must remain unchanged. Only the key name changes.

File: reflow_runtime/models.py
Change 1: rename internal model field if present

If any workflow model currently stores this value under task, rename that attribute to input.

Update all call sites accordingly.

If no internal model field exists yet, no new abstraction is required beyond what the loader needs.

User-facing text and examples

All workflow examples, fixtures, tests, and documentation in scope for this PR must use input, not task.

Acceptance criteria

The change is complete only if all of the following are true.

Runtime workspace behavior

No .reflow path appears in WorkspaceSnapshot.entries.

No .reflow path appears in changed_paths.

Runtime-managed files under .reflow never trigger write-policy failures.

New runtime-created files under .reflow are ignored automatically without workflow changes.

Workflow schema behavior

A workflow using input loads successfully.

A workflow using task fails with a clear rename error.

A workflow using both task and input fails with a clear rename error.

The semantics of the renamed field remain otherwise unchanged.

Non-runtime behavior

Writes outside .reflow continue to be detected exactly as before.

allow_write, forbid_write, and required_files behavior outside .reflow is unchanged.

Escape-path behavior remains unchanged from v1.A.

Controller behavior

stdout.txt and stderr.txt are written exactly once per invocation.

Shell final.txt continues to contain shell stdout exactly as before.

Stop behavior remains unchanged from v1.A.

Test requirements
Test 1: .reflow is fully ignored

Execute a step that causes runtime writes under .reflow.

Expected result:

no .reflow path appears in changed_paths

policy outcome is unaffected by those writes

Test 2: non-.reflow violations still fail

Execute a step that writes outside its allowed non-runtime path.

Expected result:

policy still fails exactly as in v1.A

Test 3: top-level dotpaths remain correct

Exercise snapshotting on paths such as:

.env

.gitignore

.github/workflows/ci.yml

Expected result:

relative paths are preserved exactly

no leading-dot corruption occurs

Test 4: workflow with input loads

Create a workflow YAML that uses input.

Expected result:

loader accepts it

runtime behavior matches the old task semantics

Test 5: workflow with task fails clearly

Create a workflow YAML that uses task.

Expected result:

loader raises ConfigError

error clearly states that task was renamed to input

Test 6: workflow with both fields fails clearly

Create a workflow YAML that contains both task and input.

Expected result:

loader raises ConfigError

error clearly instructs the user to use input

Test 7: output files remain correct

For both agent and shell steps, verify output persistence for:

provider unavailable

timeout

non-zero exit

malformed control output

success

Test 8: signal handling unchanged

Interrupt a running step through the existing stop flow and by direct termination.

Expected result:

graceful stop behavior remains unchanged from v1.A

Risks
Risk 1: overbroad runtime-owned matching

If the runtime-owned helper matches more than the top-level .reflow tree, real workspace paths may be hidden.

Mitigation: match only when the first path component is exactly .reflow.

Risk 2: partial schema rename

If only loader validation is changed but downstream references still expect task, runtime errors may follow.

Mitigation: rename all in-scope references consistently and add schema tests.

Risk 3: hidden dotpath corruption

Unsafe relative-path handling can corrupt top-level hidden-file paths.

Mitigation: use explicit path construction, not broad string trimming.

Rollout and compatibility

This PR intentionally changes workflow schema behavior:

input is supported

task is rejected

This is a deliberate breaking rename with a clear validation error.

No CLI or exit-code changes are allowed.

Definition of done

This PR is done when:

.reflow is fully excluded from snapshot-based policy checks

per-iteration snapshot-ignore plumbing is removed

workflow YAML uses input instead of task

task is rejected with clear rename guidance

output persistence is centralized

signal handling remains unchanged

all acceptance criteria and tests pass
