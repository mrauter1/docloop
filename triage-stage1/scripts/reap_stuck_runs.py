from __future__ import annotations

import argparse

try:
    from _common import print_json, resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import print_json, resolve_runtime
from worker.main import reap_stuck_runs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reap stuck Stage 1 AI runs.")
    parser.add_argument("--max-age-seconds", type=int, default=None)
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    resolved_settings, resolved_session_factory = resolve_runtime(
        settings=settings,
        session_factory=session_factory,
    )
    reaped_count = reap_stuck_runs(
        resolved_session_factory,
        settings=resolved_settings,
        max_age_seconds=args.max_age_seconds,
    )
    print_json({"status": "ok", "reaped_count": reaped_count})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
