from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from .models import InvocationResult, ProviderProfile


def invoke_provider(
    profile: ProviderProfile,
    request: str,
    workspace: Path,
    iteration_dir: Path | None,
    final_path: Path | None,
    *,
    child_pid_callback: Callable[[int | None], None] | None = None,
) -> InvocationResult:
    if final_path is None:
        raise ValueError("final_path is required for provider invocation.")
    command_argv = build_provider_argv(profile, request, workspace, final_path)
    env = os.environ.copy()
    env.update(profile.env)
    result = _run_process(
        command_argv,
        workspace,
        env,
        timeout=profile.timeout_sec,
        child_pid_callback=child_pid_callback,
    )
    if result.unavailable:
        return result

    if profile.kind == "claude":
        final_path.write_text(result.stdout, encoding="utf-8")
    elif not final_path.exists():
        final_path.write_text("", encoding="utf-8")

    return result


def invoke_shell(
    cmd: str,
    workspace: Path,
    env_overrides: dict[str, str],
    *,
    child_pid_callback: Callable[[int | None], None] | None = None,
) -> InvocationResult:
    command_argv = build_shell_argv(cmd)
    env = os.environ.copy()
    env.update(env_overrides)
    env.setdefault("HOME", str(workspace))
    env["BASH_ENV"] = ""
    env["ENV"] = ""
    return _run_process(
        command_argv,
        workspace,
        env,
        timeout=None,
        child_pid_callback=child_pid_callback,
    )


def build_provider_argv(profile: ProviderProfile, request: str, workspace: Path, final_path: Path) -> list[str]:
    if profile.kind == "codex":
        argv = [profile.command, "exec", "--cd", str(workspace)]
        if profile.model:
            argv.extend(["--model", profile.model])
        argv.extend(profile.args)
        argv.extend(["--output-last-message", str(final_path), request])
        return argv

    argv = [profile.command, "-p", request]
    if profile.model:
        argv.extend(["--model", profile.model])
    argv.extend(profile.args)
    return argv


def build_shell_argv(cmd: str) -> list[str]:
    return ["/bin/sh", "-lc", cmd]


def _run_process(
    command_argv: list[str],
    workspace: Path,
    env: dict[str, str],
    *,
    timeout: int | None,
    child_pid_callback: Callable[[int | None], None] | None,
) -> InvocationResult:
    try:
        process = subprocess.Popen(
            command_argv,
            cwd=workspace,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        return InvocationResult(command_argv=command_argv, stdout="", stderr="", exit_code=None, unavailable=True)

    _publish_child_pid(child_pid_callback, process.pid)
    try:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return InvocationResult(
                command_argv=command_argv,
                stdout=stdout,
                stderr=stderr,
                exit_code=None,
                timed_out=True,
            )
        except KeyboardInterrupt:
            _terminate_process(process)
            raise
    finally:
        _publish_child_pid(child_pid_callback, None)

    return InvocationResult(
        command_argv=command_argv,
        stdout=stdout,
        stderr=stderr,
        exit_code=process.returncode,
    )


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()


def _publish_child_pid(callback: Callable[[int | None], None] | None, pid: int | None) -> None:
    if callback is not None:
        callback(pid)
