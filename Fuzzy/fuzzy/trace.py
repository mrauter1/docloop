from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Generic, Iterable, Mapping, Sequence, TypeVar

from .schema import deterministic_json_dumps, ensure_json_compatible

T = TypeVar("T")
TraceSink = Callable[["TraceRecord"], Any]
_REDACTION_TOKEN = "[REDACTED]"


@dataclass(frozen=True)
class TraceAttempt:
    attempt: int
    model: str
    instructions: str
    raw_text: str | None = None
    parsed_payload: Any = None
    provider_response_id: str | None = None
    provider_metadata: dict[str, Any] | None = None
    validation_category: str | None = None
    validation_message: str | None = None
    provider_category: str | None = None
    provider_message: str | None = None
    success: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "attempt": self.attempt,
            "model": self.model,
            "instructions": self.instructions,
            "raw_text": self.raw_text,
            "parsed_payload": _json_safe(self.parsed_payload),
            "provider_response_id": self.provider_response_id,
            "provider_metadata": _json_safe(self.provider_metadata),
            "validation_category": self.validation_category,
            "validation_message": self.validation_message,
            "provider_category": self.provider_category,
            "provider_message": self.provider_message,
            "success": self.success,
        }
        return {key: value for key, value in payload.items() if value is not None}


@dataclass(frozen=True)
class TraceRecord:
    operation: str
    model: str
    messages: list[dict[str, Any]]
    output_schema: dict[str, Any]
    system_prompt: str | None
    attempts: tuple[TraceAttempt, ...]
    attempt_count: int
    success: bool
    final_validation_category: str | None = None
    final_validation_message: str | None = None
    result: Any = None
    error: dict[str, Any] | None = None
    trace_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _build_trace_id(self._payload_without_id()))

    def _payload_without_id(self) -> dict[str, Any]:
        payload = {
            "operation": self.operation,
            "model": self.model,
            "messages": _json_safe(self.messages),
            "output_schema": _json_safe(self.output_schema),
            "system_prompt": self.system_prompt,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "attempt_count": self.attempt_count,
            "success": self.success,
            "final_validation_category": self.final_validation_category,
            "final_validation_message": self.final_validation_message,
            "result": _json_safe(self.result),
            "error": _json_safe(self.error),
        }
        return {key: value for key, value in payload.items() if value is not None}

    def to_dict(self, *, redact: Sequence[str] | None = None) -> dict[str, Any]:
        payload = {"trace_id": self.trace_id, **self._payload_without_id()}
        return apply_redaction(payload, redact)


@dataclass(frozen=True)
class TraceResult(Generic[T]):
    value: T
    trace: TraceRecord


def save_trace(
    trace_or_result: TraceRecord | TraceResult[Any] | Mapping[str, Any],
    path_or_dir: str | Path,
    *,
    redact: Sequence[str] | None = None,
) -> Path:
    payload = _trace_payload(trace_or_result, redact=redact)
    target = Path(path_or_dir)
    if target.suffix.lower() != ".json":
        trace_id = payload.get("trace_id", "trace")
        target = target / f"{trace_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(deterministic_json_dumps(payload) + "\n", encoding="utf-8")
    return target


def render_trace_html(
    trace_or_path: TraceRecord | TraceResult[Any] | Mapping[str, Any] | str | Path,
    *,
    redact: Sequence[str] | None = None,
) -> str:
    payload = _resolve_trace_payload(trace_or_path, redact=redact)
    attempts = payload.get("attempts", [])
    attempt_rows = []
    for attempt in attempts:
        attempt_json = html.escape(json.dumps(attempt, indent=2, ensure_ascii=False, sort_keys=True))
        attempt_rows.append(
            "<details><summary>"
            f"Attempt {attempt.get('attempt')} | success={attempt.get('success', False)}"
            "</summary><pre>"
            f"{attempt_json}"
            "</pre></details>"
        )

    payload_json = html.escape(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Fuzzy Trace</title>"
        "<style>"
        "body{font-family:ui-monospace,SFMono-Regular,monospace;margin:2rem;line-height:1.4;}"
        "pre{background:#f6f8fa;padding:1rem;overflow:auto;border-radius:8px;}"
        "details{margin:0.75rem 0;}"
        "dl{display:grid;grid-template-columns:max-content 1fr;gap:0.5rem 1rem;}"
        "dt{font-weight:700;}"
        "</style></head><body>"
        "<h1>Fuzzy Trace</h1>"
        "<dl>"
        f"<dt>Trace ID</dt><dd>{html.escape(str(payload.get('trace_id', '')))}</dd>"
        f"<dt>Operation</dt><dd>{html.escape(str(payload.get('operation', '')))}</dd>"
        f"<dt>Model</dt><dd>{html.escape(str(payload.get('model', '')))}</dd>"
        f"<dt>Success</dt><dd>{html.escape(str(payload.get('success', False)))}</dd>"
        f"<dt>Attempts</dt><dd>{html.escape(str(payload.get('attempt_count', 0)))}</dd>"
        "</dl>"
        "<h2>Attempts</h2>"
        f"{''.join(attempt_rows) or '<p>No attempts recorded.</p>'}"
        "<h2>Trace JSON</h2>"
        f"<pre>{payload_json}</pre>"
        "</body></html>"
    )


