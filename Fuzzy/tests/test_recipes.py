from __future__ import annotations

import asyncio

import pytest

from fuzzy import FrameworkError, LLMAdapter
from fuzzy.evals import run_extraction_eval
from fuzzy.recipes import (
    APPROVAL_ROUTING_EVAL_SUITE,
    APPROVAL_ROUTING_SCHEMA,
    DOCUMENT_COMPLETENESS_EVAL_SUITE,
    DOCUMENT_COMPLETENESS_SCHEMA,
    LEAD_QUALIFICATION_EVAL_SUITE,
    LEAD_QUALIFICATION_SCHEMA,
    SUPPORT_TRIAGE_EVAL_SUITE,
    SUPPORT_TRIAGE_SCHEMA,
    ApprovalRequest,
    DocumentPackage,
    LeadProfile,
    RecipeRun,
    SupportCustomer,
    SupportTicket,
    assess_document_completeness,
    qualify_lead,
    route_approval,
    triage_support_request,
)
from examples.queue_document_worker import process_document_job


class FakeAdapter(LLMAdapter):
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, dict):
            return response
        return {"raw_text": response, "provider_response_id": f"resp-{len(self.requests)}"}


def test_support_triage_returns_typed_decision_and_recipe_traces():
    adapter = FakeAdapter(
        [
            '{"category":"billing","urgency":"high","refund_candidate":true}',
            '{"kind":"command","command":{"name":"open_refund_review_case","args":{"priority":"high"}}}',
        ]
    )

    decision = asyncio.run(
        triage_support_request(
            adapter=adapter,
            model="gpt-test",
            ticket=SupportTicket(subject="Refund", body="I was billed twice."),
            customer=SupportCustomer(account_tier="enterprise", has_open_invoice=True),
            return_trace=True,
        )
    )

    assert isinstance(decision, RecipeRun)
    assert decision.value.category == "billing"
    assert decision.value.next_action["command"]["name"] == "open_refund_review_case"
    assert [step.step for step in decision.traces] == ["triage", "next_action"]


def test_lead_qualification_supports_message_evidence():
    source_messages = [
        {"role": "user", "parts": [{"type": "text", "text": "1200 employee fintech buyer"}]},
        {
            "role": "user",
            "parts": [{"type": "json", "data": {"timeline": "this month", "seats": 500}}],
        },
    ]
    adapter = FakeAdapter(
        [
            '{"segment":"enterprise","budget_band":"high","urgency":"high","qualified":true}',
            '{"kind":"command","command":{"name":"assign_account_executive","args":{"priority":"expedited"}}}',
        ]
    )

    decision = asyncio.run(
        qualify_lead(
            adapter=adapter,
            model="gpt-test",
            messages=source_messages,
        )
    )

    assert decision.segment == "enterprise"
    assert source_messages == [
        {"role": "user", "parts": [{"type": "text", "text": "1200 employee fintech buyer"}]},
        {
            "role": "user",
            "parts": [{"type": "json", "data": {"timeline": "this month", "seats": 500}}],
        },
    ]
    assert adapter.requests[0]["messages"][1]["parts"][0]["data"]["seats"] == 500
    assert adapter.requests[1]["messages"][:2] == source_messages
    assert adapter.requests[1]["messages"][2]["parts"][0]["data"]["qualification"] == {
        "segment": "enterprise",
        "budget_band": "high",
        "urgency": "high",
        "qualified": True,
    }


def test_approval_router_bundles_manual_review_path():
    adapter = FakeAdapter(
        [
            '{"risk_tier":"high","route":"security_review","needs_manual_review":true}',
            '{"kind":"command","command":{"name":"route_to_security","args":{"reason":"Sensitive system access"}}}',
        ]
    )

    decision = asyncio.run(
        route_approval(
            adapter=adapter,
            model="gpt-test",
            request=ApprovalRequest(
                requester_role="contractor",
                requested_system="production-analytics",
                justification="Need export access",
                estimated_impact="high",
            ),
        )
    )

    assert decision.risk_tier == "high"
    assert decision.needs_manual_review is True
    assert decision.next_action["command"]["name"] == "route_to_security"


