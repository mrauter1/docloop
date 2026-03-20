from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import Settings, get_settings  # noqa: E402
from shared.db import make_session_factory  # noqa: E402


def resolve_runtime(
    *,
    settings: Settings | None = None,
    session_factory=None,
):
    resolved_settings = settings or get_settings()
    resolved_session_factory = session_factory or make_session_factory(settings=resolved_settings)
    return resolved_settings, resolved_session_factory


def print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, default=str))
