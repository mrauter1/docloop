# Review of `docloop.py`

## Verdict

`docloop.py` has a good minimal shape, but it is not currently error-free in its core behavior. The main loop does not reliably work against the installed Codex CLI, and several control-flow and git-state edge cases break the guarantees the script claims to provide.

The design is strong in one respect: it keeps orchestration state on disk and constrains git tracking to the target document plus `.docloop/`. That is the right minimal boundary. The implementation around the Codex invocation, iteration semantics, and commit guarantees is not yet robust enough to trust for unattended use.

## What The Script Gets Right

- The architecture is genuinely minimal: one target document, one `.docloop/` state directory, and git as the checkpoint mechanism.
- `init_workspace()` creates a usable workspace with clear defaults and avoids broad `git add .` behavior.
- The control-tag approach is simple and easy to reason about.
- Stall detection is directionally useful, even though one branch of it currently misfires.

## Findings

### 1. Critical: the shipped Codex invocation is incompatible with the installed CLI

Code reference: `docloop.py:163-171`

The script runs:

```text
codex exec --ephemeral --sandbox workspace-write --ask-for-approval never --model ...
```

On this machine, `codex exec --help` shows `--full-auto` and `--dangerously-bypass-approvals-and-sandbox`, but not `--ask-for-approval`. A real run of `docloop.py` failed immediately with:

```text
error: unexpected argument '--ask-for-approval' found
```

Impact:

- The current implementation cannot execute the core loop successfully against the installed `codex-cli 0.114.0`.
- This is a release-blocking bug because it breaks the only external action the tool performs.

Recommendation:

- Replace the hardcoded approval flag with the currently supported equivalent, or probe CLI capabilities first and select the compatible invocation.
- Treat an unsupported CLI contract as a hard startup failure, not an iteration event.

### 2. Critical: Codex process failures are misclassified as agent stalls

Code reference: `docloop.py:181-223`

If the Codex subprocess exits non-zero, the script prints a warning but then continues into the normal "did files change?" stall logic. In the real run above, an argument-parsing failure from the CLI was treated as:

```text
[!] Agent returned non-zero exit code (2).
[-] No file changes detected. Stall counter: 1/2
```

Impact:

- Infrastructure failures, auth failures, API transport failures, and invalid CLI arguments are all misreported as agent inactivity.
- The script can waste iterations and inject misleading unblock warnings into `.docloop/progress.txt` when the real problem is external.

Recommendation:

- Split subprocess outcomes into distinct classes:
  - invocation/configuration failure
  - transport/auth/runtime failure
  - successful run with no mutation
- Do not feed non-zero Codex exits into stall detection.

### 3. Critical: existing git repositories without a valid identity silently lose all checkpoint commits

Code reference: `docloop.py:104-113`, `docloop.py:153-154`, `docloop.py:199-200`, `docloop.py:207-208`, `docloop.py:227-228`

The script only configures `user.name` and `user.email` when `.git/` does not exist. In an existing repository with no usable identity, all `git commit` calls fail silently because every commit uses `allow_fail=True`.

Observed behavior in `/tmp/docloop-existingrepo.Ui1ezC`:

- `docloop.py` printed a success message after a stub completion run.
- `git log` remained empty.
- `git status --short` showed all `.docloop/*` files and `SAD.md` still staged.

Impact:

- The script claims to use git as the checkpointing backbone, but that guarantee disappears in a common local setup.
- Operators can believe they have snapshots and completion history when they do not.

Recommendation:

- Validate commit capability before the loop starts, even in pre-existing repositories.
- If commit capability is missing, fail fast with a clear error instead of continuing.
- If silent no-op commits are desired for unchanged trees, distinguish that case from identity/configuration failures.

### 4. High: a question on the last allowed iteration always ends as a failure

Code reference: `docloop.py:189-203`, `docloop.py:232-233`

When the agent emits `<question>...</question>`, the script records the answer, commits it, resets the stall counter, and `continue`s. If this happens on the final iteration, the loop ends and the script immediately prints:

```text
[FAILED] Reached max iterations ...
```

Observed behavior in `/tmp/docloop-stubtest-question.AHxpc4` with `--max-iterations 1`:

- The human clarification was appended to `.docloop/context.md`.
- The clarification commit was created.
- The process still exited with code `1`.

Impact:

- A successful clarification handoff is reported as total failure.
- A question currently consumes an iteration budget slot even though it is an external dependency handoff, not model progress.

Recommendation:

- Do not count clarification turns against the iteration cap, or explicitly extend the loop budget after a question.
- At minimum, if a question happens on the last iteration, rerun once more before declaring failure.

### 5. High: completion is trusted without verifying the criteria file

Code reference: `docloop.py:205-209`

The script treats `<promise>COMPLETE</promise>` as authoritative and prints:

```text
[SUCCESS] ... Verification successful.
```

But it never checks whether `.docloop/criteria.md` actually has every box marked complete.

Impact:

- The success message overstates what was proven.
- A misaligned or hallucinated final response can terminate the loop even if the criteria file still contradicts the claim.

Recommendation:

- On completion, read `.docloop/criteria.md` and verify that every checklist item is marked `- [x]`.
- If the checklist is not fully satisfied, reject the completion signal and continue or fail explicitly.

### 6. Medium: the stall warning can be injected too late to have any effect

Code reference: `docloop.py:218-223`, `docloop.py:232-233`

