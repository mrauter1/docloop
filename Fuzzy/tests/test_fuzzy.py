from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fuzzy import Command, FrameworkError, LLMAdapter, LLMOps, classify, dispatch, drop, eval_bool, extract
from fuzzy.adapters import OpenAIAdapter, OpenRouterAdapter, _http_error_category
from fuzzy.errors import ProviderError


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
        return {"raw_text": response, "provider_response_id": "fake-response"}


class EnvelopeAdapter(LLMAdapter):
    def __init__(self, response):
        self.response = response
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        return self.response


def test_eval_bool_retries_malformed_json_then_succeeds():
    adapter = FakeAdapter(["not-json", '{"result": true}'])

    value = asyncio.run(
        eval_bool(
            adapter=adapter,
            model="gpt-test",
            context={"answer": 42},
            expression="answer equals 42",
        )
    )

    assert value is True
    assert len(adapter.requests) == 2
    assert "Previous attempt failed validation (malformed_json)" in adapter.requests[1]["instructions"]
    assert adapter.requests[0]["context_json"] == '{"context":{"answer":42}}'


def test_classify_exhausts_choice_validation():
    adapter = FakeAdapter(['{"label":"gamma"}', '{"label":"gamma"}'])

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            classify(
                adapter=adapter,
                model="gpt-test",
                context={"topic": "x"},
                labels=["alpha", "beta"],
            )
        )

    exc = exc_info.value
    assert exc.category == "validation_exhausted"
    assert exc.final_validation_category == "choice_invalid"
    assert exc.attempt_count == 2


def test_extract_returns_model_instance():
    adapter = FakeAdapter(['{"name":"Ada","age":31}'])

    class Person:
        def __init__(self, name, age):
            self.name = name
            self.age = age

        @classmethod
        def model_json_schema(cls):
            return {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer", "minimum": 0},
                },
                "required": ["name", "age"],
                "additionalProperties": False,
            }

        @classmethod
        def model_validate(cls, payload):
            return cls(name=payload["name"], age=payload["age"])

    value = asyncio.run(
        extract(
            adapter=adapter,
            model="gpt-test",
            context={"person": "Ada"},
            schema=Person,
        )
    )

    assert isinstance(value, Person)
    assert value.name == "Ada"
    assert value.age == 31


def test_extract_rejects_unsupported_model_type():
    adapter = FakeAdapter([])

    class Unsupported:
        pass

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            extract(
                adapter=adapter,
                model="gpt-test",
                context={"x": 1},
                schema=Unsupported,
            )
        )

    exc = exc_info.value
    assert exc.category == "unsupported_runtime"
    assert exc.attempt_count == 0


def test_dispatch_validates_command_args_before_execution():
    adapter = FakeAdapter(
        [
            '{"kind":"command","command":{"name":"send_email","args":{"to":"not-an-email"}}}',
            '{"kind":"command","command":{"name":"send_email","args":{"to":"user@example.com"}}}',
        ]
    )
    executed = []

    result = asyncio.run(
        dispatch(
            adapter=adapter,
            model="gpt-test",
            context={"intent": "notify"},
            commands=[
                Command(
                    name="send_email",
                    description="Send an email",
                    input_schema={
                        "type": "object",
                        "properties": {"to": {"type": "string", "pattern": ".+@.+"}},
                        "required": ["to"],
                        "additionalProperties": False,
                    },
                    output_schema={
                        "type": "object",
                        "properties": {"status": {"const": "sent"}},
                        "required": ["status"],
                        "additionalProperties": False,
                    },
                    executor=lambda args: executed.append(args) or {"status": "sent"},
                )
            ],
            auto_execute=True,
        )
    )

    assert result["decision"]["kind"] == "command"
    assert result["result"] == {"status": "sent"}
    assert executed == [{"to": "user@example.com"}]
    assert "command_args_invalid" in adapter.requests[1]["instructions"]


