from __future__ import annotations

import asyncio
import json

import pytest

from fuzzy import LLMAdapter
from fuzzy.evals import (
    EvalCase,
    EvalVariant,
    assert_eval_thresholds,
    load_eval_suite,
    run_classification_eval,
    run_eval_matrix,
    run_extraction_eval,
    write_eval_report,
)


class FakeAdapter(LLMAdapter):
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("no fake response queued")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, dict):
            return response
        return {"raw_text": response, "provider_response_id": "fake-response"}


def test_run_classification_eval_and_thresholds():
    adapter = FakeAdapter(
        [
            '{"label":"keep"}',
            "not-json",
            '{"label":"drop"}',
        ]
    )

    report = asyncio.run(
        run_classification_eval(
            adapter=adapter,
            model="gpt-test",
            labels=["keep", "drop"],
            suite_name="triage",
            cases=[
                EvalCase(name="case-1", context={"value": 1}, expected="keep"),
                EvalCase(name="case-2", context={"value": 2}, expected="drop"),
            ],
        )
    )

    assert report.summary.total_cases == 2
    assert report.summary.pass_rate == 1.0
    assert report.summary.retry_rate == 0.5
    assert report.summary.accuracy == 1.0
    assert report.summary.confusion_matrix == {"keep": {"keep": 1}, "drop": {"drop": 1}}
    assert report.case_results[1].trace is not None
    assert report.case_results[1].trace.attempt_count == 2
    assert_eval_thresholds(report, min_pass_rate=1.0, max_retry_rate=0.5, min_accuracy=1.0)


def test_run_extraction_eval_and_report_exports(tmp_path):
    adapter = FakeAdapter(
        [
            '{"name": 7}',
            '{"name":"Ada"}',
        ]
    )

    report = asyncio.run(
        run_extraction_eval(
            adapter=adapter,
            model="gpt-test",
            schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            suite_name="extractors",
            max_attempts=1,
            cases=[
                EvalCase(name="bad", context={"person": 7}, expected={"name": "Ada"}),
                EvalCase(name="good", context={"person": "Ada"}, expected={"name": "Ada"}),
            ],
        )
    )

    assert report.summary.total_cases == 2
    assert report.summary.validation_exhausted_count == 1
    assert report.summary.schema_validity_rate == 0.5

    json_path = write_eval_report(report, tmp_path / "report.json")
    markdown_path = write_eval_report(report, tmp_path / "report.md")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["summary"]["validation_exhausted_count"] == 1
    assert "Eval Report: extractors" in markdown_path.read_text(encoding="utf-8")

    with pytest.raises(AssertionError):
        assert_eval_thresholds(report, min_schema_validity_rate=1.0, max_validation_exhausted_count=0)


def test_load_eval_suite_and_run_eval_matrix(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "name": "classify-suite",
                "task": "classification",
                "cases": [
                    {
                        "name": "one",
                        "context": {"value": 1},
                        "expected": "keep",
                        "tags": ["smoke"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    suite = load_eval_suite(suite_path)
    assert suite.name == "classify-suite"
    assert suite.cases[0].tags == ("smoke",)

    variants = [
        EvalVariant(name="model-a", model="model-a"),
        EvalVariant(name="model-b", model="model-b"),
    ]

    async def runner(variant: EvalVariant):
        adapter = FakeAdapter(['{"label":"keep"}'])
        return await run_classification_eval(
            adapter=adapter,
            model=variant.model or "fallback",
            labels=["keep", "drop"],
            suite_name=suite.name,
            cases=suite.cases,
        )

    reports = asyncio.run(run_eval_matrix(variants=variants, runner=runner))

    assert set(reports) == {"model-a", "model-b"}
    assert reports["model-a"].variant_name == "model-a"
    assert reports["model-b"].summary.pass_rate == 1.0
