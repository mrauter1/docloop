from __future__ import annotations

from typing import Any

from fuzzy.recipes import LeadProfile, qualify_lead


async def qualify_inbound_lead(*, adapter: Any, model: str, lead_record: dict[str, Any]) -> dict[str, Any]:
    decision = await qualify_lead(
        adapter=adapter,
        model=model,
        lead=LeadProfile(
            company_name=lead_record["company_name"],
            employee_count=lead_record["employee_count"],
            industry=lead_record["industry"],
            inbound_message=lead_record["inbound_message"],
        ),
    )
    return {
        "segment": decision.segment,
        "budget_band": decision.budget_band,
        "urgency": decision.urgency,
        "qualified": decision.qualified,
        "next_action": decision.next_action,
    }
