from __future__ import annotations

from typing import Any

from fuzzy.recipes import SupportCustomer, SupportTicket, triage_support_request


async def handle_support_ticket(*, adapter: Any, model: str, payload: dict[str, Any]) -> dict[str, Any]:
    decision = await triage_support_request(
        adapter=adapter,
        model=model,
        ticket=SupportTicket(
            subject=payload["subject"],
            body=payload["body"],
            channel=payload.get("channel", "email"),
            account_id=payload.get("account_id"),
        ),
        customer=SupportCustomer(
            account_tier=payload["customer"]["account_tier"],
            previous_refunds=payload["customer"].get("previous_refunds", 0),
            has_open_invoice=payload["customer"].get("has_open_invoice", False),
            contract_value_band=payload["customer"].get("contract_value_band", "standard"),
        ),
    )
    return {
        "category": decision.category,
        "urgency": decision.urgency,
        "refund_candidate": decision.refund_candidate,
        "next_action": decision.next_action,
    }
