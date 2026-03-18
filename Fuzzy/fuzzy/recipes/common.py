from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, Sequence, TypeVar

from ..core import _UNSET
from ..trace import TraceRecord

T = TypeVar("T")
RecipeTraceSink = Callable[["RecipeStepTrace"], Any]


@dataclass(frozen=True)
class RecipeStepTrace:
    step: str
    trace: TraceRecord


@dataclass(frozen=True)
class RecipeRun(Generic[T]):
    value: T
    traces: tuple[RecipeStepTrace, ...]


class RecipeTracer:
    def __init__(self, sink: RecipeTraceSink | None = None) -> None:
        self._sink = sink
        self._traces: list[RecipeStepTrace] = []

    def step_sink(self, step: str) -> Callable[[TraceRecord], None]:
        def sink(trace: TraceRecord) -> None:
            step_trace = RecipeStepTrace(step=step, trace=trace)
            self._traces.append(step_trace)
            if self._sink is not None:
                self._sink(step_trace)

        return sink

    def snapshot(self) -> tuple[RecipeStepTrace, ...]:
        return tuple(self._traces)


def recipe_result(value: T, *, return_trace: bool, tracer: RecipeTracer) -> T | RecipeRun[T]:
    if return_trace:
        return RecipeRun(value=value, traces=tracer.snapshot())
    return value


def resolve_messages_or_context(
    *,
    context: Any,
    messages: Sequence[dict[str, Any]] | Any,
) -> tuple[Any, Sequence[dict[str, Any]] | Any]:
    if messages is _UNSET:
        return context, _UNSET
    return _UNSET, messages


def extend_recipe_evidence(
    *,
    context: Any,
    messages: Sequence[dict[str, Any]] | Any,
    key: str,
    value: Any,
) -> tuple[Any, Sequence[dict[str, Any]] | Any]:
    if messages is not _UNSET:
        return _UNSET, [
            *messages,
            {
                "role": "user",
                "parts": [
                    {
                        "type": "json",
                        "data": {
                            key: value,
                        },
                    }
                ],
            },
        ]

    if context is _UNSET:
        return {key: value}, _UNSET

    if isinstance(context, dict):
        return {**context, key: value}, _UNSET

    return {"evidence": context, key: value}, _UNSET
