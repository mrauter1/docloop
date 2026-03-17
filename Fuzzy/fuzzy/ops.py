from __future__ import annotations

import asyncio
import threading
from typing import Any, Sequence

from .adapters import LLMAdapter, OpenAIAdapter, OpenRouterAdapter
from .core import DEFAULT_MAX_ATTEMPTS, _ensure_optional_prompt_text, classify, dispatch, eval_bool, extract
from .errors import FrameworkError
from .types import Command


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
        raise FrameworkError(
            operation="factory",
            category="invalid_configuration",
            message=f"Unknown provider {provider!r}",
            attempt_count=0,
        )

    async def eval_bool(
        self,
        *,
        context: Any,
        expression: str,
        model: str | None = None,
        max_attempts: int | None = None,
        system_prompt: str | None = None,
    ) -> bool:
        return await eval_bool(
            adapter=self.adapter,
            context=context,
            model=self.model if model is None else model,
            expression=expression,
            max_attempts=max_attempts if max_attempts is not None else self.max_attempts,
            system_prompt=self.system_prompt if system_prompt is None else system_prompt,
        )

    async def classify(
        self,
        *,
        context: Any,
        labels: Sequence[str],
        model: str | None = None,
        max_attempts: int | None = None,
        system_prompt: str | None = None,
    ) -> str:
        return await classify(
            adapter=self.adapter,
            context=context,
            model=self.model if model is None else model,
            labels=labels,
            max_attempts=max_attempts if max_attempts is not None else self.max_attempts,
            system_prompt=self.system_prompt if system_prompt is None else system_prompt,
        )

    async def extract(
        self,
        *,
        context: Any,
        schema: Any,
        model: str | None = None,
        max_attempts: int | None = None,
        system_prompt: str | None = None,
    ) -> Any:
        return await extract(
            adapter=self.adapter,
            context=context,
            model=self.model if model is None else model,
            schema=schema,
            max_attempts=max_attempts if max_attempts is not None else self.max_attempts,
            system_prompt=self.system_prompt if system_prompt is None else system_prompt,
        )

    async def dispatch(
        self,
        *,
        context: Any,
        labels: Sequence[str] | None = None,
        commands: Sequence[Command | dict[str, Any]] | None = None,
        auto_execute: bool = False,
        model: str | None = None,
        max_attempts: int | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        return await dispatch(
            adapter=self.adapter,
            context=context,
            model=self.model if model is None else model,
            labels=labels,
            commands=commands,
            auto_execute=auto_execute,
            max_attempts=max_attempts if max_attempts is not None else self.max_attempts,
            system_prompt=self.system_prompt if system_prompt is None else system_prompt,
        )

    def eval_bool_sync(self, **kwargs: Any) -> bool:
        return _run_sync(self.eval_bool(**kwargs))

    def classify_sync(self, **kwargs: Any) -> str:
        return _run_sync(self.classify(**kwargs))

    def extract_sync(self, **kwargs: Any) -> Any:
        return _run_sync(self.extract(**kwargs))

    def dispatch_sync(self, **kwargs: Any) -> dict[str, Any]:
        return _run_sync(self.dispatch(**kwargs))


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
