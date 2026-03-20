from __future__ import annotations

import argparse

import uvicorn

try:
    from _common import resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import resolve_runtime
from app.main import create_app
from shared.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Stage 1 web app.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    resolved_settings, resolved_session_factory = resolve_runtime(
        settings=settings,
        session_factory=session_factory,
    )
    configure_logging(service="web")
    app = create_app(settings=resolved_settings, session_factory=resolved_session_factory)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_config=None,
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
