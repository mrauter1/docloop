from __future__ import annotations

import asyncio
import threading
import urllib.request

import pytest

from fuzzy import (
    ApprovalDecision,
    AnthropicAdapter,
    AzureOpenAIAdapter,
    BatchCall,
    BatchPolicy,
    Command,
    CommandPolicy,
    FallbackModel,
    FrameworkError,
    GeminiAdapter,
    LLMAdapter,
    LLMOps,
    LocalOpenAIAdapter,
    ModelPricing,
    RuntimeBudget,
    dispatch,
    drop,
    eval_bool,
    find_model_pricing,
    get_model_pricing,
    get_pricing_catalog,
    list_pricing_models,
    pricing_for_models,
    run_batch,
)
from fuzzy.errors import ProviderError


class FallbackAdapter(LLMAdapter):
    def __init__(self) -> None:
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        if request["model"] == "primary":
            raise ProviderError("rate_limit", "slow down")
        return {
            "raw_text": '{"result": true}',
            "provider_response_id": "resp-fallback",
            "provider_metadata": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
        }


class ValidationAdapter(LLMAdapter):
    def __init__(self) -> None:
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        if len(self.requests) == 1:
            return {"raw_text": "not-json", "provider_response_id": "resp-1"}
        return {"raw_text": '{"result": true}', "provider_response_id": "resp-2"}


class DispatchAdapter(LLMAdapter):
    def __init__(self, raw_text: str) -> None:
        self.raw_text = raw_text

    async def complete(self, request):
        return {"raw_text": self.raw_text, "provider_response_id": "dispatch-1"}


def test_eval_bool_uses_fallback_model_on_provider_error_and_records_attempt_models():
    adapter = FallbackAdapter()

    traced = asyncio.run(
        eval_bool(
            adapter=adapter,
            model="primary",
            context={"x": 1},
            expression="x == 1",
            fallback_models=[FallbackModel(model="backup")],
            max_attempts=2,
            return_trace=True,
        )
    )

    assert traced.value is True
    assert [request["model"] for request in adapter.requests] == ["primary", "backup"]
    assert [attempt.model for attempt in traced.trace.attempts] == ["primary", "backup"]


def test_eval_bool_does_not_use_fallback_model_for_validation_retries():
    adapter = ValidationAdapter()

    traced = asyncio.run(
        eval_bool(
            adapter=adapter,
            model="primary",
            context={"x": 1},
            expression="x == 1",
            fallback_models=[FallbackModel(model="backup")],
            max_attempts=2,
            return_trace=True,
        )
    )

    assert traced.value is True
    assert [request["model"] for request in adapter.requests] == ["primary", "primary"]


def test_dispatch_simulator_mode_skips_executor_and_emits_audit_record():
    executed = []
    audit_records = []
    adapter = DispatchAdapter('{"kind":"command","command":{"name":"approve","args":{"note":"ok"}}}')

    result = asyncio.run(
        dispatch(
            adapter=adapter,
            model="gpt-test",
            context={"request": "ok"},
            commands=[
                Command(
                    name="approve",
                    input_schema={
                        "type": "object",
                        "properties": {"note": {"type": "string"}},
                        "required": ["note"],
                        "additionalProperties": False,
                    },
                    executor=lambda args: executed.append(args) or {"status": "approved"},
                )
            ],
            auto_execute=True,
            command_policy=CommandPolicy(simulator_mode=True, audit_sink=audit_records.append),
        )
    )

    assert executed == []
    assert result["decision"]["command"]["name"] == "approve"
    assert result["result"]["simulated"] is True
    assert audit_records[0].simulated is True
    assert audit_records[0].executed is False


def test_dispatch_allow_list_rejects_blocked_command_before_approval_or_execution():
    executed = []
    approval_calls = []
    audit_records = []
    adapter = DispatchAdapter('{"kind":"command","command":{"name":"approve","args":{}}}')

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            dispatch(
                adapter=adapter,
                model="gpt-test",
                context={"request": "ok"},
                commands=[
                    Command(
                        name="approve",
                        input_schema={"type": "object", "additionalProperties": False},
                        executor=lambda args: executed.append(args) or {"status": "approved"},
                    )
                ],
                auto_execute=True,
                command_policy=CommandPolicy(
                    allow_commands=("different_command",),
                    approval_hook=lambda decision, context: approval_calls.append(decision) or ApprovalDecision(True),
                    audit_sink=audit_records.append,
                ),
            )
        )

    assert exc_info.value.category == "command_execution"
    assert "allow-list" in exc_info.value.message
    assert executed == []
    assert approval_calls == []
    assert audit_records[0].approved is False
    assert audit_records[0].executed is False


def test_dispatch_deny_list_rejects_command_before_execution():
    executed = []
    adapter = DispatchAdapter('{"kind":"command","command":{"name":"approve","args":{}}}')

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            dispatch(
                adapter=adapter,
                model="gpt-test",
                context={"request": "ok"},
                commands=[
                    Command(
                        name="approve",
                        input_schema={"type": "object", "additionalProperties": False},
                        executor=lambda args: executed.append(args) or {"status": "approved"},
                    )
                ],
                auto_execute=True,
                command_policy=CommandPolicy(deny_commands=("approve",)),
            )
        )

    assert exc_info.value.category == "command_execution"
    assert "deny-list" in exc_info.value.message
    assert executed == []


