from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


StructuredContract = Mapping[str, Any] | type[Any]


@dataclass(frozen=True)
class Command:
    name: str
    input_schema: StructuredContract
    executor: Callable[[Any], Any]
    description: str | None = None
    output_schema: StructuredContract | None = None
