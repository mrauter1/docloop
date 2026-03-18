from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Sequence

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

LeadSegment = Literal["enterprise", "mid_market", "smb", "startup"]
BudgetBand = Literal["low", "medium", "high", "unknown"]
LeadUrgency = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class LeadProfile:
    company_name: str
    employee_count: int
    industry: str
    inbound_message: str


@dataclass(frozen=True)
class LeadQualificationDecision:
    segment: LeadSegment
    budget_band: BudgetBand
    urgency: LeadUrgency
    qualified: bool
    next_action: dict[str, Any]


LEAD_QUALIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "segment": {"type": "string", "enum": ["enterprise", "mid_market", "smb", "startup"]},
        "budget_band": {"type": "string", "enum": ["low", "medium", "high", "unknown"]},
        "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
        "qualified": {"type": "boolean"},
    },
    "required": ["segment", "budget_band", "urgency", "qualified"],
    "additionalProperties": False,
}

_LEAD_PROMPT = (
    "Qualify the inbound lead for a B2B sales team. "
    "Return segment, budget band, urgency, and whether the lead is qualified."
)
_NOOP_EXECUTOR = lambda args: args


async def qualify_lead(
    *,
    adapter: Any,
    model: str,
    lead: LeadProfile | dict[str, Any] | None = None,
    messages: Sequence[Message] | Any = _UNSET,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    system_prompt: str | None = None,
    return_trace: bool = False,
    trace_sink: RecipeTraceSink | None = None,
) -> LeadQualificationDecision | RecipeRun[LeadQualificationDecision]:
    context = _UNSET if messages is not _UNSET else _lead_context(lead=lead)
    context, recipe_messages = resolve_messages_or_context(context=context, messages=messages)
    tracer = RecipeTracer(trace_sink)
    should_trace = return_trace or trace_sink is not None

    extraction = await extract(
        adapter=adapter,
        model=model,
        context=context,
        messages=recipe_messages,
        schema=LEAD_QUALIFICATION_SCHEMA,
        max_attempts=max_attempts,
        system_prompt=_LEAD_PROMPT if system_prompt is None else system_prompt,
        return_trace=should_trace,
        trace_sink=tracer.step_sink("qualification"),
    )
    qualification = extraction.value if should_trace else extraction
    dispatch_context, dispatch_messages = extend_recipe_evidence(
        context=context,
        messages=recipe_messages,
        key="qualification",
        value=qualification,
    )

    next_action = await dispatch(
        adapter=adapter,
        model=model,
        context=dispatch_context,
        messages=dispatch_messages,
        commands=[
            Command(
                name="assign_account_executive",
                description="Use for qualified high-value leads that need direct follow-up.",
                input_schema={
                    "type": "object",
                    "properties": {"priority": {"type": "string", "enum": ["standard", "expedited"]}},
                    "required": ["priority"],
                    "additionalProperties": False,
                },
                executor=_NOOP_EXECUTOR,
            ),
            Command(
                name="enqueue_nurture_sequence",
                description="Use for promising leads that are not ready for direct sales follow-up.",
                input_schema={
                    "type": "object",
                    "properties": {"track": {"type": "string", "enum": ["education", "product_updates"]}},
                    "required": ["track"],
                    "additionalProperties": False,
                },
                executor=_NOOP_EXECUTOR,
            ),
            Command(
                name="request_more_context",
                description="Use when budget, timing, or fit is too unclear.",
                input_schema={
                    "type": "object",
                    "properties": {"question": {"type": "string"}},
                    "required": ["question"],
                    "additionalProperties": False,
                },
                executor=_NOOP_EXECUTOR,
            ),
        ],
        max_attempts=max_attempts,
        system_prompt=(
            "Choose the next sales workflow action. "
            "Do not assign an account executive unless the lead is clearly qualified."
        ),
        return_trace=should_trace,
        trace_sink=tracer.step_sink("next_action"),
    )
    next_action_data = next_action.value if should_trace else next_action

    value = LeadQualificationDecision(
        segment=qualification["segment"],
        budget_band=qualification["budget_band"],
        urgency=qualification["urgency"],
        qualified=qualification["qualified"],
        next_action=next_action_data,
    )
    return recipe_result(value, return_trace=return_trace, tracer=tracer)


def _lead_context(*, lead: LeadProfile | dict[str, Any] | None) -> dict[str, Any]:
    if lead is None:
        raise ValueError("lead is required when messages are not supplied")
    return {"lead": asdict(lead) if isinstance(lead, LeadProfile) else dict(lead)}
