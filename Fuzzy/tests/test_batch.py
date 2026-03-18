from __future__ import annotations

import asyncio

from fuzzy import BatchCall, FrameworkError, LLMAdapter, LLMOps, run_batch
import pytest


class RoutingAdapter(LLMAdapter):
    def __init__(self) -> None:
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        payload = request["messages"][0]["parts"][0]
        data = payload.get("data")
        text = payload.get("text")

        if isinstance(data, dict) and "value" in data:
            if data["value"] == 1:
                await asyncio.sleep(0.02)
                return {"raw_text": '{"result": true}', "provider_response_id": "resp-1"}
            if data["value"] == 2:
                return {"raw_text": '{"result": false}', "provider_response_id": "resp-2"}
            if data["value"] == 3:
                return {"raw_text": "not-json", "provider_response_id": "resp-3"}
            if data["value"] == 4:
                return {"raw_text": '{"result": true}', "provider_response_id": "resp-4"}
        if text == "gold":
            return {"raw_text": '{"label":"gold"}', "provider_response_id": "resp-5"}
        raise AssertionError(f"unexpected request {request!r}")


def test_run_batch_collects_results_in_input_order_and_traces():
    adapter = RoutingAdapter()

    report = asyncio.run(
        run_batch(
            [
                BatchCall(operation="eval_bool", name="slow", context={"value": 1}, expression="value is one"),
                BatchCall(operation="eval_bool", name="fast", context={"value": 2}, expression="value is two"),
            ],
            adapter=adapter,
            model="gpt-test",
            concurrency=2,
            return_traces=True,
        )
    )

    assert report.total_calls == 2
    assert report.completed_calls == 2
    assert report.succeeded_calls == 2
    assert report.failed_calls == 0
    assert [result.name for result in report.results] == ["slow", "fast"]
    assert [result.value for result in report.results] == [True, False]
    assert all(result.trace is not None for result in report.results)


def test_run_batch_keeps_per_call_failures_without_stopping():
    adapter = RoutingAdapter()

    report = asyncio.run(
        run_batch(
            [
                BatchCall(operation="eval_bool", name="bad", context={"value": 3}, expression="value is valid"),
                BatchCall(operation="classify", name="good", context="gold", labels=["gold", "silver"]),
            ],
            adapter=adapter,
            model="gpt-test",
            concurrency=2,
            return_traces=True,
        )
    )

    assert report.succeeded_calls == 1
    assert report.failed_calls == 1
    assert report.skipped_calls == 0
    assert report.results[0].success is False
    assert report.results[0].error.category == "validation_exhausted"
    assert report.results[0].trace is not None
    assert report.results[1].success is True
    assert report.results[1].value == "gold"


def test_run_batch_stop_on_error_marks_later_calls_as_skipped():
    adapter = RoutingAdapter()

    report = asyncio.run(
        run_batch(
            [
                BatchCall(operation="eval_bool", name="fails", context={"value": 3}, expression="value is valid"),
                BatchCall(operation="eval_bool", name="skipped", context={"value": 4}, expression="value is four"),
            ],
            adapter=adapter,
            model="gpt-test",
            concurrency=1,
            stop_on_error=True,
        )
    )

    assert report.completed_calls == 1
    assert report.failed_calls == 2
    assert report.skipped_calls == 1
    assert report.results[0].success is False
    assert report.results[1].skipped is True
    assert {request["messages"][0]["parts"][0]["data"]["value"] for request in adapter.requests} == {3}


def test_llmops_run_batch_uses_instance_defaults():
    adapter = RoutingAdapter()
    ops = LLMOps(adapter=adapter, model="gpt-test")

    report = asyncio.run(
        ops.run_batch(
            [
                BatchCall(operation="eval_bool", context={"value": 1}, expression="value is one"),
                BatchCall(operation="classify", context="gold", labels=["gold", "silver"]),
            ],
            concurrency=1,
        )
    )

    assert report.succeeded_calls == 2
    assert [result.value for result in report.results] == [True, "gold"]


def test_run_batch_reports_preflight_call_configuration_errors_without_hitting_provider():
    adapter = RoutingAdapter()

    report = asyncio.run(
        run_batch(
            [
                BatchCall(operation="classify", name="bad"),
                BatchCall(operation="eval_bool", name="good", context={"value": 2}, expression="value is two"),
            ],
            adapter=adapter,
            model="gpt-test",
            concurrency=2,
        )
    )

    assert report.failed_calls == 1
    assert report.succeeded_calls == 1
    assert report.results[0].success is False
    assert report.results[0].error.category == "invalid_configuration"
    assert report.results[1].success is True
    assert len(adapter.requests) == 1


def test_run_batch_accepts_per_call_model_when_batch_default_is_absent():
    adapter = RoutingAdapter()

    report = asyncio.run(
        run_batch(
            [
                BatchCall(
                    operation="eval_bool",
                    context={"value": 1},
                    expression="value is one",
                    model="gpt-per-call",
                )
            ],
            adapter=adapter,
            concurrency=1,
        )
    )

    assert report.succeeded_calls == 1
    assert report.results[0].value is True
    assert adapter.requests[0]["model"] == "gpt-per-call"


def test_run_batch_rejects_invalid_concurrency_before_execution():
    adapter = RoutingAdapter()

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            run_batch(
                [BatchCall(operation="eval_bool", context={"value": 1}, expression="value is one")],
                adapter=adapter,
                model="gpt-test",
                concurrency=0,
            )
        )

    assert exc_info.value.category == "invalid_configuration"
    assert adapter.requests == []


def test_run_batch_does_not_expose_success_traces_when_return_traces_is_false():
    adapter = RoutingAdapter()

    report = asyncio.run(
        run_batch(
            [BatchCall(operation="eval_bool", context={"value": 1}, expression="value is one")],
            adapter=adapter,
            model="gpt-test",
        )
    )

    assert report.results[0].success is True
    assert report.results[0].value is True
    assert report.results[0].trace is None