def test_dispatch_command_input_model_type_materializes_for_executor_only():
    adapter = FakeAdapter(['{"kind":"command","command":{"name":"send_email","args":{"to":"user@example.com"}}}'])
    executed = []

    class EmailArgs:
        def __init__(self, to):
            self.to = to

        @classmethod
        def model_json_schema(cls):
            return {
                "type": "object",
                "properties": {"to": {"type": "string", "pattern": ".+@.+"}},
                "required": ["to"],
                "additionalProperties": False,
            }

        @classmethod
        def model_validate(cls, payload):
            return cls(to=payload["to"])

    result = asyncio.run(
        dispatch(
            adapter=adapter,
            model="gpt-test",
            context={"intent": "notify"},
            commands=[
                Command(
                    name="send_email",
                    input_schema=EmailArgs,
                    executor=lambda args: executed.append(args) or {"status": "sent"},
                )
            ],
            auto_execute=True,
        )
    )

    assert result["decision"]["command"]["args"] == {"to": "user@example.com"}
    assert len(executed) == 1
    assert isinstance(executed[0], EmailArgs)
    assert executed[0].to == "user@example.com"


def test_dispatch_command_output_model_type_returns_model_instance():
    adapter = FakeAdapter(['{"kind":"command","command":{"name":"compute","args":{}}}'])

    class ComputeResult:
        def __init__(self, ok, code):
            self.ok = ok
            self.code = code

        @classmethod
        def model_json_schema(cls):
            return {
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "code": {"type": "integer"},
                },
                "required": ["ok", "code"],
                "additionalProperties": False,
            }

        @classmethod
        def model_validate(cls, payload):
            return cls(ok=payload["ok"], code=payload["code"])

    result = asyncio.run(
        dispatch(
            adapter=adapter,
            model="gpt-test",
            context={"intent": "compute"},
            commands=[
                Command(
                    name="compute",
                    input_schema={"type": "object", "additionalProperties": False},
                    output_schema=ComputeResult,
                    executor=lambda args: {"ok": True, "code": 200},
                )
            ],
            auto_execute=True,
        )
    )

    assert isinstance(result["result"], ComputeResult)
    assert result["result"].ok is True
    assert result["result"].code == 200


def test_dispatch_label_mode_returns_decision_shape():
    adapter = FakeAdapter(['{"kind":"label","label":"archive"}'])

    value = asyncio.run(
        dispatch(
            adapter=adapter,
            model="gpt-test",
            context={"state": "done"},
            labels=["archive", "ignore"],
        )
    )

    assert value == {"kind": "label", "label": "archive"}


def test_provider_errors_map_without_retry():
    adapter = FakeAdapter([ProviderError("rate_limit", "slow down")])

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            eval_bool(
                adapter=adapter,
                model="gpt-test",
                context={"x": 1},
                expression="x == 1",
                max_attempts=3,
            )
        )

    exc = exc_info.value
    assert exc.category == "provider_rate_limit"
    assert exc.attempt_count == 1


def test_drop_sanitizes_nested_non_json_values_deterministically():
    value = {
        "a": {3, 1, 2},
        "b": [{"ok": True}, object()],
        7: "drop-key",
    }

    assert drop(value) == {"a": [1, 2, 3], "b": [{"ok": True}]}


def test_drop_prunes_unsupported_nested_leaves_without_inventing_nulls():
    value = {"field": object(), "items": [object(), "ok"]}

    assert drop(value) == {"items": ["ok"]}


def test_llmops_defaults_and_sync_wrapper():
    adapter = FakeAdapter(['{"result": false}'])
    ops = LLMOps(adapter=adapter, model="default-model", system_prompt="default prompt")

    value = ops.eval_bool_sync(context={"flag": False}, expression="flag is true")

    assert value is False
    assert adapter.requests[0]["model"] == "default-model"
    assert "default prompt" in adapter.requests[0]["instructions"]


def test_llmops_sync_wrapper_works_inside_running_loop():
    adapter = FakeAdapter(['{"label":"keep"}'])
    ops = LLMOps(adapter=adapter, model="m")

    async def run():
        return ops.classify_sync(context={"x": 1}, labels=["keep", "drop"])

    assert asyncio.run(run()) == "keep"


