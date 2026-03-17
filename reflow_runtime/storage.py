from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .models import IterationContext, PendingInput, RunState, WorkspaceSnapshot


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RunStore:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.reflow_dir = workspace / ".reflow"
        self.runs_dir = self.reflow_dir / "runs"
        self.active_path = self.reflow_dir / "active.json"

    def ensure_layout(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def active_lock(self) -> dict[str, object] | None:
        if not self.active_path.exists():
            return None
        return json.loads(self.active_path.read_text(encoding="utf-8"))

    def write_active(self, run: RunState, controller_pid: int, child_pid: int | None = None) -> None:
        payload = {
            "run_id": run.run_id,
            "workflow": run.workflow,
            "status": run.status,
            "started_at": run.started_at,
            "updated_at": run.updated_at,
            "controller_pid": controller_pid,
        }
        if child_pid is not None:
            payload["child_pid"] = child_pid
        atomic_write_json(self.active_path, payload)

    def clear_active(self, run_id: str | None = None) -> None:
        if not self.active_path.exists():
            return
        if run_id is not None:
            try:
                payload = json.loads(self.active_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
            if payload.get("run_id") != run_id:
                return
        self.active_path.unlink(missing_ok=True)

    def create_run(self, workflow_name: str, steps: list[str], entry: str, task: str | None = None) -> RunState:
        self.ensure_layout()
        started_at = utc_now()
        run_id = f"run_{started_at.replace('-', '').replace(':', '').replace('T', 'T').replace('Z', 'Z')}_{uuid.uuid4().hex[:8]}"
        run = RunState(
            run_id=run_id,
            workflow=workflow_name,
            task=task,
            status="running",
            current_step=entry,
            step_loops={name: 0 for name in steps},
            cycle_count=0,
            started_at=started_at,
            updated_at=started_at,
        )
        run_dir = self.run_dir(run_id)
        (run_dir / "steps").mkdir(parents=True, exist_ok=True)
        (run_dir / "operator_inputs.md").write_text("", encoding="utf-8")
        self.save_run(run)
        return run

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def operator_inputs_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "operator_inputs.md"

    def history_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "history.jsonl"

    def run_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "run.json"

    def load_run(self, run_id: str) -> RunState:
        path = self.run_path(run_id)
        if not path.is_file():
            raise FileNotFoundError(f"Run {run_id!r} does not exist.")
        return RunState.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save_run(self, run: RunState) -> None:
        run.updated_at = utc_now()
        atomic_write_json(self.run_path(run.run_id), run.to_dict())

    def append_history(self, run_id: str, event_type: str, **fields: object) -> None:
        payload = {"ts": utc_now(), "type": event_type, "run_id": run_id}
        payload.update(fields)
        with self.history_path(run_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")

    def reserve_iteration(
        self,
        run: RunState,
        step_name: str,
        kind: str,
        *,
        request_text: str | None = None,
        command_text: str | None = None,
        command_argv: list[str] | None = None,
    ) -> IterationContext:
        run.step_loops[step_name] += 1
        loop = run.step_loops[step_name]
        iteration_dir = self.run_dir(run.run_id) / "steps" / step_name / f"{loop:03d}"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = iteration_dir / "stdout.txt"
        stderr_path = iteration_dir / "stderr.txt"
        final_path = iteration_dir / "final.txt"
        meta_path = iteration_dir / "meta.json"
        request_path = iteration_dir / "request.txt" if kind == "agent" else None
        command_path = iteration_dir / "command.txt" if kind == "shell" else None
        if request_path and request_text is not None:
            request_path.write_text(request_text, encoding="utf-8")
        if command_path and command_text is not None:
            command_path.write_text(command_text, encoding="utf-8")
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        final_path.write_text("", encoding="utf-8")
        meta = {
            "step": step_name,
            "loop": loop,
            "kind": kind,
            "command_argv": command_argv or [],
            "started_at": utc_now(),
            "ended_at": None,
            "exit_code": None,
            "status": "failed",
            "transition_target": None,
            "input_requested": False,
            "question_count": 0,
            "decision_value": None,
            "required_files_missing": [],
        }
        if kind == "shell":
            meta["command_text"] = command_text or ""
        atomic_write_json(meta_path, meta)
        self.save_run(run)
        return IterationContext(
            step_name=step_name,
            loop=loop,
            kind=kind,
            iteration_dir=iteration_dir,
            meta_path=meta_path,
            request_path=request_path,
            command_path=command_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            final_path=final_path,
        )

    def finalize_iteration(
        self,
        run: RunState,
        ctx: IterationContext,
        *,
        command_argv: list[str],
        exit_code: int | None,
        status: str,
        transition_target: str | None,
        input_requested: bool,
        question_count: int,
        decision_value: str | None,
        required_files_missing: list[str],
        context_present: dict[str, bool] | None = None,
        command_text: str | None = None,
    ) -> None:
        meta = json.loads(ctx.meta_path.read_text(encoding="utf-8"))
        meta.update(
            {
                "command_argv": command_argv,
                "ended_at": utc_now(),
                "exit_code": exit_code,
                "status": status,
                "transition_target": transition_target,
                "input_requested": input_requested,
                "question_count": question_count,
                "decision_value": decision_value,
                "required_files_missing": list(required_files_missing),
            }
        )
        if command_text is not None:
            meta["command_text"] = command_text
        if context_present is not None:
            meta["context_present"] = dict(context_present)
        atomic_write_json(ctx.meta_path, meta)
        self.append_history(
            run.run_id,
            "iteration_finished",
            step=ctx.step_name,
            loop=ctx.loop,
            kind=ctx.kind,
            status=status,
            exit_code=exit_code,
            transition_target=transition_target,
            iteration_dir=_relative_to_workspace(self.workspace, ctx.iteration_dir),
        )

    def reconcile_reserved_iteration(self, run: RunState) -> None:
        current_loop = run.step_loops.get(run.current_step, 0)
        if current_loop < 1:
            return
        meta_path = self.run_dir(run.run_id) / "steps" / run.current_step / f"{current_loop:03d}" / "meta.json"
        if not meta_path.is_file():
            return
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("ended_at") is not None:
            return
        meta.update(
            {
                "ended_at": utc_now(),
                "exit_code": None,
                "status": "interrupted",
                "transition_target": None,
                "input_requested": False,
                "question_count": 0,
            }
        )
        atomic_write_json(meta_path, meta)
        loop = int(meta["loop"])
        self.append_history(
            run.run_id,
            "iteration_finished",
            step=run.current_step,
            loop=loop,
            kind=meta["kind"],
            status="interrupted",
            exit_code=None,
            transition_target=None,
            iteration_dir=_relative_to_workspace(self.workspace, meta_path.parent),
        )


def atomic_write_json(path: Path, payload: object) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=False) + "\n")


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp_name = handle.name
    os.replace(temp_name, path)


def append_operator_inputs(path: Path, step: str, loop: int, mode: str, questions: list[str], answers: list[str]) -> None:
    timestamp = utc_now()
    lines = [f"## {timestamp} | {step} | loop {loop} | {mode}", ""]
    for index, (question, answer) in enumerate(zip(questions, answers, strict=True), start=1):
        lines.extend([f"Q{index}: {question.splitlines()[0]}"])
        for extra in question.splitlines()[1:]:
            lines.append(f"  {extra}")
        lines.append(f"A{index}: {answer.splitlines()[0]}")
        for extra in answer.splitlines()[1:]:
            lines.append(f"  {extra}")
        lines.append("")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip() + "\n\n")


def is_pid_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _relative_to_workspace(workspace: Path, path: Path) -> str:
    return path.relative_to(workspace).as_posix()