def test_dispatch_denied_by_approval_hook_raises_and_audits():
    audit_records = []
    adapter = DispatchAdapter('{"kind":"command","command":{"name":"approve","args":{}}}')

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
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
                command_policy=CommandPolicy(
                    approval_hook=lambda decision, context: ApprovalDecision(False, "manual review required"),
                    audit_sink=audit_records.append,
                ),
            )
        )

    assert exc_info.value.category == "command_execution"
    assert "manual review required" in exc_info.value.message
    assert audit_records[0].approved is False
    assert audit_records[0].executed is False


def test_dispatch_timeout_raises_command_execution():
    adapter = DispatchAdapter('{"kind":"command","command":{"name":"approve","args":{}}}')

    async def slow_executor(args):
        await asyncio.sleep(0.05)
        return {"status": "approved"}

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            dispatch(
                adapter=adapter,
                model="gpt-test",
                context={"request": "ok"},
                commands=[
                    Command(
                        name="approve",
                        input_schema={"type": "object", "additionalProperties": False},
                        executor=slow_executor,
                    )
                ],
                auto_execute=True,
                command_policy=CommandPolicy(timeout_seconds=0.01),
            )
        )

    assert exc_info.value.category == "command_execution"
    assert "timed out" in exc_info.value.message


def test_dispatch_async_timeout_cancels_executor_before_side_effect():
    adapter = DispatchAdapter('{"kind":"command","command":{"name":"approve","args":{}}}')
    state = {"executed": False, "cancelled": False}

    async def cancellable_executor(args):
        try:
            await asyncio.sleep(0.05)
            state["executed"] = True
            return {"status": "approved"}
        except asyncio.CancelledError:
            state["cancelled"] = True
            raise

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            dispatch(
                adapter=adapter,
                model="gpt-test",
                context={"request": "ok"},
                commands=[
                    Command(
                        name="approve",
                        input_schema={"type": "object", "additionalProperties": False},
                        executor=cancellable_executor,
                    )
                ],
                auto_execute=True,
                command_policy=CommandPolicy(timeout_seconds=0.01),
            )
        )

    assert exc_info.value.category == "command_execution"
    assert state == {"executed": False, "cancelled": True}


def test_dispatch_rejects_timeout_for_sync_executor_before_execution():
    adapter = DispatchAdapter('{"kind":"command","command":{"name":"approve","args":{}}}')
    executed = []

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            dispatch(
                adapter=adapter,
                model="gpt-test",
                context={"request": "ok"},
                commands=[
                    Command(
                        name="approve",
                        input_schema={"type": "object", "additionalProperties": False},
                        executor=lambda args: executed.append(True) or {"status": "approved"},
                    )
                ],
                auto_execute=True,
                command_policy=CommandPolicy(timeout_seconds=0.01),
            )
        )

    assert executed == []
    assert exc_info.value.category == "command_execution"
    assert "requires an async executor" in exc_info.value.message


def test_dispatch_sync_executor_stays_on_current_thread_without_timeout():
    adapter = DispatchAdapter('{"kind":"command","command":{"name":"approve","args":{}}}')
    caller_thread = threading.get_ident()
    executor_threads = []

    result = asyncio.run(
        dispatch(
            adapter=adapter,
            model="gpt-test",
            context={"request": "ok"},
            commands=[
                Command(
                    name="approve",
                    input_schema={"type": "object", "additionalProperties": False},
                    executor=lambda args: executor_threads.append(threading.get_ident()) or {"status": "approved"},
                )
            ],
            auto_execute=True,
        )
    )

    assert result["result"] == {"status": "approved"}
    assert executor_threads == [caller_thread]


def test_run_batch_reports_cost_and_stops_after_budget_exhaustion():
    adapter = DispatchAdapter('{"result": true}')

    report = asyncio.run(
        run_batch(
            [
                BatchCall(operation="eval_bool", context={"x": 1}, expression="x == 1"),
                BatchCall(operation="eval_bool", context={"x": 2}, expression="x == 2"),
            ],
            adapter=type(
                "BudgetAdapter",
                (LLMAdapter,),
                {
                    "__init__": lambda self: setattr(self, "count", 0),
                    "complete": lambda self, request: _budget_complete(self, request),
                },
            )(),
            model="gpt-test",
            concurrency=1,
            batch_policy=BatchPolicy(budget=RuntimeBudget(max_requests=1)),
            pricing=[ModelPricing(model="gpt-test", input_cost_per_1k_tokens=0.5, output_cost_per_1k_tokens=1.0)],
        )
    )

    assert report.budget_exhausted is True
    assert report.results[1].skipped is True
    assert report.cost is not None
    assert report.cost.request_count == 1
    assert report.cost.total_tokens == 6
    assert report.cost.estimated_cost == pytest.approx((4 / 1000.0) * 0.5 + (2 / 1000.0) * 1.0)