def test_factory_validation_and_dispatch():
    with pytest.raises(FrameworkError) as exc_info:
        LLMOps.from_provider("unknown", model="m", api_key="x")

    assert exc_info.value.operation == "factory"
    assert exc_info.value.category == "invalid_configuration"


def test_dispatch_executor_output_validation_error():
    adapter = FakeAdapter(['{"kind":"command","command":{"name":"compute","args":{}}}'])

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            dispatch(
                adapter=adapter,
                model="gpt-test",
                context={"intent": "compute"},
                commands=[
                    Command(
                        name="compute",
                        input_schema={"type": "object", "additionalProperties": False},
                        output_schema={
                            "type": "object",
                            "properties": {"ok": {"const": True}},
                            "required": ["ok"],
                            "additionalProperties": False,
                        },
                        executor=lambda args: {"ok": False},
                    )
                ],
                auto_execute=True,
            )
        )

    exc = exc_info.value
    assert exc.category == "executor_output_validation"


def test_dispatch_post_selection_errors_preserve_provider_attempt_count():
    adapter = FakeAdapter(
        [
            '{"kind":"command","command":{"name":"compute","args":{"value":"bad"}}}',
            '{"kind":"command","command":{"name":"compute","args":{"value":2}}}',
        ]
    )

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            dispatch(
                adapter=adapter,
                model="gpt-test",
                context={"intent": "compute"},
                commands=[
                    Command(
                        name="compute",
                        input_schema={
                            "type": "object",
                            "properties": {"value": {"type": "integer"}},
                            "required": ["value"],
                            "additionalProperties": False,
                        },
                        executor=lambda args: (_ for _ in ()).throw(RuntimeError("boom")),
                    )
                ],
                auto_execute=True,
            )
        )

    exc = exc_info.value
    assert exc.category == "command_execution"
    assert exc.attempt_count == 2


def test_extract_rejects_invalid_schema_keywords_before_provider_call():
    adapter = FakeAdapter([])

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            extract(
                adapter=adapter,
                model="gpt-test",
                context={"x": 1},
                schema={"type": "string", "minLength": "bad"},
            )
        )

    exc = exc_info.value
    assert exc.category == "invalid_configuration"
    assert exc.attempt_count == 0
    assert adapter.requests == []


def test_extract_rejects_non_json_schema_literals_before_provider_call():
    adapter = FakeAdapter([])

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            extract(
                adapter=adapter,
                model="gpt-test",
                context={"x": 1},
                schema={"const": object()},
            )
        )

    exc = exc_info.value
    assert exc.category == "invalid_configuration"
    assert exc.attempt_count == 0
    assert adapter.requests == []


def test_extract_model_type_rejects_invalid_derived_schema_before_provider_call():
    adapter = FakeAdapter([])

    class BrokenModel:
        @classmethod
        def model_json_schema(cls) -> dict[str, Any]:
            return {"type": "object", "properties": {"value": {"const": object()}}}

        @classmethod
        def model_validate(cls, payload: Any) -> "BrokenModel":
            return cls()

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            extract(
                adapter=adapter,
                model="gpt-test",
                context={"x": 1},
                schema=BrokenModel,
            )
        )

    exc = exc_info.value
    assert exc.category == "invalid_configuration"
    assert exc.attempt_count == 0
    assert adapter.requests == []


def test_dispatch_rejects_invalid_regex_schema_before_provider_call():
    adapter = FakeAdapter([])

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            dispatch(
                adapter=adapter,
                model="gpt-test",
                context={"intent": "send"},
                commands=[
                    Command(
                        name="send_email",
                        input_schema={
                            "type": "object",
                            "properties": {"to": {"type": "string", "pattern": "("}},
                            "required": ["to"],
                            "additionalProperties": False,
                        },
                        executor=lambda args: {"ok": True},
                    )
                ],
            )
        )

    exc = exc_info.value
    assert exc.category == "invalid_configuration"
    assert exc.attempt_count == 0
    assert adapter.requests == []


