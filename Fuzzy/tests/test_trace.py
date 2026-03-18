from __future__ import annotations

import asyncio
import json

import pytest

from fuzzy import Command, FrameworkError, LLMAdapter, classify, dispatch, eval_bool
from fuzzy.trace import TraceResult, save_trace, write_trace_html


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


def test_eval_bool_return_trace_records_retries_and_metadata():
    adapter = FakeAdapter(
        [
            {
                "raw_text": "not-json",
                "provider_response_id": "resp-1",
                "provider_metadata": {"total_tokens": 9},
            },
            {
                "raw_text": '{"result": true}',
                "provider_response_id": "resp-2",
                "provider_metadata": {"total_tokens": 11},
            },
        ]
    )

    traced = asyncio.run(
        eval_bool(
            adapter=adapter,
            model="gpt-test",
            context={"flag": True},
            expression="flag is true",
            return_trace=True,
        )
    )

    assert isinstance(traced, TraceResult)
    assert traced.value is True
    assert traced.trace.success is True
    assert traced.trace.attempt_count == 2
    assert traced.trace.attempts[0].validation_category == "malformed_json"
    assert traced.trace.attempts[1].provider_response_id == "resp-2"
    assert traced.trace.attempts[1].provider_metadata == {"total_tokens": 11}
    assert traced.trace.to_dict()["result"] == {"result": True}


def test_dispatch_trace_sink_receives_terminal_auto_execute_trace():
    adapter = FakeAdapter(['{"kind":"command","command":{"name":"approve","args":{}}}'])
    traces = []

    result = asyncio.run(
        dispatch(
            adapter=adapter,
            model="gpt-test",
            context={"request": "ok"},
            commands=[
                Command(
                    name="approve",
                    input_schema={"type": "object", "additionalProperties": False},
                    executor=lambda args: {"status": "approved"},
                )
            ],
            auto_execute=True,
            trace_sink=traces.append,
        )
    )

    assert result == {
        "decision": {"kind": "command", "command": {"name": "approve", "args": {}}},
        "result": {"status": "approved"},
    }
    assert len(traces) == 1
    assert traces[0].result == result
    assert traces[0].success is True


def test_validation_error_exposes_trace_and_trace_helpers_round_trip(tmp_path):
    adapter = FakeAdapter(['{"label":"gamma"}'])

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            classify(
                adapter=adapter,
                model="gpt-test",
                context={"topic": "x"},
                labels=["alpha", "beta"],
                max_attempts=1,
                trace_sink=lambda trace: None,
            )
        )

    trace = exc_info.value.trace
    assert trace is not None
    assert trace.success is False
    assert trace.final_validation_category == "choice_invalid"

    json_path = save_trace(trace, tmp_path, redact=["$.messages[0].parts[0].data.topic"])
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["messages"][0]["parts"][0]["data"]["topic"] == "[REDACTED]"

    html_path = write_trace_html(json_path, tmp_path / "trace.html")
    html_output = html_path.read_text(encoding="utf-8")
    assert "Fuzzy Trace" in html_output
    assert "choice_invalid" in html_output


def test_trace_sink_must_be_callable():
    adapter = FakeAdapter([])

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            eval_bool(
                adapter=adapter,
                model="gpt-test",
                context={"flag": True},
                expression="flag is true",
                trace_sink="bad",
            )
        )

    assert exc_info.value.category == "invalid_configuration"
    assert exc_info.value.message == "trace_sink must be callable or None"