def test_approval_router_preserves_structured_context_in_dispatch_step():
    adapter = FakeAdapter(
        [
            '{"risk_tier":"medium","route":"manager_review","needs_manual_review":true}',
            '{"kind":"command","command":{"name":"route_to_manager","args":{"reason":"Needs manager sign-off"}}}',
        ]
    )

    asyncio.run(
        route_approval(
            adapter=adapter,
            model="gpt-test",
            request=ApprovalRequest(
                requester_role="employee",
                requested_system="crm",
                justification="Need account updates",
                estimated_impact="medium",
            ),
        )
    )

    dispatch_payload = adapter.requests[1]["messages"][0]["parts"][0]["data"]
    assert dispatch_payload["request"]["requested_system"] == "crm"
    assert dispatch_payload["assessment"] == {
        "risk_tier": "medium",
        "route": "manager_review",
        "needs_manual_review": True,
    }


def test_document_completeness_supports_message_evidence_and_recipe_traces():
    source_messages = [
        {"role": "user", "parts": [{"type": "text", "text": "Business onboarding package for review."}]},
        {
            "role": "user",
            "parts": [
                {
                    "type": "json",
                    "data": {
                        "documents": [
                            {"type": "certificate_of_incorporation", "status": "present"},
                            {"type": "government_id", "status": "present"},
                        ],
                        "submitted_fields": {"legal_name": "Northwind Trading"},
                        "jurisdiction": "BR",
                    },
                }
            ],
        },
    ]
    adapter = FakeAdapter(
        [
            '{"is_complete":false,"missing_items":["proof_of_address"],"risk_flags":[]}',
            '{"kind":"command","command":{"name":"request_missing_documents","args":{"items":["proof_of_address"]}}}',
        ]
    )

    decision = asyncio.run(
        assess_document_completeness(
            adapter=adapter,
            model="gpt-test",
            messages=source_messages,
            return_trace=True,
        )
    )

    assert isinstance(decision, RecipeRun)
    assert decision.value.is_complete is False
    assert decision.value.missing_items == ["proof_of_address"]
    assert decision.value.next_action["command"]["name"] == "request_missing_documents"
    assert [step.step for step in decision.traces] == ["assessment", "next_action"]
    assert adapter.requests[1]["messages"][:2] == source_messages
    assert adapter.requests[1]["messages"][2]["parts"][0]["data"]["assessment"] == {
        "is_complete": False,
        "missing_items": ["proof_of_address"],
        "risk_flags": [],
    }


def test_document_completeness_supports_structured_context():
    adapter = FakeAdapter(
        [
            '{"is_complete":true,"missing_items":[],"risk_flags":["high_risk_jurisdiction"]}',
            '{"kind":"command","command":{"name":"escalate_risk_review","args":{"reason":"high_risk_jurisdiction"}}}',
        ]
    )

    decision = asyncio.run(
        assess_document_completeness(
            adapter=adapter,
            model="gpt-test",
            package=DocumentPackage(
                applicant_type="business",
                documents=[{"type": "certificate_of_incorporation", "status": "present"}],
                submitted_fields={"legal_name": "Northwind Trading"},
                jurisdiction="KY",
            ),
        )
    )

    assert decision.is_complete is True
    assert decision.risk_flags == ["high_risk_jurisdiction"]
    assert decision.next_action["command"]["name"] == "escalate_risk_review"


def test_document_completeness_stops_before_dispatch_when_extraction_fails():
    adapter = FakeAdapter(["not-json"])

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            assess_document_completeness(
                adapter=adapter,
                model="gpt-test",
                package=DocumentPackage(
                    applicant_type="business",
                    documents=[],
                    submitted_fields={},
                    jurisdiction="BR",
                ),
                max_attempts=1,
            )
        )

    assert exc_info.value.category == "validation_exhausted"
    assert len(adapter.requests) == 1


