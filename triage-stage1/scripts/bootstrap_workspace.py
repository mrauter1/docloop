from __future__ import annotations

import argparse

try:
    from _common import print_json, resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import print_json, resolve_runtime
from shared.bootstrap import DEFAULT_BOOTSTRAP_VERSION, WorkspaceBootstrapError, bootstrap_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap the Stage 1 triage workspace.")
    parser.add_argument(
        "--bootstrap-version",
        default=DEFAULT_BOOTSTRAP_VERSION,
        help="Value written to system_state.bootstrap_version.",
    )
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    resolved_settings, resolved_session_factory = resolve_runtime(
        settings=settings,
        session_factory=session_factory,
    )
    try:
        result = bootstrap_workspace(
            resolved_settings,
            session_factory=resolved_session_factory,
            bootstrap_version=args.bootstrap_version,
        )
    except WorkspaceBootstrapError as exc:
        print_json({"status": "error", "error": str(exc)})
        return 1

    payload = {"status": "ok"}
    payload.update(result.as_dict())
    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
