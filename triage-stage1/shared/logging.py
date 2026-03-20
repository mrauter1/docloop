from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    def __init__(self, *, default_service: str) -> None:
        super().__init__()
        self.default_service = default_service

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": self.default_service,
            "level": record.levelname.lower(),
            "logger": record.name,
        }
        structured = getattr(record, "structured_payload", None)
        if isinstance(structured, dict):
            payload.update(structured)
        else:
            payload["message"] = record.getMessage()
        payload.setdefault("service", self.default_service)
        return json.dumps(payload, default=str)


def configure_logging(*, service: str, level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(default_service=service))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def log_event(
    logger: logging.Logger,
    *,
    service: str,
    event: str,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    payload = {"service": service, "event": event, **fields}
    logger.log(level, event, extra={"structured_payload": payload})