def test_document_completeness_requires_package_when_messages_are_not_supplied():
    adapter = FakeAdapter([])

    with pytest.raises(ValueError) as exc_info:
        asyncio.run(
            assess_document_completeness(
                adapter=adapter,
                model="gpt-test",
            )
        )

    assert str(exc_info.value) == "package is required when messages are not supplied"
    assert adapter.requests == []


def test_support_triage_stops_before_dispatch_when_extraction_fails():
    adapter = FakeAdapter(["not-json"])

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            triage_support_request(
                adapter=adapter,
                model="gpt-test",
                ticket=SupportTicket(subject="Refund", body="I was billed twice."),
                customer=SupportCustomer(account_tier="enterprise", has_open_invoice=True),
                max_attempts=1,
            )
        )

    assert exc_info.value.category == "validation_exhausted"
    assert len(adapter.requests) == 1


def test_recipe_eval_fixtures_run_against_exported_schemas():
    adapter = FakeAdapter(
        [
            '{"category":"billing","urgency":"high","refund_candidate":true}',
            '{"segment":"enterprise","budget_band":"high","urgency":"high","qualified":true}',
            '{"risk_tier":"high","route":"security_review","needs_manual_review":true}',
            '{"is_complete":false,"missing_items":["proof_of_address"],"risk_flags":[]}',
        ]
    )

    support_report = asyncio.run(
        run_extraction_eval(
            adapter=adapter,
            model="gpt-test",
            schema=SUPPORT_TRIAGE_SCHEMA,
            suite_name=SUPPORT_TRIAGE_EVAL_SUITE.name,
            cases=SUPPORT_TRIAGE_EVAL_SUITE.cases,
        )
    )
    lead_report = asyncio.run(
        run_extraction_eval(
            adapter=adapter,
            model="gpt-test",
            schema=LEAD_QUALIFICATION_SCHEMA,
            suite_name=LEAD_QUALIFICATION_EVAL_SUITE.name,
            cases=LEAD_QUALIFICATION_EVAL_SUITE.cases,
        )
    )
    approval_report = asyncio.run(
        run_extraction_eval(
            adapter=adapter,
            model="gpt-test",
            schema=APPROVAL_ROUTING_SCHEMA,
            suite_name=APPROVAL_ROUTING_EVAL_SUITE.name,
            cases=APPROVAL_ROUTING_EVAL_SUITE.cases,
        )
    )
    document_report = asyncio.run(
        run_extraction_eval(
            adapter=adapter,
            model="gpt-test",
            schema=DOCUMENT_COMPLETENESS_SCHEMA,
            suite_name=DOCUMENT_COMPLETENESS_EVAL_SUITE.name,
            cases=DOCUMENT_COMPLETENESS_EVAL_SUITE.cases,
        )
    )

    assert support_report.summary.pass_rate == 1.0
    assert lead_report.summary.pass_rate == 1.0
    assert approval_report.summary.pass_rate == 1.0
    assert document_report.summary.pass_rate == 1.0


def test_queue_document_worker_processes_mixed_evidence_job():
    adapter = FakeAdapter(
        [
            '{"is_complete":false,"missing_items":["proof_of_address"],"risk_flags":[]}',
            '{"kind":"command","command":{"name":"request_missing_documents","args":{"items":["proof_of_address"]}}}',
        ]
    )

    result = asyncio.run(
        process_document_job(
            adapter=adapter,
            model="gpt-test",
            job={
                "job_id": "job-7",
                "job_type": "business onboarding",
                "package": {
                    "documents": [
                        {"type": "certificate_of_incorporation", "status": "present"},
                        {"type": "government_id", "status": "present"},
                    ],
                    "submitted_fields": {"legal_name": "Northwind Trading"},
                    "jurisdiction": "BR",
                },
            },
        )
    )

    assert result["job_id"] == "job-7"
    assert result["missing_items"] == ["proof_of_address"]
    assert result["next_action"]["command"]["name"] == "request_missing_documents"
    assert adapter.requests[0]["messages"][0]["parts"][0]["text"] == (
        "Review the submitted intake package for business onboarding."
    )
