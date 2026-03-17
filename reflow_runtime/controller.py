from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import sys
import time
from pathlib import Path

from .loaders import collect_workflow_validation_errors, load_config, load_workflow, resolve_provider_for_step
from .models import (
    AgentStep,
    AwaitingInputError,
    BlockedRunError,
    EXIT_CODE_AWAITING_INPUT,
    EXIT_CODE_BLOCKED,
    EXIT_CODE_INTERNAL,
    EXIT_CODE_MAX_CYCLES,
    EXIT_CODE_MAX_LOOPS,
    EXIT_CODE_PROVIDER_UNAVAILABLE,
    EXIT_CODE_STEP_FAILED,
    EXIT_CODE_STOPPED,
    FAILURE_INTERNAL,
    FAILURE_MAX_CYCLES,
    FAILURE_MAX_LOOPS,
    FAILURE_PROVIDER_UNAVAILABLE,
    FAILURE_STEP_FAILED,
    STATUS_AWAITING_INPUT,
    STATUS_BLOCKED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_STOPPED,
    StepFailedError,
    TERMINAL_STATUSES,
)
from .policy import evaluate_policy, snapshot_workspace
from .protocol import malformed_control_warning, parse_agent_outcome, parse_full_auto_answers, render_agent_request
from .providers import build_shell_argv, invoke_provider, invoke_shell
from .scaffold import write_scaffold
from .storage import RunStore, append_operator_inputs, is_pid_alive


def run_new_workflow(workspace: Path, workflow_name: str, full_auto: bool, task: str | None = None) -> int:
    config = load_config(workspace)
    workflow = load_workflow(workspace, workflow_name, config)
    task = _normalize_task_for_workflow(workflow.name, workflow.input_mode, task)
    store = RunStore(workspace)
    _refuse_if_active_conflict(store)
    run = store.create_run(workflow.name, list(workflow.steps), workflow.entry, task=task)
    store.write_active(run, os.getpid())
    store.append_history(run.run_id, "run_started", workflow=workflow.name, entry_step=workflow.entry, task=task)
    return _run_with_stop_guard(
        store,
        run,
        lambda: _drive_run(store, config, workflow, run, full_auto=full_auto),
    )


def resume_run(workspace: Path, run_id: str, full_auto: bool) -> int:
    config = load_config(workspace)
    store = RunStore(workspace)
    run = store.load_run(run_id)
    if run.status != STATUS_RUNNING:
        raise ValueError("resume requires a running run.")
    workflow = load_workflow(workspace, run.workflow, config)
    _refuse_if_active_conflict(store, run_id=run_id)
    store.write_active(run, os.getpid())
    return _run_with_stop_guard(
        store,
        run,
        lambda: _resume_active_run(store, config, workflow, run, full_auto=full_auto),
    )


def reply_to_run(workspace: Path, run_id: str, full_auto: bool) -> int:
    config = load_config(workspace)
    store = RunStore(workspace)
    run = store.load_run(run_id)
    if run.status != STATUS_AWAITING_INPUT or run.pending_input is None:
        raise ValueError("reply requires a run with pending_input.")
    workflow = load_workflow(workspace, run.workflow, config)
    _refuse_if_active_conflict(store, run_id=run_id)
    store.write_active(run, os.getpid())
    return _run_with_stop_guard(
        store,
        run,
        lambda: _reply_active_run(store, config, workflow, run, full_auto=full_auto),
    )


def stop_run(workspace: Path, run_id: str) -> int:
    store = RunStore(workspace)
    run = store.load_run(run_id)
    active = store.active_lock()
    if active and active.get("run_id") == run_id:
        _signal_active_processes(active)
        time.sleep(0.1)
    _terminalize_stopped_run(store, run)
    return 0


