from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class Command:
    name: str
    input_schema: Mapping[str, Any]
    executor: Callable[[dict[str, Any]], Any]
    description: str | None = None
    output_schema: Mapping[str, Any] | None = None