async def _budget_complete(self, request):
    self.count += 1
    return {
        "raw_text": '{"result": true}',
        "provider_response_id": f"resp-{self.count}",
        "provider_metadata": {"input_tokens": 4, "output_tokens": 2, "total_tokens": 6},
    }


def test_azure_openai_adapter_builds_response_payload_without_sdk_calls():
    adapter = AzureOpenAIAdapter(api_key="secret", endpoint="https://example.openai.azure.com")
    captured = {}

    def fake_post_json(payload):
        captured["payload"] = payload
        return {"output_text": '{"result": true}', "id": "azure-1", "usage": {"total_tokens": 7}}

    adapter._post_json = fake_post_json  # type: ignore[method-assign]

    response = asyncio.run(
        adapter.complete(
            {
                "operation": "eval_bool",
                "model": "gpt-4o-mini",
                "instructions": "Return JSON.",
                "messages": [{"role": "user", "parts": [{"type": "json", "data": {"x": 1}}]}],
                "output_schema": {
                    "type": "object",
                    "properties": {"result": {"type": "boolean"}},
                    "required": ["result"],
                    "additionalProperties": False,
                },
                "attempt": 1,
            }
        )
    )

    assert "api-version=2024-10-21" in adapter.base_url
    assert captured["payload"]["model"] == "gpt-4o-mini"
    assert response["provider_response_id"] == "azure-1"
    assert response["provider_metadata"] == {"total_tokens": 7}


def test_llmops_from_provider_supports_azure_openai():
    ops = LLMOps.from_provider(
        "azure_openai",
        model="gpt-test",
        api_key="secret",
        endpoint="https://example.openai.azure.com",
    )

    assert isinstance(ops.adapter, AzureOpenAIAdapter)


def test_llmops_from_provider_supports_anthropic():
    ops = LLMOps.from_provider(
        "anthropic",
        model="claude-3-5-haiku-latest",
        api_key="secret",
    )

    assert isinstance(ops.adapter, AnthropicAdapter)


def test_llmops_from_provider_supports_gemini():
    ops = LLMOps.from_provider(
        "gemini",
        model="gemini-2.0-flash",
        api_key="secret",
    )

    assert isinstance(ops.adapter, GeminiAdapter)


def test_llmops_from_provider_supports_local_openai_without_api_key():
    ops = LLMOps.from_provider(
        "local_openai",
        model="local-model",
        base_url="http://localhost:11434/v1/responses",
    )

    assert isinstance(ops.adapter, LocalOpenAIAdapter)


def test_local_openai_adapter_omits_authorization_header_when_api_key_is_missing(monkeypatch):
    adapter = LocalOpenAIAdapter(base_url="http://localhost:11434/v1/responses")
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"output_text":"{\\"result\\": true}","id":"local-1"}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = {key.lower(): value for key, value in request.header_items()}
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    response = asyncio.run(
        adapter.complete(
            {
                "operation": "eval_bool",
                "model": "local-model",
                "instructions": "Return JSON.",
                "messages": [{"role": "user", "parts": [{"type": "text", "text": "hi"}]}],
                "output_schema": {"type": "object"},
                "attempt": 1,
            }
        )
    )

    assert captured["url"] == "http://localhost:11434/v1/responses"
    assert "authorization" not in captured["headers"]
    assert captured["headers"]["content-type"] == "application/json"
    assert response["provider_response_id"] == "local-1"


def test_local_openai_adapter_includes_authorization_header_when_api_key_is_set(monkeypatch):
    adapter = LocalOpenAIAdapter(base_url="http://localhost:11434/v1/responses", api_key="secret")
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"output_text":"{\\"result\\": true}","id":"local-2"}'

    def fake_urlopen(request, timeout):
        captured["headers"] = {key.lower(): value for key, value in request.header_items()}
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    asyncio.run(
        adapter.complete(
            {
                "operation": "eval_bool",
                "model": "local-model",
                "instructions": "Return JSON.",
                "messages": [{"role": "user", "parts": [{"type": "text", "text": "hi"}]}],
                "output_schema": {"type": "object"},
                "attempt": 1,
            }
        )
    )

    assert captured["headers"]["authorization"] == "Bearer secret"


def test_pricing_catalog_helpers_are_explicit_and_strict():
    catalog = get_pricing_catalog()

    assert catalog.name == "default"
    assert "gpt-4o-mini" in list_pricing_models()
    assert find_model_pricing("gpt-4o-mini") == get_model_pricing("gpt-4o-mini")
    assert [item.model for item in pricing_for_models(["gpt-4o-mini", "gemini-2.0-flash"])] == [
        "gpt-4o-mini",
        "gemini-2.0-flash",
    ]

    with pytest.raises(KeyError):
        get_model_pricing("missing-model")

    assert find_model_pricing("missing-model") is None


def test_drop_remains_publicly_exported():
    assert drop({"field": object(), "items": [object(), "ok"]}) == {"items": ["ok"]}
