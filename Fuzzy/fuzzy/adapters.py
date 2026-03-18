from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Mapping

from .errors import ProviderError
from .schema import deterministic_json_dumps


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
            "input": _build_openai_input(request),
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
            "provider_metadata": _extract_provider_metadata(response),
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


class AzureOpenAIAdapter(OpenAIAdapter):
    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str,
        api_version: str = "2024-10-21",
        timeout: float = 60.0,
    ) -> None:
        normalized_endpoint = endpoint.rstrip("/")
        if not normalized_endpoint:
            raise ValueError("endpoint is required")
        self.api_version = api_version
        super().__init__(
            api_key=api_key,
            base_url=f"{normalized_endpoint}/openai/responses?api-version={api_version}",
            timeout=timeout,
        )

    def _post_json(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url,
            data=body,
            headers={
                "api-key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        return _perform_request(req, timeout=self.timeout)


class LocalOpenAIAdapter(OpenAIAdapter):
    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8000/v1/responses",
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        normalized_base_url = base_url.rstrip("/")
        if not normalized_base_url:
            raise ValueError("base_url is required")
        self.api_key = api_key
        self.base_url = normalized_base_url
        self.timeout = timeout

    def _post_json(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        return _perform_request(req, timeout=self.timeout)


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
            "messages": _build_openrouter_messages(request),
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
            "provider_metadata": _extract_provider_metadata(response),
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


class AnthropicAdapter(LLMAdapter):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.anthropic.com/v1/messages",
        anthropic_version: str = "2023-06-01",
        max_tokens: int = 1024,
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer")
        self.api_key = api_key
        self.base_url = base_url
        self.anthropic_version = anthropic_version
        self.max_tokens = max_tokens
        self.timeout = timeout

    async def complete(self, request: Mapping[str, Any]) -> dict[str, Any]:
        payload = {
            "model": request["model"],
            "system": _build_schema_instruction(request),
            "messages": _build_anthropic_messages(request),
            "max_tokens": self.max_tokens,
        }
        response = await asyncio.to_thread(self._post_json, payload)
        raw_text = self._extract_anthropic_text(response)
        return {
            "raw_text": raw_text,
            "provider_response_id": response.get("id"),
            "provider_metadata": _extract_anthropic_metadata(response),
        }

    def _post_json(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": self.anthropic_version,
                "content-type": "application/json",
            },
            method="POST",
        )
        return _perform_request(req, timeout=self.timeout)

    @staticmethod
    def _extract_anthropic_text(response: Mapping[str, Any]) -> str:
        content = response.get("content", [])
        if not isinstance(content, list):
            raise ProviderError("provider_contract", "Anthropic response content must be a list")
        for item in content:
            if not isinstance(item, Mapping):
                raise ProviderError("provider_contract", "Anthropic response content items must be objects")
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                return item["text"]
        raise ProviderError("provider_contract", "Anthropic response did not include usable candidate text")


class GeminiAdapter(LLMAdapter):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta/models",
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        normalized_base_url = base_url.rstrip("/")
        if not normalized_base_url:
            raise ValueError("base_url is required")
        self.api_key = api_key
        self.base_url = normalized_base_url
        self.timeout = timeout

    async def complete(self, request: Mapping[str, Any]) -> dict[str, Any]:
        payload = {
            "systemInstruction": {
                "parts": [{"text": _build_schema_instruction(request)}],
            },
            "contents": _build_gemini_contents(request),
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": request["output_schema"],
            },
        }
        response = await asyncio.to_thread(self._post_json, request["model"], payload)
        raw_text = self._extract_gemini_text(response)
        return {
            "raw_text": raw_text,
            "provider_response_id": _extract_gemini_response_id(response),
            "provider_metadata": _extract_gemini_metadata(response),
        }

    def _post_json(self, model: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{urllib.parse.quote(model, safe='')}:generateContent?key={urllib.parse.quote(self.api_key, safe='')}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return _perform_request(req, timeout=self.timeout)

    @staticmethod
    def _extract_gemini_text(response: Mapping[str, Any]) -> str:
        candidates = response.get("candidates", [])
        if not isinstance(candidates, list):
            raise ProviderError("provider_contract", "Gemini response candidates must be a list")
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                raise ProviderError("provider_contract", "Gemini response candidates must be objects")
            content = candidate.get("content", {})
            if not isinstance(content, Mapping):
                raise ProviderError("provider_contract", "Gemini response content must be an object")
            parts = content.get("parts", [])
            if not isinstance(parts, list):
                raise ProviderError("provider_contract", "Gemini response parts must be a list")
            text_parts: list[str] = []
            for part in parts:
                if not isinstance(part, Mapping):
                    raise ProviderError("provider_contract", "Gemini response parts must be objects")
                text = part.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
            if text_parts:
                return "".join(text_parts)
        raise ProviderError("provider_contract", "Gemini response did not include usable candidate text")


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


def _build_openai_input(request: Mapping[str, Any]) -> list[dict[str, Any]]:
    items = [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": request["instructions"]}],
        }
    ]
    for message in request["messages"]:
        items.append(
            {
                "role": message["role"],
                "content": [_build_openai_content_part(part) for part in message["parts"]],
            }
        )
    return items


def _build_openai_content_part(part: Mapping[str, Any]) -> dict[str, str]:
    if part["type"] == "text":
        return {"type": "input_text", "text": part["text"]}
    return {"type": "input_text", "text": deterministic_json_dumps(part["data"])}


def _build_openrouter_messages(request: Mapping[str, Any]) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": request["instructions"]}]
    for message in request["messages"]:
        messages.append(
            {
                "role": message["role"],
                "content": _render_message_text(message["parts"]),
            }
        )
    return messages


def _build_anthropic_messages(request: Mapping[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for message in request["messages"]:
        messages.append(
            {
                "role": message["role"],
                "content": [{"type": "text", "text": _render_message_text(message["parts"])}],
            }
        )
    return messages


def _build_gemini_contents(request: Mapping[str, Any]) -> list[dict[str, Any]]:
    contents: list[dict[str, Any]] = []
    for message in request["messages"]:
        contents.append(
            {
                "role": "model" if message["role"] == "assistant" else "user",
                "parts": [{"text": _render_message_text(message["parts"])}],
            }
        )
    return contents


def _render_message_text(parts: list[Mapping[str, Any]]) -> str:
    rendered: list[str] = []
    for part in parts:
        if part["type"] == "text":
            rendered.append(part["text"])
            continue
        rendered.append(deterministic_json_dumps(part["data"]))
    return "\n\n".join(rendered)


def _build_schema_instruction(request: Mapping[str, Any]) -> str:
    return (
        f"{request['instructions']}\n\n"
        "Return exactly one JSON value that matches this schema:\n"
        f"{deterministic_json_dumps(request['output_schema'])}"
    )


def _extract_provider_metadata(response: Mapping[str, Any]) -> dict[str, Any] | None:
    usage = response.get("usage")
    if not isinstance(usage, Mapping):
        return None
    metadata = {str(key): value for key, value in usage.items() if isinstance(key, str)}
    return metadata or None


def _extract_anthropic_metadata(response: Mapping[str, Any]) -> dict[str, Any] | None:
    usage = response.get("usage")
    if not isinstance(usage, Mapping):
        return None
    metadata: dict[str, Any] = {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if isinstance(input_tokens, int) and not isinstance(input_tokens, bool) and input_tokens >= 0:
        metadata["input_tokens"] = input_tokens
    if isinstance(output_tokens, int) and not isinstance(output_tokens, bool) and output_tokens >= 0:
        metadata["output_tokens"] = output_tokens
    if "input_tokens" in metadata and "output_tokens" in metadata:
        metadata["total_tokens"] = metadata["input_tokens"] + metadata["output_tokens"]
    return metadata or None


def _extract_gemini_response_id(response: Mapping[str, Any]) -> str | None:
    response_id = response.get("responseId")
    return response_id if isinstance(response_id, str) else None


def _extract_gemini_metadata(response: Mapping[str, Any]) -> dict[str, Any] | None:
    usage = response.get("usageMetadata")
    if not isinstance(usage, Mapping):
        return None
    metadata: dict[str, Any] = {}
    prompt_tokens = usage.get("promptTokenCount")
    completion_tokens = usage.get("candidatesTokenCount")
    total_tokens = usage.get("totalTokenCount")
    if isinstance(prompt_tokens, int) and not isinstance(prompt_tokens, bool) and prompt_tokens >= 0:
        metadata["prompt_tokens"] = prompt_tokens
    if isinstance(completion_tokens, int) and not isinstance(completion_tokens, bool) and completion_tokens >= 0:
        metadata["completion_tokens"] = completion_tokens
    if isinstance(total_tokens, int) and not isinstance(total_tokens, bool) and total_tokens >= 0:
        metadata["total_tokens"] = total_tokens
    elif "prompt_tokens" in metadata and "completion_tokens" in metadata:
        metadata["total_tokens"] = metadata["prompt_tokens"] + metadata["completion_tokens"]
    return metadata or None