def status_run(workspace: Path, run_id: str, verbose: bool = False) -> int:
    store = RunStore(workspace)
    run = store.load_run(run_id)
    config = load_config(workspace)
    workflow = load_workflow(workspace, run.workflow, config)
    print(f"run_id: {run.run_id}")
    print(f"workflow: {run.workflow}")
    if run.task is not None:
        print(f"task: {run.task}")
    print(f"status: {run.status}")
    print(f"current_step: {run.current_step}")
    print(f"cycle_count: {run.cycle_count}")
    print(f"started_at: {run.started_at}")
    print(f"updated_at: {run.updated_at}")
    if run.status == STATUS_AWAITING_INPUT and run.pending_input:
        print(f"pending_step: {run.pending_input.step}")
        print(f"pending_loop: {run.pending_input.loop}")
        print(f"pending_question_count: {len(run.pending_input.questions)}")
        print(f"pending_auto_round: {run.pending_input.auto_round}")
    if run.status == STATUS_FAILED:
        print(f"failure_type: {run.failure_type}")
        print(f"failure_reason: {run.failure_reason}")
    if verbose:
        step = workflow.steps[run.current_step]
        if isinstance(step, AgentStep):
            context_present = _load_latest_context_present(store, run)
            for entry in step.context:
                present = context_present.get(entry.path)
                if present is None:
                    present = _context_path_exists(workspace, workflow, entry.path)
                suffix = entry.path if present else f"{entry.path} (not present)"
                print(f"context: {suffix} - {entry.as_description}")
            for entry in step.produces:
                print(f"expected_output: {entry.path} - {entry.as_description}")
    return 0


def list_runs(workspace: Path) -> int:
    store = RunStore(workspace)
    runs: list[tuple[str, str, str, str]] = []
    if store.runs_dir.exists():
        for child in store.runs_dir.iterdir():
            if not child.is_dir():
                continue
            run_path = child / "run.json"
            if not run_path.is_file():
                continue
            run = store.load_run(child.name)
            runs.append((run.started_at, run.run_id, run.workflow, run.status, run.updated_at))
    for _started_at, run_id, workflow, status, updated_at in sorted(runs, reverse=True):
        print(f"{run_id}\t{workflow}\t{status}\t{updated_at}")
    return 0


def validate_workflow(workspace: Path, workflow_name: str) -> int:
    config = load_config(workspace)
    print("Config: ok")
    errors = collect_workflow_validation_errors(workspace, workflow_name, config)
    if errors:
        print(f"Workflow '{workflow_name}': FAILED")
        for error in errors:
            print(f"  - {error}")
        return 25

    workflow = load_workflow(workspace, workflow_name, config)
    providers = sorted(
        {
            resolve_provider_for_step(config, workflow, step).name
            for step in workflow.steps.values()
            if isinstance(step, AgentStep)
        }
    )
    providers_display = ", ".join(providers)
    print(f"Workflow '{workflow.name}': ok")
    print(f"  Steps: {', '.join(workflow.steps)}")
    print(f"  Entry: {workflow.entry}")
    print(f"  Providers: {providers_display}")
    return 0


def init_workflow(
    workspace: Path,
    workflow_name: str,
    *,
    template_name: str,
    provider_kind: str,
    target: str,
) -> int:
    result = write_scaffold(
        workspace,
        workflow_name,
        template_name=template_name,
        provider_kind=provider_kind,
        target=target,
    )
    config = load_config(workspace)
    errors = collect_workflow_validation_errors(workspace, workflow_name, config)
    if errors:
        raise ValueError(f"generated workflow {workflow_name!r} is invalid: {'; '.join(errors)}")
    print(f"Workflow '{workflow_name}' initialized.")
    print("")
    for path in result.created:
        print(f"  Created {path}")
    if result.skipped:
        for path in result.skipped:
            print(f"  Skipped {path} (already exists)")
    print("")
    print("Next steps:")
    for index, step in enumerate(result.next_steps, start=1):
        print(f"  {index}. {step}")
    return 0


def reserve_iteration(store: RunStore, run, step_name: str):
    step_kind = "agent"
    return store.reserve_iteration(run, step_name, step_kind)


def reconcile_reserved_iteration(store: RunStore, run) -> None:
    store.reconcile_reserved_iteration(run)


