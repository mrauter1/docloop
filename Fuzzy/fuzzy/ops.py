from __future__ import annotations

import asyncio
import threading
from typing import Any, Sequence

from .adapters import (
    AnthropicAdapter,
    AzureOpenAIAdapter,
    GeminiAdapter,
    LLMAdapter,
    LocalOpenAIAdapter,
    OpenAIAdapter,
    OpenRouterAdapter,
)
from .batch import BatchCall, BatchReport, run_batch
from .core import DEFAULT_MAX_ATTEMPTS, _UNSET, _ensure_optional_prompt_text, classify, dispatch, eval_bool, extract
from .execution import CommandPolicy
from .errors import FrameworkError
from .policy import BatchPolicy, FallbackModel, ModelPricing
from .trace import TraceResult, TraceSink
from .types import Command, Message


class LLMOps:
    def __init__(
        self,
        adapter: LLMAdapter,
        model: str,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        system_prompt: str | None = None,
    ) -> None:
        if not isinstance(adapter, LLMAdapter):
            raise FrameworkError(
                operation="factory",
                category="invalid_configuration",
                message="adapter must implement LLMAdapter",
                attempt_count=0,
            )
        if not isinstance(model, str) or not model.strip():
            raise FrameworkError(
                operation="factory",
                category="invalid_configuration",
                message="model must be a non-empty string",
                attempt_count=0,
            )
        if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts < 1:
            raise FrameworkError(
                operation="factory",
                category="invalid_configuration",
                message="max_attempts must be a positive integer",
                attempt_count=0,
            )
        _ensure_optional_prompt_text(system_prompt, operation="factory", name="system_prompt")
        self.adapter = adapter
        self.model = model
        self.max_attempts = max_attempts
        self.system_prompt = system_prompt

    @classmethod
    def from_openai(
        cls,
        *,
        model: str,
        api_key: str,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        system_prompt: str | None = None,
        **adapter_kwargs: Any,
    ) -> "LLMOps":
        try:
            adapter = OpenAIAdapter(api_key=api_key, **adapter_kwargs)
        except Exception as exc:
            raise FrameworkError(
                operation="factory",
                category="invalid_configuration",
                message=str(exc),
                attempt_count=0,
                cause=exc,
            ) from exc
        return cls(adapter=adapter, model=model, max_attempts=max_attempts, system_prompt=system_prompt)

    @classmethod
    def from_openrouter(
        cls,
        *,
        model: str,
        api_key: str,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        system_prompt: str | None = None,
        **adapter_kwargs: Any,
    ) -> "LLMOps":
        try:
            adapter = OpenRouterAdapter(api_key=api_key, **adapter_kwargs)
        except Exception as exc:
            raise FrameworkError(
                operation="factory",
                category="invalid_configuration",
                message=str(exc),
                attempt_count=0,
                cause=exc,
            ) from exc
        return cls(adapter=adapter, model=model, max_attempts=max_attempts, system_prompt=system_prompt)

    @classmethod
    def from_azure_openai(
        cls,
        *,
        model: str,
        api_key: str,
        endpoint: str,
        api_version: str = "2024-10-21",
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        system_prompt: str | None = None,
        **adapter_kwargs: Any,
    ) -> "LLMOps":
        try:
            adapter = AzureOpenAIAdapter(
                api_key=api_key,
                endpoint=endpoint,
                api_version=api_version,
                **adapter_kwargs,
            )
        except Exception as exc:
            raise FrameworkError(
                operation="factory",
                category="invalid_configuration",
                message=str(exc),
                attempt_count=0,
                cause=exc,
            ) from exc
        return cls(adapter=adapter, model=model, max_attempts=max_attempts, system_prompt=system_prompt)

    @classmethod
    def from_anthropic(
        cls,
        *,
        model: str,
        api_key: str,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        system_prompt: str | None = None,
        **adapter_kwargs: Any,
    ) -> "LLMOps":
        try:
            adapter = AnthropicAdapter(api_key=api_key, **adapter_kwargs)
        except Exception as exc:
            raise FrameworkError(
                operation="factory",
                category="invalid_configuration",
                message=str(exc),
                attempt_count=0,
                cause=exc,
            ) from exc
        return cls(adapter=adapter, model=model, max_attempts=max_attempts, system_prompt=system_prompt)

    @classmethod
    def from_gemini(
        cls,
        *,
        model: str,
        api_key: str,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        system_prompt: str | None = None,
        **adapter_kwargs: Any,
    ) -> "LLMOps":
        try:
            adapter = GeminiAdapter(api_key=api_key, **adapter_kwargs)
        except Exception as exc:
            raise FrameworkError(
                operation="factory",
                category="invalid_configuration",
                message=str(exc),
                attempt_count=0,
                cause=exc,
            ) from exc
        return cls(adapter=adapter, model=model, max_attempts=max_attempts, system_prompt=system_prompt)

    @classmethod
    def from_local_openai(
        cls,
        *,
        model: str,
        api_key: str | None = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        system_prompt: str | None = None,
        **adapter_kwargs: Any,
    ) -> "LLMOps":
        try:
            adapter = LocalOpenAIAdapter(api_key=api_key, **adapter_kwargs)
        except Exception as exc:
            raise FrameworkError(
                operation="factory",
                category="invalid_configuration",
                message=str(exc),
                attempt_count=0,
                cause=exc,
            ) from exc
        return cls(adapter=adapter, model=model, max_attempts=max_attempts, system_prompt=system_prompt)

    @classmethod
    def from_provider(
        cls,
        provider: str,
        *,
        model: str,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        system_prompt: str | None = None,
        **provider_kwargs: Any,
    ) -> "LLMOps":
        if provider == "openai":
            return cls.from_openai(
                model=model,
                max_attempts=max_attempts,
                system_prompt=system_prompt,
                **provider_kwargs,
            )
        if provider == "openrouter":
            return cls.from_openrouter(
                model=model,
                max_attempts=max_attempts,
                system_prompt=system_prompt,
                **provider_kwargs,
            )
        if provider == "azure_openai":
            return cls.from_azure_openai(
                model=model,
                max_attempts=max_attempts,
                system_prompt=system_prompt,
                **provider_kwargs,
            )
        if provider == "anthropic":
            return cls.from_anthropic(
                model=model,
                max_attempts=max_attempts,
                system_prompt=system_prompt,
                **provider_kwargs,
            )
        if provider == "gemini":
            return cls.from_gemini(
                model=model,
                max_attempts=max_attempts,
                system_prompt=system_prompt,
                **provider_kwargs,
            )
        if provider == "local_openai":
            return cls.from_local_openai(
                model=model,
                max_attempts=max_attempts,
                system_prompt=system_prompt,
                **provider_kwargs,
            )
        raise FrameworkError(
            operation="factory",
            category="invalid_configuration",
            message=f"Unknown provider {provider!r}",
            attempt_count=0,
        )

    async def eval_bool(
        self,
        *,
        expression: str,
        context: Any = _UNSET,
        messages: Sequence[Message] | Any = _UNSET,
        model: str | None = None,
        max_attempts: int | None = None,
        system_prompt: str | None = None,
        fallback_models: Sequence[FallbackModel] | None = None,
        return_trace: bool = False,
        trace_sink: TraceSink | None = None,
    ) -> bool | TraceResult[bool]:
        return await eval_bool(
            adapter=self.adapter,
            context=context,
            messages=messages,
            model=self.model if model is None else model,
            expression=expression,
            max_attempts=max_attempts if max_attempts is not None else self.max_attempts,
            system_prompt=self.system_prompt if system_prompt is None else system_prompt,
            fallback_models=fallback_models,
            return_trace=return_trace,
            trace_sink=trace_sink,
        )

    async def classify(
        self,
        *,
        labels: Sequence[str],
        context: Any = _UNSET,
        messages: Sequence[Message] | Any = _UNSET,
        model: str | None = None,
        max_attempts: int | None = None,
        system_prompt: str | None = None,
        fallback_models: Sequence[FallbackModel] | None = None,
        return_trace: bool = False,
        trace_sink: TraceSink | None = None,
    ) -> str | TraceResult[str]:
        return await classify(
            adapter=self.adapter,
            context=context,
            messages=messages,
            model=self.model if model is None else model,
            labels=labels,
            max_attempts=max_attempts if max_attempts is not None else self.max_attempts,
            system_prompt=self.system_prompt if system_prompt is None else system_prompt,
            fallback_models=fallback_models,
            return_trace=return_trace,
            trace_sink=trace_sink,
        )

    async def extract(
        self,
        *,
        schema: Any,
        context: Any = _UNSET,
        messages: Sequence[Message] | Any = _UNSET,
        model: str | None = None,
        max_attempts: int | None = None,
        system_prompt: str | None = None,
        fallback_models: Sequence[FallbackModel] | None = None,
        return_trace: bool = False,
        trace_sink: TraceSink | None = None,
    ) -> Any:
        return await extract(
            adapter=self.adapter,
            context=context,
            messages=messages,
            model=self.model if model is None else model,
            schema=schema,
            max_attempts=max_attempts if max_attempts is not None else self.max_attempts,
            system_prompt=self.system_prompt if system_prompt is None else system_prompt,
            fallback_models=fallback_models,
            return_trace=return_trace,
            trace_sink=trace_sink,
        )

    async def dispatch(
        self,
        *,
        labels: Sequence[str] | None = None,
        commands: Sequence[Command | dict[str, Any]] | None = None,
        context: Any = _UNSET,
        messages: Sequence[Message] | Any = _UNSET,
        auto_execute: bool = False,
        model: str | None = None,
        max_attempts: int | None = None,
        system_prompt: str | None = None,
        fallback_models: Sequence[FallbackModel] | None = None,
        command_policy: CommandPolicy | None = None,
        return_trace: bool = False,
        trace_sink: TraceSink | None = None,
    ) -> dict[str, Any]:
        return await dispatch(
            adapter=self.adapter,
            context=context,
            messages=messages,
            model=self.model if model is None else model,
            labels=labels,
            commands=commands,
            auto_execute=auto_execute,
            max_attempts=max_attempts if max_attempts is not None else self.max_attempts,
            system_prompt=self.system_prompt if system_prompt is None else system_prompt,
            fallback_models=fallback_models,
            command_policy=command_policy,
            return_trace=return_trace,
            trace_sink=trace_sink,
        )

    async def run_batch(
        self,
        calls: Sequence[BatchCall],
        *,
        concurrency: int = 4,
        return_traces: bool = False,
        stop_on_error: bool = False,
        model: str | None = None,
        max_attempts: int | None = None,
        system_prompt: str | None = None,
        batch_policy: BatchPolicy | None = None,
        pricing: Sequence[ModelPricing] | None = None,
    ) -> BatchReport:
        return await run_batch(
            calls,
            adapter=self.adapter,
            model=self.model if model is None else model,
            concurrency=concurrency,
            return_traces=return_traces,
            stop_on_error=stop_on_error,
            max_attempts=max_attempts if max_attempts is not None else self.max_attempts,
            system_prompt=self.system_prompt if system_prompt is None else system_prompt,
            batch_policy=batch_policy,
            pricing=pricing,
        )

    def eval_bool_sync(self, **kwargs: Any) -> bool:
        return _run_sync(self.eval_bool(**kwargs))

    def classify_sync(self, **kwargs: Any) -> str:
        return _run_sync(self.classify(**kwargs))

    def extract_sync(self, **kwargs: Any) -> Any:
        return _run_sync(self.extract(**kwargs))

    def dispatch_sync(self, **kwargs: Any) -> dict[str, Any]:
        return _run_sync(self.dispatch(**kwargs))

    def run_batch_sync(self, calls: Sequence[BatchCall], **kwargs: Any) -> BatchReport:
        return _run_sync(self.run_batch(calls, **kwargs))


def _run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}
    error: dict[str, BaseException] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:
            error["value"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()

    if "value" in error:
        raise error["value"]
    return result["value"]
