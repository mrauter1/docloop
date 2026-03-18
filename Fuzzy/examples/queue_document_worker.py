from __future__ import annotations

from typing import Any

from fuzzy.recipes import assess_document_completeness


async def process_document_job(*, adapter: Any, model: str, job: dict[str, Any]) -> dict[str, Any]:
    messages = [
        {
            "role": "user",
            "parts": [
                {
                    "type": "text",
                    "text": f"Review the submitted intake package for {job['job_type']}.",
                }
            ],
        },
        {
            "role": "user",
            "parts": [
                {
                    "type": "json",
                    "data": job["package"],
                }
            ],
        },
    ]

    decision = await assess_document_completeness(
        adapter=adapter,
        model=model,
        messages=messages,
    )
    return {
        "job_id": job["job_id"],
        "is_complete": decision.is_complete,
        "missing_items": decision.missing_items,
        "risk_flags": decision.risk_flags,
        "next_action": decision.next_action,
    }