def _drive_run(store: RunStore, config, workflow, run, *, full_auto: bool) -> int:
    protocol_warning: str | None = None
    while True:
        if run.status in TERMINAL_STATUSES:
            return _exit_code_for_run(run)
        if run.status == STATUS_AWAITING_INPUT:
            store.clear_active(run.run_id)
            return EXIT_CODE_AWAITING_INPUT

        step = workflow.steps[run.current_step]
        try:
            if isinstance(step, AgentStep):
                protocol_warning = _execute_agent_step(
                    store,
                    config,
                    workflow,
                    run,
                    step,
                    full_auto=full_auto,
                    protocol_warning=protocol_warning,
                )
            else:
                protocol_warning = _execute_shell_step(store, workflow, run, step)
        except KeyboardInterrupt:
            _terminalize_stopped_run(store, run)
            return EXIT_CODE_STOPPED
        except FileNotFoundError as exc:
            _fail_run(store, run, FAILURE_INTERNAL, str(exc))
        except Exception as exc:
            _fail_run(store, run, FAILURE_INTERNAL, str(exc))


def _resume_active_run(store, config, workflow, run, *, full_auto: bool) -> int:
    store.reconcile_reserved_iteration(run)
    store.append_history(run.run_id, "resume_started", current_step=run.current_step)
    store.save_run(run)
    return _drive_run(store, config, workflow, run, full_auto=full_auto)


def _reply_active_run(store, config, workflow, run, *, full_auto: bool) -> int:
    store.append_history(run.run_id, "reply_started", current_step=run.current_step)
    _resolve_pending_input(store, config, workflow, run, full_auto=full_auto)
    return _drive_run(store, config, workflow, run, full_auto=full_auto)


def _execute_agent_step(store, config, workflow, run, step, *, full_auto: bool, protocol_warning: str | None) -> str | None:
    if run.step_loops[step.name] + 1 > step.max_loops:
        _fail_run(store, run, FAILURE_MAX_LOOPS, f"step {step.name} exceeded max_loops")
        return None

    next_loop = run.step_loops[step.name] + 1
    context_present = _compute_context_present(store.workspace, workflow, step)
    request_text = render_agent_request(
        workflow,
        run,
        step,
        next_loop,
        protocol_warning,
        store.workspace,
        context_present,
    )
    ctx = store.reserve_iteration(run, step.name, "agent", request_text=request_text, command_argv=[])
    before = snapshot_workspace(store.workspace)
    provider = resolve_provider_for_step(config, workflow, step)
    invocation = invoke_provider(
        provider,
        request_text,
        store.workspace,
        ctx.iteration_dir,
        ctx.final_path,
        child_pid_callback=_active_child_callback(store, run),
    )
    _persist_invocation_outputs(ctx, stdout=invocation.stdout, stderr=invocation.stderr)
    after = snapshot_workspace(store.workspace)

    if invocation.unavailable:
        store.finalize_iteration(
            run,
            ctx,
            command_argv=invocation.command_argv,
            exit_code=invocation.exit_code,
            status="failed",
            transition_target=None,
            input_requested=False,
            question_count=0,
            decision_value=None,
            required_files_missing=[],
            context_present=context_present,
        )
        _fail_run(store, run, FAILURE_PROVIDER_UNAVAILABLE, f"provider {provider.name} unavailable")
        return None

    if invocation.timed_out or invocation.exit_code != 0:
        store.finalize_iteration(
            run,
            ctx,
            command_argv=invocation.command_argv,
            exit_code=invocation.exit_code,
            status="failed",
            transition_target=None,
            input_requested=False,
            question_count=0,
            decision_value=None,
            required_files_missing=[],
            context_present=context_present,
        )
        _fail_run(store, run, FAILURE_STEP_FAILED, f"provider step {step.name} failed")
        return None

    try:
        outcome = parse_agent_outcome(ctx.final_path.read_text(encoding="utf-8"), step.transitions)
    except StepFailedError as exc:
        store.finalize_iteration(
            run,
            ctx,
            command_argv=invocation.command_argv,
            exit_code=invocation.exit_code,
            status="failed",
            transition_target=None,
            input_requested=False,
            question_count=0,
            decision_value=None,
            required_files_missing=[],
            context_present=context_present,
        )
        if run.step_loops[step.name] >= step.max_loops:
            _fail_run(store, run, FAILURE_MAX_LOOPS, f"step {step.name} exceeded max_loops after malformed control output")
            return None
        store.save_run(run)
        return f"{malformed_control_warning()} ({exc})"

    policy_result = evaluate_policy(before, after, step.policy, store.workspace)
    if policy_result.violations:
        store.finalize_iteration(
            run,
            ctx,
            command_argv=invocation.command_argv,
            exit_code=invocation.exit_code,
            status="failed",
            transition_target=None,
            input_requested=False,
            question_count=0,
            decision_value=outcome.decision_value,
            required_files_missing=[],
            context_present=context_present,
        )
        _fail_run(store, run, FAILURE_STEP_FAILED, "; ".join(policy_result.violations))
        return None

    transition_target = outcome.transition_target
    required_missing = []
    if transition_target not in {None, "@retry", "@blocked"}:
        required_missing = policy_result.required_files_missing
    if required_missing:
        store.finalize_iteration(
            run,
            ctx,
            command_argv=invocation.command_argv,
            exit_code=invocation.exit_code,
            status="failed",
            transition_target=None,
            input_requested=False,
            question_count=0,
            decision_value=outcome.decision_value,
            required_files_missing=required_missing,
            context_present=context_present,
        )
        if run.step_loops[step.name] >= step.max_loops:
            _fail_run(store, run, FAILURE_MAX_LOOPS, f"required files missing after {step.name}")
        return malformed_control_warning()

    store.finalize_iteration(
        run,
        ctx,
        command_argv=invocation.command_argv,
        exit_code=invocation.exit_code,
        status="ok",
        transition_target=transition_target,
        input_requested=outcome.input_requested,
        question_count=len(outcome.questions),
        decision_value=outcome.decision_value,
        required_files_missing=required_missing,
        context_present=context_present,
    )

    if outcome.input_requested:
        run.pending_input = _new_pending_input(step.name, ctx.loop, outcome.questions)
        run.status = STATUS_AWAITING_INPUT
        store.save_run(run)
        store.write_active(run, os.getpid())
        store.append_history(
            run.run_id,
            "input_requested",
            step=step.name,
            loop=ctx.loop,
            question_count=len(outcome.questions),
        )
        _resolve_pending_input(store, config, workflow, run, full_auto=full_auto, provider_step=step)
        return None

    return _advance_after_transition(store, workflow, run, step.count_toward_cycles, transition_target)


