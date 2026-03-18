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

RiskTier = Literal["low", "medium", "high"]
ApprovalRoute = Literal["auto_approve", "manager_review", "security_review", "deny"]


@dataclass(frozen=True)
class ApprovalRequest:
    requester_role: str
    requested_system: str
    justification: str
    estimated_impact: str


@dataclass(frozen=True)
class ApprovalRoutingDecision:
    risk_tier: RiskTier
    route: ApprovalRoute
    needs_manual_review: bool
    next_action: dict[str, Any]


APPROVAL_ROUTING_SCHEMA = {
    "type": "object",
    "properties": {
        "risk_tier": {"type": "string", "enum": ["low", "medium", "high"]},
        "route": {"type": "string", "enum": ["auto_approve", "manager_review", "security_review", "deny"]},
        "needs_manual_review": {"type": "boolean"},
    },
    "required": ["risk_tier", "route", "needs_manual_review"],
    "additionalProperties": False,
}

_APPROVAL_PROMPT = (
    "Assess the approval request conservatively. "
    "Return risk tier, routing path, and whether manual review is required."
)
_NOOP_EXECUTOR = lambda args: args


async def route_approval(
    *,
    adapter: Any,
    model: str,
    request: ApprovalRequest | dict[str, Any] | None = None,
    messages: Sequence[Message] | Any = _UNSET,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    system_prompt: str | None = None,
    return_trace: bool = False,
    trace_sink: RecipeTraceSink | None = None,
) -> ApprovalRoutingDecision | RecipeRun[ApprovalRoutingDecision]:
    context = _UNSET if messages is not _UNSET else _approval_context(request=request)
    context, recipe_messages = resolve_messages_or_context(context=context, messages=messages)
    tracer = RecipeTracer(trace_sink)
    should_trace = return_trace or trace_sink is not None

    extraction = await extract(
        adapter=adapter,
        model=model,
        context=context,
        messages=recipe_messages,
        schema=APPROVAL_ROUTING_SCHEMA,
        max_attempts=max_attempts,
        system_prompt=_APPROVAL_PROMPT if system_prompt is None else system_prompt,
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
                name="approve_request",
                description="Use only when risk is low and policy fit is clear.",
                input_schema={
                    "type": "object",
                    "properties": {"note": {"type": "string"}},
                    "required": ["note"],
                    "additionalProperties": False,
                },
                executor=_NOOP_EXECUTOR,
            ),
            Command(
                name="route_to_manager",
                description="Use for medium-risk requests that need managerial approval.",
                input_schema={
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                    "required": ["reason"],
                    "additionalProperties": False,
                },
                executor=_NOOP_EXECUTOR,
            ),
            Command(
                name="route_to_security",
                description="Use for elevated-risk systems or requests with sensitive scope.",
                input_schema={
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                    "required": ["reason"],
                    "additionalProperties": False,
                },
                executor=_NOOP_EXECUTOR,
            ),
            Command(
                name="deny_request",
                description="Use when the request is clearly out of policy or unjustified.",
                input_schema={
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                    "required": ["reason"],
                    "additionalProperties": False,
                },
                executor=_NOOP_EXECUTOR,
            ),
        ],
        max_attempts=max_attempts,
        system_prompt=(
            "Choose the operational approval action. "
            "Preserve manual review for medium or high risk requests."
        ),
        return_trace=should_trace,
        trace_sink=tracer.step_sink("next_action"),
    )
    next_action_data = next_action.value if should_trace else next_action

    value = ApprovalRoutingDecision(
        risk_tier=assessment["risk_tier"],
        route=assessment["route"],
        needs_manual_review=assessment["needs_manual_review"],
        next_action=next_action_data,
    )
    return recipe_result(value, return_trace=return_trace, tracer=tracer)


def _approval_context(*, request: ApprovalRequest | dict[str, Any] | None) -> dict[str, Any]:
    if request is None:
        raise ValueError("request is required when messages are not supplied")
    return {"request": asdict(request) if isinstance(request, ApprovalRequest) else dict(request)}
