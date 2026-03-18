from __future__ import annotations

from ..evals import EvalCase, EvalSuite

SUPPORT_TRIAGE_EVAL_SUITE = EvalSuite(
    name="support-triage",
    task="extraction",
    cases=(
        EvalCase(
            name="billing-refund",
            context={
                "ticket": {
                    "subject": "Charged twice",
                    "body": "I was billed twice today and need a refund.",
                    "channel": "email",
                    "account_id": "acct-1",
                },
                "customer": {
                    "account_tier": "enterprise",
                    "previous_refunds": 0,
                    "has_open_invoice": True,
                    "contract_value_band": "large",
                },
            },
            expected={"category": "billing", "urgency": "high", "refund_candidate": True},
            tags=("recipe", "support"),
        ),
    ),
)

LEAD_QUALIFICATION_EVAL_SUITE = EvalSuite(
    name="lead-qualification",
    task="extraction",
    cases=(
        EvalCase(
            name="enterprise-hot-lead",
            context={
                "lead": {
                    "company_name": "Northwind",
                    "employee_count": 1200,
                    "industry": "Fintech",
                    "inbound_message": "We need procurement review this month for a 500-seat rollout.",
                }
            },
            expected={"segment": "enterprise", "budget_band": "high", "urgency": "high", "qualified": True},
            tags=("recipe", "sales"),
        ),
    ),
)

APPROVAL_ROUTING_EVAL_SUITE = EvalSuite(
    name="approval-routing",
    task="extraction",
    cases=(
        EvalCase(
            name="sensitive-system",
            context={
                "request": {
                    "requester_role": "contractor",
                    "requested_system": "production-analytics",
                    "justification": "Need direct customer export access.",
                    "estimated_impact": "high",
                }
            },
            expected={"risk_tier": "high", "route": "security_review", "needs_manual_review": True},
            tags=("recipe", "approval"),
        ),
    ),
)

DOCUMENT_COMPLETENESS_EVAL_SUITE = EvalSuite(
    name="document-completeness",
    task="extraction",
    cases=(
        EvalCase(
            name="missing-proof-of-address",
            context={
                "package": {
                    "applicant_type": "business",
                    "documents": [
                        {"type": "certificate_of_incorporation", "status": "present"},
                        {"type": "government_id", "status": "present"},
                    ],
                    "submitted_fields": {
                        "legal_name": "Northwind Trading",
                        "registration_number": "NW-42",
                    },
                    "jurisdiction": "BR",
                }
            },
            expected={
                "is_complete": False,
                "missing_items": ["proof_of_address"],
                "risk_flags": [],
            },
            tags=("recipe", "documents"),
        ),
    ),
)


def get_recipe_eval_suites() -> dict[str, EvalSuite]:
    return {
        "support_triage": SUPPORT_TRIAGE_EVAL_SUITE,
        "lead_qualification": LEAD_QUALIFICATION_EVAL_SUITE,
        "approval_routing": APPROVAL_ROUTING_EVAL_SUITE,
        "document_completeness": DOCUMENT_COMPLETENESS_EVAL_SUITE,
    }
