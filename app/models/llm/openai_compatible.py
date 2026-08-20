import asyncio
import base64
import json
import logging
import os
import time
from typing import Any, AsyncIterator
import httpx

from app.models.llm.base import LLMProvider, LLMResponse, ToolCall
from app.models.llm.health import ProviderHealth, ProviderHealthStatus
from app.models.llm.schema import to_openai_tools

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(LLMProvider):
    """Generic provider abstraction for OpenAI-compatible REST endpoints (Cerebras, Mistral, Z.AI, etc.)."""

    def __init__(
        self,
        provider_name: str,
        base_url: str,
        api_key_env: str,
        model: str,
        timeout: float = 30.0,
        custom_capabilities: dict[str, bool] | None = None,
    ):
        self.provider_name = provider_name
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.model = model
        self.timeout = timeout
        self._custom_capabilities = custom_capabilities or {}
        self.health = ProviderHealth()

        self._api_key = os.environ.get(self.api_key_env, "")
        if not self._api_key:
            self.health.status = ProviderHealthStatus.UNAVAILABLE
            self.health.last_error_message = f"Environment variable '{self.api_key_env}' is missing."
            logger.debug(f"[{self.provider_name}] Missing {self.api_key_env}. Provider marked UNAVAILABLE.")

    def capabilities(self) -> dict[str, bool]:
        """Returns capability dictionary for the model."""
        m_lower = self.model.lower()
        is_vision = any(k in m_lower for k in ["vision", "vl", "pixtral", "ocr", "glm-4v"])
        is_reasoning = any(k in m_lower for k in ["oss", "r1", "reasoning", "glm-5", "large", "medium", "codestral"])

        default_caps = {
            "text": True,
            "vision": is_vision,
            "tool_calling": True,
            "structured_output": True,
            "streaming": True,
            "reasoning": is_reasoning,
            "embeddings": "embed" in m_lower,
            "audio": "voxtral" in m_lower or "audio" in m_lower,
        }
        default_caps.update(self._custom_capabilities)
        return default_caps

    def _prepare_messages(
        self,
        messages: list[dict[str, Any]],
        images: list[bytes] | None = None,
    ) -> list[dict[str, Any]]:
        """Formats messages and embeds base64 image data for multimodal models."""
        if not images:
            return messages

        formatted = []
        for msg in messages:
            if msg.get("role") == "user":
                content_list: list[dict[str, Any]] = [
                    {"type": "text", "text": msg.get("content") or ""}
                ]
                for img in images:
                    b64 = base64.b64encode(img).decode("utf-8")
                    content_list.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    })
                formatted.append({"role": "user", "content": content_list})
            else:
                formatted.append(msg)
        return formatted

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        images: list[bytes] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Sends chat completion request to the OpenAI-compatible endpoint."""
        if not self._api_key:
            raise RuntimeError(f"Cannot generate: {self.api_key_env} is not configured.")

        t0 = time.perf_counter()
        prepared_msgs = self._prepare_messages(messages, images)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": prepared_msgs,
        }

        if tools and self.capabilities().get("tool_calling", True):
            payload["tools"] = to_openai_tools(tools)
            payload["tool_choice"] = "auto"

        # Structured output format if requested
        if kwargs.get("response_format"):
            payload["response_format"] = kwargs["response_format"]
        if kwargs.get("temperature") is not None:
            payload["temperature"] = kwargs["temperature"]
        if kwargs.get("max_tokens") is not None:
            payload["max_tokens"] = kwargs["max_tokens"]

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

                if resp.status_code != 200:
                    retry_after = None
                    if "Retry-After" in resp.headers:
                        try:
                            retry_after = float(resp.headers["Retry-After"])
                        except ValueError:
                            pass
                    self.health.record_failure(resp.text, status_code=resp.status_code, retry_after=retry_after)
                    raise RuntimeError(f"[{self.provider_name}] HTTP {resp.status_code}: {resp.text}")

                resp_json = resp.json()
                self.health.record_success(elapsed_ms)

                choice = resp_json.get("choices", [{}])[0]
                message = choice.get("message", {})
                text_content = message.get("content") or ""

                # Strip <think> tags if reasoning tokens are returned inline
                if "</think>" in text_content:
                    text_content = text_content.split("</think>", 1)[1].strip()

                tool_calls: list[ToolCall] = []
                raw_tool_calls = message.get("tool_calls") or []
                for tc in raw_tool_calls:
                    fn = tc.get("function", {})
                    args_raw = fn.get("arguments", "{}")
                    try:
                        args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                    except Exception:
                        args = {"raw": args_raw}
                    tool_calls.append(ToolCall(
                        id=tc.get("id", "call_0"),
                        name=fn.get("name", "unknown"),
                        arguments=args,
                    ))

                return LLMResponse(
                    text=text_content,
                    tool_calls=tool_calls,
                    finish_reason=choice.get("finish_reason", "stop"),
                    provider=self.provider_name,
                    model=self.model,
                    raw_response=resp_json,
                )

            except httpx.TimeoutException as e:
                self.health.record_failure(f"Timeout ({self.timeout}s)", status_code=408)
                raise RuntimeError(f"[{self.provider_name}] Request timed out after {self.timeout}s: {e}")
            except Exception as e:
                if not isinstance(e, RuntimeError):
                    self.health.record_failure(str(e))
                raise

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        images: list[bytes] | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Streams tokens from OpenAI-compatible SSE endpoint."""
        if not self._api_key:
            raise RuntimeError(f"Cannot stream: {self.api_key_env} is not configured.")

        t0 = time.perf_counter()
        prepared_msgs = self._prepare_messages(messages, images)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": prepared_msgs,
            "stream": True,
        }

        if tools and self.capabilities().get("tool_calling", True):
            payload["tools"] = to_openai_tools(tools)
            payload["tool_choice"] = "auto"

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        in_think_block = False

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        err_text = body.decode("utf-8", errors="replace")
                        self.health.record_failure(err_text, status_code=response.status_code)
                        raise RuntimeError(f"[{self.provider_name}] Stream HTTP {response.status_code}: {err_text}")

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            choices = chunk.get("choices", [])
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})
                            token = delta.get("content")
                            if token:
                                if "<think>" in token:
                                    in_think_block = True
                                    continue
                                if "</think>" in token:
                                    in_think_block = False
                                    continue
                                if in_think_block:
                                    continue
                                yield token
                        except Exception:
                            continue

                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                self.health.record_success(elapsed_ms)

            except Exception as e:
                if not isinstance(e, RuntimeError):
                    self.health.record_failure(str(e))
                raise
