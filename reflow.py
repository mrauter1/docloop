#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from reflow_runtime.controller import (
    init_workflow,
    list_runs,
    reply_to_run,
    resume_run,
    run_new_workflow,
    status_run,
    stop_run,
    validate_workflow,
)
from reflow_runtime.models import ConfigError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reflow workflow runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("workflow")
    run_parser.add_argument("task", nargs="?")
    run_parser.add_argument("--task-file")
    run_parser.add_argument("--workspace", default=".")
    run_parser.add_argument("--full-auto", action="store_true")

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("run_id")
    resume_parser.add_argument("--workspace", default=".")
    resume_parser.add_argument("--full-auto", action="store_true")

    reply_parser = subparsers.add_parser("reply")
    reply_parser.add_argument("run_id")
    reply_parser.add_argument("--workspace", default=".")
    reply_parser.add_argument("--full-auto", action="store_true")

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("run_id")
    status_parser.add_argument("--workspace", default=".")
    status_parser.add_argument("--verbose", action="store_true")

    stop_parser = subparsers.add_parser("stop")
    stop_parser.add_argument("run_id")
    stop_parser.add_argument("--workspace", default=".")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--workspace", default=".")

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("workflow")
    validate_parser.add_argument("--workspace", default=".")

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("workflow")
    init_parser.add_argument("--template", default="write-verify", choices=["write-verify", "single-agent"])
    init_parser.add_argument("--provider", default="codex", choices=["codex", "claude"])
    init_parser.add_argument("--target", default="target.md")
    init_parser.add_argument("--workspace", default=".")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    try:
        if args.command == "run":
            task = _load_task_argument(args.task, args.task_file)
            return run_new_workflow(workspace, args.workflow, full_auto=args.full_auto, task=task)
        if args.command == "resume":
            return resume_run(workspace, args.run_id, full_auto=args.full_auto)
        if args.command == "reply":
            return reply_to_run(workspace, args.run_id, full_auto=args.full_auto)
        if args.command == "status":
            return status_run(workspace, args.run_id, verbose=args.verbose)
        if args.command == "stop":
            return stop_run(workspace, args.run_id)
        if args.command == "list":
            return list_runs(workspace)
        if args.command == "validate":
            return validate_workflow(workspace, args.workflow)
        if args.command == "init":
            return init_workflow(
                workspace,
                args.workflow,
                template_name=args.template,
                provider_kind=args.provider,
                target=args.target,
            )
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 27
    except (ConfigError, FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 25

    return 25


def _load_task_argument(task: str | None, task_file: str | None) -> str | None:
    if task is not None and task_file is not None:
        raise ValueError("TASK and --task-file are mutually exclusive.")
    if task_file is None:
        return task
    return Path(task_file).read_text(encoding="utf-8").strip() or None


if __name__ == "__main__":
    raise SystemExit(main())