def _execute_shell_step(store, workflow, run, step) -> str | None:
    if run.step_loops[step.name] + 1 > step.max_loops:
        _fail_run(store, run, FAILURE_MAX_LOOPS, f"step {step.name} exceeded max_loops")
        return None
    command_argv = build_shell_argv(step.cmd)
    ctx = store.reserve_iteration(run, step.name, "shell", command_text=step.cmd, command_argv=command_argv)
    before = snapshot_workspace(store.workspace)
    env = {
        "REFLOW_RUN_ID": run.run_id,
        "REFLOW_WORKFLOW": workflow.name,
        "REFLOW_STEP": step.name,
        "REFLOW_LOOP": str(ctx.loop),
        "REFLOW_WORKSPACE": str(store.workspace),
        "REFLOW_ITERATION_DIR": str(ctx.iteration_dir),
    }
    invocation = invoke_shell(
        step.cmd,
        store.workspace,
        env,
        child_pid_callback=_active_child_callback(store, run),
    )
    _persist_invocation_outputs(ctx, stdout=invocation.stdout, stderr=invocation.stderr, final=invocation.stdout)
    after = snapshot_workspace(store.workspace)

    if invocation.unavailable:
        store.finalize_iteration(
            run,
            ctx,
            command_argv=invocation.command_argv,
            exit_code=invocation.exit_code,
            status="failed",
            transition_target=None,
            input_requested=False,
            question_count=0,
            decision_value=None,
            required_files_missing=[],
            command_text=step.cmd,
        )
        _fail_run(store, run, FAILURE_INTERNAL, f"shell step {step.name} could not start")
        return None

    policy_result = evaluate_policy(before, after, step.policy, store.workspace)
    if policy_result.violations:
        store.finalize_iteration(
            run,
            ctx,
            command_argv=invocation.command_argv,
            exit_code=invocation.exit_code,
            status="failed",
            transition_target=None,
            input_requested=False,
            question_count=0,
            decision_value=None,
            required_files_missing=[],
            command_text=step.cmd,
        )
        _fail_run(store, run, FAILURE_STEP_FAILED, "; ".join(policy_result.violations))
        return None

    transition_target = step.on_success if invocation.exit_code == 0 else step.on_failure
    required_missing = []
    if transition_target not in {"@retry", "@blocked"}:
        required_missing = policy_result.required_files_missing
    if required_missing:
        store.finalize_iteration(
            run,
            ctx,
            command_argv=invocation.command_argv,
            exit_code=invocation.exit_code,
            status="failed",
            transition_target=transition_target,
            input_requested=False,
            question_count=0,
            decision_value=None,
            required_files_missing=required_missing,
            command_text=step.cmd,
        )
        if run.step_loops[step.name] >= step.max_loops:
            _fail_run(store, run, FAILURE_MAX_LOOPS, f"required files missing after {step.name}")
        return None

    store.finalize_iteration(
        run,
        ctx,
        command_argv=invocation.command_argv,
        exit_code=invocation.exit_code,
        status="ok",
        transition_target=transition_target,
        input_requested=False,
        question_count=0,
        decision_value=None,
        required_files_missing=required_missing,
        command_text=step.cmd,
    )
    return _advance_after_transition(store, workflow, run, step.count_toward_cycles, transition_target)


