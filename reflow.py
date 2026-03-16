#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from reflow_runtime.controller import (
    list_runs,
    reply_to_run,
    resume_run,
    run_new_workflow,
    status_run,
    stop_run,
)
from reflow_runtime.models import ConfigError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reflow workflow runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("workflow")
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

    stop_parser = subparsers.add_parser("stop")
    stop_parser.add_argument("run_id")
    stop_parser.add_argument("--workspace", default=".")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--workspace", default=".")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    try:
        if args.command == "run":
            return run_new_workflow(workspace, args.workflow, full_auto=args.full_auto)
        if args.command == "resume":
            return resume_run(workspace, args.run_id, full_auto=args.full_auto)
        if args.command == "reply":
            return reply_to_run(workspace, args.run_id, full_auto=args.full_auto)
        if args.command == "status":
            return status_run(workspace, args.run_id)
        if args.command == "stop":
            return stop_run(workspace, args.run_id)
        if args.command == "list":
            return list_runs(workspace)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 27
    except (ConfigError, FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 25
    return 25


if __name__ == "__main__":
    raise SystemExit(main())