def write_trace_html(
    trace_or_path: TraceRecord | TraceResult[Any] | Mapping[str, Any] | str | Path,
    output_path: str | Path,
    *,
    redact: Sequence[str] | None = None,
) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_trace_html(trace_or_path, redact=redact), encoding="utf-8")
    return target


def apply_redaction(payload: Mapping[str, Any], redact: Sequence[str] | None = None) -> dict[str, Any]:
    cloned = _clone_json_value(payload)
    for path in redact or ():
        segments = _parse_redaction_path(path)
        _apply_redaction_path(cloned, segments)
    return cloned


def serialize_trace(trace_or_result: TraceRecord | TraceResult[Any] | Mapping[str, Any]) -> dict[str, Any]:
    return _trace_payload(trace_or_result, redact=None)


def _trace_payload(
    trace_or_result: TraceRecord | TraceResult[Any] | Mapping[str, Any],
    *,
    redact: Sequence[str] | None,
) -> dict[str, Any]:
    if isinstance(trace_or_result, TraceResult):
        return trace_or_result.trace.to_dict(redact=redact)
    if isinstance(trace_or_result, TraceRecord):
        return trace_or_result.to_dict(redact=redact)
    if isinstance(trace_or_result, Mapping):
        return apply_redaction(_json_safe(trace_or_result), redact)
    raise TypeError("trace_or_result must be a TraceRecord, TraceResult, or mapping")


def _resolve_trace_payload(
    trace_or_path: TraceRecord | TraceResult[Any] | Mapping[str, Any] | str | Path,
    *,
    redact: Sequence[str] | None,
) -> dict[str, Any]:
    if isinstance(trace_or_path, (TraceRecord, TraceResult)) or isinstance(trace_or_path, Mapping):
        return _trace_payload(trace_or_path, redact=redact)

    path = Path(trace_or_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Stored trace must be a JSON object")
    return apply_redaction(_json_safe(payload), redact)


def _build_trace_id(payload: Mapping[str, Any]) -> str:
    digest = sha256(deterministic_json_dumps(payload).encode("utf-8")).hexdigest()
    return f"trace-{digest[:16]}"


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    try:
        ensure_json_compatible(value)
    except Exception:
        if isinstance(value, Mapping):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_json_safe(item) for item in value]
        return {"repr": repr(value), "type": type(value).__name__}
    return _clone_json_value(value)


def _clone_json_value(value: Any) -> Any:
    return json.loads(deterministic_json_dumps(value))


def _parse_redaction_path(path: str) -> list[str | int]:
    if not isinstance(path, str) or not path.startswith("$"):
        raise ValueError("redaction paths must start with '$'")
    if path == "$":
        return []

    tokens: list[str | int] = []
    index = 1
    while index < len(path):
        char = path[index]
        if char == ".":
            next_index = index + 1
            while next_index < len(path) and path[next_index] not in ".[":
                next_index += 1
            token = path[index + 1 : next_index]
            if not token:
                raise ValueError(f"invalid redaction path {path!r}")
            tokens.append(token)
            index = next_index
            continue
        if char == "[":
            next_index = path.find("]", index)
            if next_index == -1:
                raise ValueError(f"invalid redaction path {path!r}")
            token = path[index + 1 : next_index]
            if token.isdigit():
                tokens.append(int(token))
            elif token.startswith(("'", '"')) and token.endswith(("'", '"')) and len(token) >= 2:
                tokens.append(token[1:-1])
            else:
                tokens.append(token)
            index = next_index + 1
            continue
        raise ValueError(f"invalid redaction path {path!r}")
    return tokens


def _apply_redaction_path(container: Any, tokens: Iterable[str | int]) -> None:
    token_list = list(tokens)
    if not token_list:
        return

    current = container
    for token in token_list[:-1]:
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                return
            current = current[token]
            continue
        if not isinstance(current, dict) or token not in current:
            return
        current = current[token]

    final_token = token_list[-1]
    if isinstance(final_token, int):
        if isinstance(current, list) and final_token < len(current):
            current[final_token] = _REDACTION_TOKEN
        return
    if isinstance(current, dict) and final_token in current:
        current[final_token] = _REDACTION_TOKEN
