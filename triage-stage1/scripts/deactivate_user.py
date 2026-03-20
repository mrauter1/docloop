from __future__ import annotations

import argparse

try:
    from _common import print_json, resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import print_json, resolve_runtime
from shared.db import session_scope
from shared.user_admin import UserAdminError, deactivate_user_account


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deactivate a local triage user.")
    parser.add_argument("--email", required=True)
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    _, resolved_session_factory = resolve_runtime(settings=settings, session_factory=session_factory)
    try:
        with session_scope(resolved_session_factory) as session:
            user = deactivate_user_account(session, email=args.email)
            payload = {
                "status": "ok",
                "user_id": str(user.id),
                "email": user.email,
                "is_active": user.is_active,
            }
    except UserAdminError as exc:
        print_json({"status": "error", "error": str(exc)})
        return 1

    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
