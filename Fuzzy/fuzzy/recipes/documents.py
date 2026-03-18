from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from ..core import DEFAULT_MAX_ATTEMPTS, _UNSET, dispatch, extract
from ..types import Command, Message
from .common import (
    RecipeRun,
    RecipeTraceSink,
    RecipeTracer,
    extend_recipe_evidence,
    recipe_result,
    resolve_messages_or_context,
)


@dataclass(frozen=True)
class DocumentPackage:
    applicant_type: str
    documents: list[dict[str, Any]]
    submitted_fields: dict[str, Any]
    jurisdiction: str


@dataclass(frozen=True)
class DocumentCompletenessDecision:
    is_complete: bool
    missing_items: list[str]
    risk_flags: list[str]
    next_action: dict[str, Any]


DOCUMENT_COMPLETENESS_SCHEMA = {
    "type": "object",
    "properties": {
        "is_complete": {"type": "boolean"},
        "missing_items": {
            "type": "array",
            "items": {"type": "string"},
        },
        "risk_flags": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["is_complete", "missing_items", "risk_flags"],
    "additionalProperties": False,
}

_DOCUMENT_PROMPT = (
    "Assess whether the submitted document package is complete enough to move forward. "
    "Return whether it is complete, which items are missing, and any risk flags that require manual review."
)
_NOOP_EXECUTOR = lambda args: args


async def assess_document_completeness(
    *,
    adapter: Any,
    model: str,
    package: DocumentPackage | dict[str, Any] | None = None,
    messages: Sequence[Message] | Any = _UNSET,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    system_prompt: str | None = None,
    return_trace: bool = False,
    trace_sink: RecipeTraceSink | None = None,
) -> DocumentCompletenessDecision | RecipeRun[DocumentCompletenessDecision]:
    context = _UNSET if messages is not _UNSET else _document_context(package=package)
    context, recipe_messages = resolve_messages_or_context(context=context, messages=messages)
    tracer = RecipeTracer(trace_sink)
    should_trace = return_trace or trace_sink is not None

    extraction = await extract(
        adapter=adapter,
        model=model,
        context=context,
        messages=recipe_messages,
        schema=DOCUMENT_COMPLETENESS_SCHEMA,
        max_attempts=max_attempts,
        system_prompt=_DOCUMENT_PROMPT if system_prompt is None else system_prompt,
        return_trace=should_trace,
        trace_sink=tracer.step_sink("assessment"),
    )
    assessment = extraction.value if should_trace else extraction
    dispatch_context, dispatch_messages = extend_recipe_evidence(
        context=context,
        messages=recipe_messages,
        key="assessment",
        value=assessment,
    )

    next_action = await dispatch(
        adapter=adapter,
        model=model,
        context=dispatch_context,
        messages=dispatch_messages,
        commands=[
            Command(
                name="request_missing_documents",
                description="Use when the package is incomplete and the missing items are clear enough to request directly.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                        }
                    },
                    "required": ["items"],
                    "additionalProperties": False,
                },
                executor=_NOOP_EXECUTOR,
            ),
            Command(
                name="advance_to_manual_review",
                description="Use when the package is complete enough for a human analyst to continue review.",
                input_schema={
                    "type": "object",
                    "properties": {"queue": {"type": "string"}},
                    "required": ["queue"],
                    "additionalProperties": False,
                },
                executor=_NOOP_EXECUTOR,
            ),
            Command(
                name="escalate_risk_review",
                description="Use when risk flags require a specialized manual review path even if the package is complete.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string"},
                    },
                    "required": ["reason"],
                    "additionalProperties": False,
                },
                executor=_NOOP_EXECUTOR,
            ),
        ],
        max_attempts=max_attempts,
        system_prompt=(
            "Choose the next operational document-intake action. "
            "Prefer requesting specific missing documents when incompleteness is the main issue."
        ),
        return_trace=should_trace,
        trace_sink=tracer.step_sink("next_action"),
    )
    next_action_data = next_action.value if should_trace else next_action

    value = DocumentCompletenessDecision(
        is_complete=assessment["is_complete"],
        missing_items=list(assessment["missing_items"]),
        risk_flags=list(assessment["risk_flags"]),
        next_action=next_action_data,
    )
    return recipe_result(value, return_trace=return_trace, tracer=tracer)


def _document_context(*, package: DocumentPackage | dict[str, Any] | None) -> dict[str, Any]:
    if package is None:
        raise ValueError("package is required when messages are not supplied")
    return {"package": asdict(package) if isinstance(package, DocumentPackage) else dict(package)}