def _resolve_pending_input(store, config, workflow, run, *, full_auto: bool, provider_step=None) -> None:
    pending = run.pending_input
    if pending is None:
        return
    if full_auto:
        step = provider_step or workflow.steps[pending.step]
        _run_full_auto_answers(store, config, workflow, run, step)
        return

    if not _can_prompt_inline():
        _persist_waiting_state(store, run)
        return

    answers = [_prompt(question) for question in pending.questions]
    append_operator_inputs(
        store.operator_inputs_path(run.run_id),
        pending.step,
        pending.loop,
        "human",
        pending.questions,
        answers,
    )
    store.append_history(
        run.run_id,
        "input_resolved",
        step=pending.step,
        loop=pending.loop,
        mode="human",
        question_count=len(pending.questions),
        operator_inputs_file=f".reflow/runs/{run.run_id}/operator_inputs.md",
    )
    run.pending_input = None
    run.status = STATUS_RUNNING
    store.save_run(run)
    store.write_active(run, os.getpid())


def _run_full_auto_answers(store, config, workflow, run, step) -> None:
    pending = run.pending_input
    if pending is None:
        return
    if pending.auto_round >= workflow.operator_input.max_auto_rounds:
        _persist_waiting_state(store, run)
        return
    pending.auto_round += 1
    _persist_waiting_state(store, run)
    provider = resolve_provider_for_step(config, workflow, step)
    request = _build_full_auto_request(workflow, run, step, pending.questions)
    final_path = store.run_dir(run.run_id) / "_full_auto_final.txt"
    invocation = invoke_provider(
        provider,
        request,
        store.workspace,
        None,
        final_path,
        child_pid_callback=_active_child_callback(store, run),
    )
    if invocation.unavailable or invocation.timed_out or invocation.exit_code != 0:
        store.append_history(
            run.run_id,
            "input_auto_failed",
            step=pending.step,
            loop=pending.loop,
            auto_round=pending.auto_round,
            reason="provider_failed",
        )
        _persist_waiting_state(store, run)
        return
    try:
        answers = parse_full_auto_answers(final_path.read_text(encoding="utf-8"), len(pending.questions))
    except StepFailedError as exc:
        store.append_history(
            run.run_id,
            "input_auto_failed",
            step=pending.step,
            loop=pending.loop,
            auto_round=pending.auto_round,
            reason=str(exc),
        )
        _persist_waiting_state(store, run)
        return

    append_operator_inputs(
        store.operator_inputs_path(run.run_id),
        pending.step,
        pending.loop,
        "auto",
        pending.questions,
        answers,
    )
    store.append_history(
        run.run_id,
        "input_resolved",
        step=pending.step,
        loop=pending.loop,
        mode="auto",
        question_count=len(pending.questions),
        operator_inputs_file=f".reflow/runs/{run.run_id}/operator_inputs.md",
    )
    run.pending_input = None
    run.status = STATUS_RUNNING
    store.save_run(run)
    store.write_active(run, os.getpid())