The stall warning is appended after two consecutive no-change iterations. If that happens on the last iteration, the script exits immediately and the warning never reaches another Codex pass.

Observed behavior in `/tmp/docloop-stubtest-stall.NFdNMA` with `--max-iterations 2`:

- The warning was appended to `.docloop/progress.txt` on iteration 2.
- The script then immediately exited with failure.

Impact:

- The unblock mechanism does not reliably influence the next run.

Recommendation:

- Only inject the warning if another iteration remains, or automatically grant one additional retry after injecting it.

### 7. Medium: the "question means no edits" contract is not enforced

Code reference: `docloop.py:188-203`

The prompt says that when the agent emits `<question>...</question>`, it must not edit files. The script does not verify that. If Codex edits the target document and also emits a question, those edits remain in the workspace and can be committed after the human answer path.

Impact:

- The handoff contract is weaker than it appears.
- Partial or unsafe edits can leak across a clarification boundary.

Recommendation:

- On the question path, assert that the tracked files are unchanged before accepting the question.
- If changes exist, either reject the question or revert only the tracked working files for that iteration.

### 8. Medium: runtime compatibility is not checked until after workspace initialization and git side effects

Code reference: `docloop.py:65-75`, `docloop.py:141-177`

`check_dependencies()` only verifies that `codex` exists in `PATH`. It does not verify:

- CLI flag compatibility
- repository requirements
- auth/network reachability

Impact:

- The script can create files, initialize git, and make baseline commits before discovering that the Codex CLI cannot actually execute.

Recommendation:

- Add a startup probe for the Codex command contract you depend on.
- Fail before mutating the workspace if the command shape is unsupported.

## Runtime Testing

### Environment

- Python: `python3`
- Git: present
- Codex CLI: `codex-cli 0.114.0`

### Test 1: real `docloop.py` run against the installed Codex CLI

Command:

```bash
python3 /home/marcelo/code/docloop/docloop.py --max-iterations 1 --type SAD
```

Working directory:

```text
/tmp/docloop-smoketest.2Cyrks
```

Observed result:

- Workspace initialization succeeded.
- Baseline git commit succeeded in the fresh repo.
- Iteration 1 failed before any model work because `codex exec` rejected `--ask-for-approval`.
- The script then classified the failure as a stall and exited with code `1`.

Artifacts after the run:

- Files created: `.docloop/*`, `SAD.md`
- Git history: baseline commit only
- `.docloop/progress.txt`: unchanged aside from its initial template

Conclusion:

- Current real-world integration is broken before the loop can do useful work.

### Test 2: manual Codex CLI probe with supported flags

Command:

```bash
printf 'Reply with exactly <promise>COMPLETE</promise> and nothing else.' | codex exec --ephemeral --full-auto -
```

Observed result:

- Inside the sandbox, Codex transport failed due network restrictions.
- Re-running outside the sandbox succeeded and returned `<promise>COMPLETE</promise>`.

Conclusion:

- The local environment is capable of running Codex when invoked compatibly and with network access.
- This strengthens the finding that the current `docloop.py` failure is due to the invocation contract, not just a missing installation.

### Test 3: completion path with a local Codex stub

Working directory:

```text
/tmp/docloop-stubtest-complete.5Y8Pzp
```

Observed result:

- Exit code `0`
- Git history:
  - `docloop: baseline`
  - `docloop: SUCCESSFUL COMPLETION (SAD)`
- The target doc and `.docloop/criteria.md` were updated as expected.

Conclusion:

- The happy-path completion branch works structurally when the subprocess contract is satisfied.

### Test 4: question path with a local Codex stub

Working directory:

```text
/tmp/docloop-stubtest-question.AHxpc4
```

Observed result:

- Human clarification was appended to `.docloop/context.md`.
- Git history contains:
  - `docloop: baseline`
  - `docloop: human answered question in iteration 1`
- Process exit code was still `1` because the loop exhausted immediately afterward.

Conclusion:

- The clarification append/commit path works.
- The iteration accounting around questions is incorrect.

### Test 5: stall path with a local Codex stub

Working directory:

```text
/tmp/docloop-stubtest-stall.NFdNMA
```

Observed result:

- After two no-change iterations, the unblock warning was appended to `.docloop/progress.txt`.
- The script exited with code `1`.
- Git history contained only the baseline commit because no tracked changes existed until the warning append on the final iteration, and no follow-up iteration occurred.

Conclusion:

- Stall detection and warning injection execute, but the final-iteration timing makes the mechanism weaker than intended.

### Test 6: existing repository with no valid git identity

Working directory:

```text
/tmp/docloop-existingrepo.Ui1ezC
```

Observed result:

- The process printed a success message on the completion path.
- `git log` remained empty.
- `git status --short` showed tracked files still staged.

Conclusion:

- The script does not currently guarantee git-backed checkpointing in existing repositories.

## Overall Assessment

The minimal architecture is worth keeping. The implementation is not yet reliable enough for the stated goal that the core loop be error-free and powerful in practice. The single biggest blocker is the Codex CLI contract mismatch. After that, the next most important fixes are:

1. Separate subprocess failure handling from stall handling.
2. Enforce commit capability before entering the loop.
3. Fix the iteration semantics around clarification questions.
4. Verify completion against `.docloop/criteria.md` instead of trusting the tag alone.

If those four issues are addressed, the current design can remain minimal while becoming materially more trustworthy.