def test_dispatch_rejects_unsupported_command_model_type_before_provider_call():
    adapter = FakeAdapter([])

    class Unsupported:
        pass

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            dispatch(
                adapter=adapter,
                model="gpt-test",
                context={"intent": "send"},
                commands=[
                    Command(
                        name="send_email",
                        input_schema=Unsupported,
                        executor=lambda args: {"ok": True},
                    )
                ],
            )
        )

    exc = exc_info.value
    assert exc.category == "unsupported_runtime"
    assert exc.attempt_count == 0
    assert adapter.requests == []


def test_eval_bool_rejects_invalid_system_prompt_before_provider_call():
    adapter = FakeAdapter([])

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            eval_bool(
                adapter=adapter,
                model="gpt-test",
                context={"x": 1},
                expression="x == 1",
                system_prompt=123,
            )
        )

    exc = exc_info.value
    assert exc.category == "invalid_configuration"
    assert exc.attempt_count == 0
    assert adapter.requests == []


def test_llmops_validates_default_system_prompt():
    adapter = FakeAdapter([])

    with pytest.raises(FrameworkError) as exc_info:
        LLMOps(adapter=adapter, model="default-model", system_prompt=123)

    exc = exc_info.value
    assert exc.operation == "factory"
    assert exc.category == "invalid_configuration"
    assert exc.attempt_count == 0


def test_llmops_invalid_model_override_does_not_fall_back_to_default():
    adapter = FakeAdapter([])
    ops = LLMOps(adapter=adapter, model="default-model")

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(ops.eval_bool(context={"flag": True}, expression="flag is true", model=""))

    exc = exc_info.value
    assert exc.operation == "eval_bool"
    assert exc.category == "invalid_configuration"
    assert exc.attempt_count == 0
    assert adapter.requests == []


def test_context_rejects_non_string_mapping_keys_before_provider_call():
    adapter = FakeAdapter([])

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            eval_bool(
                adapter=adapter,
                model="gpt-test",
                context={1: "x"},
                expression="x exists",
            )
        )

    exc = exc_info.value
    assert exc.category == "invalid_configuration"
    assert exc.attempt_count == 0
    assert adapter.requests == []


def test_context_rejects_non_faithful_json_sequences_before_provider_call():
    adapter = FakeAdapter([])

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            eval_bool(
                adapter=adapter,
                model="gpt-test",
                context={"items": ("a", "b")},
                expression="items exists",
            )
        )

    exc = exc_info.value
    assert exc.category == "invalid_configuration"
    assert exc.attempt_count == 0
    assert adapter.requests == []


def test_http_5xx_maps_to_transport():
    assert _http_error_category(503) == "transport"
    assert _http_error_category(500) == "transport"
    assert _http_error_category(400) == "provider_contract"


def test_openai_adapter_malformed_nested_output_maps_to_provider_contract():
    with pytest.raises(ProviderError) as exc_info:
        OpenAIAdapter._extract_openai_text({"output": [1]})

    assert exc_info.value.category == "provider_contract"


def test_openrouter_adapter_malformed_nested_output_maps_to_provider_contract():
    with pytest.raises(ProviderError) as exc_info:
        OpenRouterAdapter._extract_openrouter_text({"choices": [1]})

    assert exc_info.value.category == "provider_contract"


def test_adapter_missing_raw_text_maps_to_provider_contract_without_retry():
    adapter = EnvelopeAdapter({})

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            eval_bool(
                adapter=adapter,
                model="gpt-test",
                context={"x": 1},
                expression="x == 1",
                max_attempts=3,
            )
        )

    exc = exc_info.value
    assert exc.category == "provider_contract"
    assert exc.attempt_count == 1
    assert exc.final_validation_category is None


def test_adapter_non_string_raw_text_maps_to_provider_contract_without_retry():
    adapter = EnvelopeAdapter({"raw_text": {"result": True}})

    with pytest.raises(FrameworkError) as exc_info:
        asyncio.run(
            eval_bool(
                adapter=adapter,
                model="gpt-test",
                context={"x": 1},
                expression="x == 1",
                max_attempts=3,
            )
        )

    exc = exc_info.value
    assert exc.category == "provider_contract"
    assert exc.attempt_count == 1
    assert exc.final_validation_category is None