def _advance_after_transition(store, workflow, run, count_toward_cycles: bool, transition_target: str | None) -> str | None:
    if transition_target == "@retry":
        store.save_run(run)
        return None
    if count_toward_cycles:
        run.cycle_count += 1
        if workflow.max_cycles is not None and run.cycle_count > workflow.max_cycles:
            _fail_run(store, run, FAILURE_MAX_CYCLES, f"workflow {workflow.name} exceeded max_cycles")
            return None
    if transition_target == "@done":
        run.status = STATUS_COMPLETED
        store.save_run(run)
        store.append_history(run.run_id, "run_terminal", status=run.status, failure_type=None, failure_reason=None)
        store.clear_active(run.run_id)
        return None
    if transition_target == "@blocked":
        run.status = STATUS_BLOCKED
        store.save_run(run)
        store.append_history(run.run_id, "run_terminal", status=run.status, failure_type=None, failure_reason=None)
        store.clear_active(run.run_id)
        return None
    if transition_target:
        run.current_step = transition_target
    store.save_run(run)
    return None


def _fail_run(store, run, failure_type: str, reason: str) -> None:
    run.status = STATUS_FAILED
    run.failure_type = failure_type
    run.failure_reason = reason
    run.pending_input = None
    store.save_run(run)
    store.append_history(
        run.run_id,
        "run_terminal",
        status=run.status,
        failure_type=run.failure_type,
        failure_reason=run.failure_reason,
    )
    store.clear_active(run.run_id)


def _terminalize_stopped_run(store, run) -> None:
    if run.status in TERMINAL_STATUSES:
        store.clear_active(run.run_id)
        return
    store.reconcile_reserved_iteration(run)
    run.status = STATUS_STOPPED
    run.failure_type = None
    run.failure_reason = None
    run.pending_input = None
    store.save_run(run)
    store.append_history(run.run_id, "run_terminal", status=run.status, failure_type=None, failure_reason=None)
    store.clear_active(run.run_id)


def _new_pending_input(step: str, loop: int, questions: list[str]):
    from .models import PendingInput
    from .storage import utc_now

    return PendingInput(
        requested_at=utc_now(),
        step=step,
        loop=loop,
        questions=list(questions),
        auto_round=0,
    )


def _persist_waiting_state(store, run) -> None:
    run.status = STATUS_AWAITING_INPUT
    store.save_run(run)
    store.write_active(run, os.getpid())


def _run_with_stop_guard(store, run, action) -> int:
    try:
        with _install_stop_signal_handlers():
            return action()
    except KeyboardInterrupt:
        _terminalize_stopped_run(store, run)
        return EXIT_CODE_STOPPED


def _build_full_auto_request(workflow, run, step, questions: list[str]) -> str:
    instructions_path = workflow.operator_input.full_auto_instructions
    if instructions_path is None:
        header = "Answer each pending question using a final <answers> block."
    else:
        header = (workflow.root / instructions_path).read_text(encoding="utf-8").rstrip()
    lines = [header, "", f"workflow: {workflow.name}", f"step: {step.name}", "questions:"]
    for index, question in enumerate(questions, start=1):
        lines.append(f"{index}. {question}")
    lines.extend(
        [
            "",
            "Emit exactly one final <answers> block with one <answer> per question, in order.",
        ]
    )
    return "\n".join(lines) + "\n"


