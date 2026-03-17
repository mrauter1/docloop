from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Mapping

from .errors import ProviderError


class LLMAdapter(ABC):
    @abstractmethod
    async def complete(self, request: Mapping[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class OpenAIAdapter(LLMAdapter):
    def __init__(self, *, api_key: str, base_url: str = "https://api.openai.com/v1/responses", timeout: float = 60.0):
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout

    async def complete(self, request: Mapping[str, Any]) -> dict[str, Any]:
        payload = {
            "model": request["model"],
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": request["instructions"]}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": request["context_json"]}],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": f"fuzzy_{request['operation']}",
                    "schema": request["output_schema"],
                    "strict": True,
                }
            },
        }
        response = await asyncio.to_thread(self._post_json, payload)
        raw_text = self._extract_openai_text(response)
        return {
            "raw_text": raw_text,
            "provider_response_id": response.get("id"),
        }

    def _post_json(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        return _perform_request(req, timeout=self.timeout)

    @staticmethod
    def _extract_openai_text(response: Mapping[str, Any]) -> str:
        if isinstance(response.get("output_text"), str):
            return response["output_text"]

        output = response.get("output", [])
        if not isinstance(output, list):
            raise ProviderError("provider_contract", "OpenAI response output must be a list")

        for item in output:
            if not isinstance(item, Mapping):
                raise ProviderError("provider_contract", "OpenAI response output items must be objects")
            content_items = item.get("content", [])
            if not isinstance(content_items, list):
                raise ProviderError("provider_contract", "OpenAI response content must be a list")
            for content in content_items:
                if not isinstance(content, Mapping):
                    raise ProviderError("provider_contract", "OpenAI response content items must be objects")
                text = content.get("text")
                if isinstance(text, str):
                    return text
        raise ProviderError("provider_contract", "OpenAI response did not include usable candidate text")


class OpenRouterAdapter(LLMAdapter):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1/chat/completions",
        timeout: float = 60.0,
        app_name: str | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.app_name = app_name

    async def complete(self, request: Mapping[str, Any]) -> dict[str, Any]:
        payload = {
            "model": request["model"],
            "messages": [
                {"role": "system", "content": request["instructions"]},
                {"role": "user", "content": request["context_json"]},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": f"fuzzy_{request['operation']}",
                    "strict": True,
                    "schema": request["output_schema"],
                },
            },
        }
        response = await asyncio.to_thread(self._post_json, payload)
        raw_text = self._extract_openrouter_text(response)
        return {
            "raw_text": raw_text,
            "provider_response_id": response.get("id"),
        }

    def _post_json(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.app_name:
            headers["X-Title"] = self.app_name

        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        return _perform_request(req, timeout=self.timeout)

    @staticmethod
    def _extract_openrouter_text(response: Mapping[str, Any]) -> str:
        choices = response.get("choices", [])
        if not isinstance(choices, list):
            raise ProviderError("provider_contract", "OpenRouter response choices must be a list")
        for choice in choices:
            if not isinstance(choice, Mapping):
                raise ProviderError("provider_contract", "OpenRouter response choices must be objects")
            message = choice.get("message", {})
            if not isinstance(message, Mapping):
                raise ProviderError("provider_contract", "OpenRouter response messages must be objects")
            content = message.get("content")
            if isinstance(content, str):
                return content
            if content is not None:
                raise ProviderError("provider_contract", "OpenRouter response message content must be a string")
        raise ProviderError("provider_contract", "OpenRouter response did not include usable candidate text")


def _perform_request(request: urllib.request.Request, *, timeout: float) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        category = _http_error_category(exc.code)
        detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
        raise ProviderError(category, detail or str(exc), exc) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError("transport", str(exc), exc) from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ProviderError("provider_contract", "Provider returned non-JSON response", exc) from exc

    if not isinstance(parsed, dict):
        raise ProviderError("provider_contract", "Provider returned an unexpected payload shape")
    return parsed


def _http_error_category(status_code: int) -> str:
    if status_code in {401, 403}:
        return "authentication"
    if status_code == 429:
        return "rate_limit"
    if 500 <= status_code <= 599:
        return "transport"
    return "provider_contract"
