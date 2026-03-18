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

SupportCategory = Literal["billing", "bug", "feature_request", "abuse", "general"]
SupportUrgency = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class SupportTicket:
    subject: str
    body: str
    channel: str = "email"
    account_id: str | None = None


@dataclass(frozen=True)
class SupportCustomer:
    account_tier: str
    previous_refunds: int = 0
    has_open_invoice: bool = False
    contract_value_band: str = "standard"


@dataclass(frozen=True)
class SupportTriageDecision:
    category: SupportCategory
    urgency: SupportUrgency
    refund_candidate: bool
    next_action: dict[str, Any]


SUPPORT_TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": ["billing", "bug", "feature_request", "abuse", "general"]},
        "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
        "refund_candidate": {"type": "boolean"},
    },
    "required": ["category", "urgency", "refund_candidate"],
    "additionalProperties": False,
}

_SUPPORT_TRIAGE_PROMPT = (
    "Triage the support request conservatively. "
    "Return category, urgency, and whether the customer looks like a refund candidate."
)
_NOOP_EXECUTOR = lambda args: args


async def triage_support_request(
    *,
    adapter: Any,
    model: str,
    ticket: SupportTicket | dict[str, Any] | None = None,
    customer: SupportCustomer | dict[str, Any] | None = None,
    messages: Sequence[Message] | Any = _UNSET,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    system_prompt: str | None = None,
    return_trace: bool = False,
    trace_sink: RecipeTraceSink | None = None,
) -> SupportTriageDecision | RecipeRun[SupportTriageDecision]:
    context = _UNSET if messages is not _UNSET else _support_context(ticket=ticket, customer=customer)
    context, recipe_messages = resolve_messages_or_context(context=context, messages=messages)
    tracer = RecipeTracer(trace_sink)
    should_trace = return_trace or trace_sink is not None

    extraction = await extract(
        adapter=adapter,
        model=model,
        context=context,
        messages=recipe_messages,
        schema=SUPPORT_TRIAGE_SCHEMA,
        max_attempts=max_attempts,
        system_prompt=_SUPPORT_TRIAGE_PROMPT if system_prompt is None else system_prompt,
        return_trace=should_trace,
        trace_sink=tracer.step_sink("triage"),
    )
    triage_data = extraction.value if should_trace else extraction
    dispatch_context, dispatch_messages = extend_recipe_evidence(
        context=context,
        messages=recipe_messages,
        key="triage",
        value=triage_data,
    )

    next_action = await dispatch(
        adapter=adapter,
        model=model,
        context=dispatch_context,
        messages=dispatch_messages,
        labels=None,
        commands=[
            Command(
                name="open_refund_review_case",
                description="Use for high-urgency billing issues or clear refund candidates.",
                input_schema={
                    "type": "object",
                    "properties": {"priority": {"type": "string", "enum": ["medium", "high"]}},
                    "required": ["priority"],
                    "additionalProperties": False,
                },
                executor=_NOOP_EXECUTOR,
            ),
            Command(
                name="route_to_engineering",
                description="Use for bugs or product defects that need engineering follow-up.",
                input_schema={
                    "type": "object",
                    "properties": {"severity": {"type": "string", "enum": ["normal", "urgent"]}},
                    "required": ["severity"],
                    "additionalProperties": False,
                },
                executor=_NOOP_EXECUTOR,
            ),
            Command(
                name="escalate_to_abuse_queue",
                description="Use for harassment, fraud, or abuse reports.",
                input_schema={
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                    "required": ["reason"],
                    "additionalProperties": False,
                },
                executor=_NOOP_EXECUTOR,
            ),
            Command(
                name="reply_with_clarification",
                description="Use when the evidence is too thin for a stronger operational action.",
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
            "Choose the next support workflow action. "
            "Prefer clarification if the issue is ambiguous."
        ),
        return_trace=should_trace,
        trace_sink=tracer.step_sink("next_action"),
    )
    next_action_data = next_action.value if should_trace else next_action

    value = SupportTriageDecision(
        category=triage_data["category"],
        urgency=triage_data["urgency"],
        refund_candidate=triage_data["refund_candidate"],
        next_action=next_action_data,
    )
    return recipe_result(value, return_trace=return_trace, tracer=tracer)


def _support_context(
    *,
    ticket: SupportTicket | dict[str, Any] | None,
    customer: SupportCustomer | dict[str, Any] | None,
) -> dict[str, Any]:
    if ticket is None or customer is None:
        raise ValueError("ticket and customer are required when messages are not supplied")
    return {
        "ticket": asdict(ticket) if isinstance(ticket, SupportTicket) else dict(ticket),
        "customer": asdict(customer) if isinstance(customer, SupportCustomer) else dict(customer),
    }