def _normalize_task_for_workflow(workflow_name: str, input_mode: str, task: str | None) -> str | None:
    normalized = task.strip() if isinstance(task, str) else None
    if normalized == "":
        normalized = None
    if input_mode == "required" and normalized is None:
        raise ValueError(
            f"workflow '{workflow_name}' requires a task. Usage: reflow run {workflow_name} \"your task description\""
        )
    if input_mode == "none":
        return None
    return normalized


def _compute_context_present(workspace: Path, workflow, step: AgentStep) -> dict[str, bool]:
    return {entry.path: _context_path_exists(workspace, workflow, entry.path) for entry in step.context}


def _context_path_exists(workspace: Path, workflow, relative_path: str) -> bool:
    return (workspace / relative_path).exists()


def _load_latest_context_present(store: RunStore, run) -> dict[str, bool]:
    step_dir = store.run_dir(run.run_id) / "steps" / run.current_step
    if not step_dir.is_dir():
        return {}
    for iteration_dir in sorted(step_dir.iterdir(), reverse=True):
        meta_path = iteration_dir / "meta.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if isinstance(meta.get("context_present"), dict):
            return {str(key): bool(value) for key, value in meta["context_present"].items()}
    return {}


def _prompt(question: str) -> str:
    print(question)
    return input("> ").rstrip()


def _can_prompt_inline() -> bool:
    stdin = sys.stdin
    return bool(stdin) and not stdin.closed and hasattr(stdin, "isatty") and stdin.isatty()


def _refuse_if_active_conflict(store: RunStore, run_id: str | None = None) -> None:
    active = store.active_lock()
    if not active:
        return
    active_run_id = active.get("run_id")
    active_status = active.get("status")
    active_pid = _safe_int(active.get("controller_pid"))
    stale = False
    try:
        active_run = store.load_run(str(active_run_id))
        stale = active_run.status in TERMINAL_STATUSES
    except FileNotFoundError:
        stale = True
    if not is_pid_alive(active_pid):
        stale = True
    if stale:
        store.clear_active()
        return
    if run_id and active_run_id == run_id:
        raise ValueError(f"workspace is already locked by run {run_id}.")
    raise ValueError(f"workspace is locked by active run {active_run_id}.")


def _exit_code_for_run(run) -> int:
    if run.status == STATUS_COMPLETED:
        return 0
    if run.status == STATUS_BLOCKED:
        return EXIT_CODE_BLOCKED
    if run.status == STATUS_AWAITING_INPUT:
        return EXIT_CODE_AWAITING_INPUT
    if run.status == STATUS_STOPPED:
        return EXIT_CODE_STOPPED
    if run.failure_type == FAILURE_PROVIDER_UNAVAILABLE:
        return EXIT_CODE_PROVIDER_UNAVAILABLE
    if run.failure_type == FAILURE_STEP_FAILED:
        return EXIT_CODE_STEP_FAILED
    if run.failure_type == FAILURE_MAX_LOOPS:
        return EXIT_CODE_MAX_LOOPS
    if run.failure_type == FAILURE_MAX_CYCLES:
        return EXIT_CODE_MAX_CYCLES
    return EXIT_CODE_INTERNAL


def _safe_int(value) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _active_child_callback(store: RunStore, run):
    def callback(child_pid: int | None) -> None:
        store.write_active(run, os.getpid(), child_pid=child_pid)

    return callback


def _persist_invocation_outputs(ctx, *, stdout: str, stderr: str, final: str | None = None) -> None:
    ctx.stdout_path.write_text(stdout, encoding="utf-8")
    ctx.stderr_path.write_text(stderr, encoding="utf-8")
    if final is not None:
        ctx.final_path.write_text(final, encoding="utf-8")


def _signal_active_processes(active: dict[str, object]) -> None:
    child_pid = _safe_int(active.get("child_pid"))
    controller_pid = _safe_int(active.get("controller_pid"))
    for pid in (child_pid, controller_pid):
        if pid and is_pid_alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass


@contextlib.contextmanager
def _install_stop_signal_handlers():
    previous_sigint = signal.getsignal(signal.SIGINT)
    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def _raise_keyboard_interrupt(_signum, _frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGINT, _raise_keyboard_interrupt)
    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
