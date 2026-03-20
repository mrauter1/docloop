from __future__ import annotations

import argparse

try:
    from _common import resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import resolve_runtime
from shared.logging import configure_logging
from worker.main import run_worker_loop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Stage 1 worker.")
    parser.add_argument("--once", action="store_true", help="Process at most one polling iteration.")
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    resolved_settings, resolved_session_factory = resolve_runtime(
        settings=settings,
        session_factory=session_factory,
    )
    configure_logging(service="worker")
    run_worker_loop(
        settings=resolved_settings,
        session_factory=resolved_session_factory,
        once=args.once,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
