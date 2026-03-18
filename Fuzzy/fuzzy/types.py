from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, TypedDict


StructuredContract = Mapping[str, Any] | type[Any]
MessageRole = Literal["user", "assistant"]


class TextPart(TypedDict):
    type: Literal["text"]
    text: str


class JsonPart(TypedDict):
    type: Literal["json"]
    data: Any


MessagePart = TextPart | JsonPart


class Message(TypedDict):
    role: MessageRole
    parts: list[MessagePart]


@dataclass(frozen=True)
class Command:
    name: str
    input_schema: StructuredContract
    executor: Callable[[Any], Any]
    description: str | None = None
    output_schema: StructuredContract | None = None
