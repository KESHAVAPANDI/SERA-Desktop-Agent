import asyncio
import base64
import json
import logging
import os
from typing import Any, AsyncIterator
import httpx

from app.models.llm.base import (
    LLMProvider,
    LLMResponse,
    ToolCall,
)
from app.models.llm.schema import to_openai_tools

logger = logging.getLogger(__name__)


class OpenRouterProvider(LLMProvider):
    """Native async HTTP provider for OpenRouter API."""

    def __init__(self, model: str):
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured.")

        self.model = model
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/sera-ai/sera",
            "X-Title": "SERA 1.0",
        }

    def capabilities(self):
        return {
            "text": True,
            "vision": True,
            "tool_calling": True,
            "structured_output": True,
            "streaming": True,
            "reasoning": True,
        }

    def _prepare_messages(
        self,
        messages: list[dict[str, Any]],
        images: list[bytes] | None = None,
    ) -> list[dict[str, Any]]:
        if not images:
            return messages

        formatted_messages = []
        for msg in messages:
            if msg.get("role") == "user":
                content_list: list[dict[str, Any]] = [
                    {"type": "text", "text": msg.get("content") or ""}
                ]
                for img_bytes in images:
                    b64 = base64.b64encode(img_bytes).decode("utf-8")
                    content_list.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        }
                    )
                formatted_messages.append({"role": "user", "content": content_list})
            else:
                formatted_messages.append(msg)

        return formatted_messages

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        images: list[bytes] | None = None,
        **kwargs,
    ) -> LLMResponse:
        prepared_msgs = self._prepare_messages(messages, images)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": prepared_msgs,
            "stream": False,
        }
        if tools:
            formatted_tools = to_openai_tools(tools)
            if formatted_tools:
                payload["tools"] = formatted_tools

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                self.base_url,
                headers=self.headers,
                json=payload,
            )

            if response.status_code != 200:
                logger.error(f"[OpenRouter] API Error {response.status_code}: {response.text}")
                raise RuntimeError(f"OpenRouter error {response.status_code}: {response.text}")

            data = response.json()
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            raw_tool_calls = message.get("tool_calls") or []

            tool_calls = []
            for call in raw_tool_calls:
                func = call.get("function", {})
                args_str = func.get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except Exception:
                    args = {}

                tool_calls.append(
                    ToolCall(
                        id=call.get("id", ""),
                        name=func.get("name", ""),
                        arguments=args,
                    )
                )

            return LLMResponse(
                text=message.get("content"),
                tool_calls=tool_calls,
                finish_reason="tool_calls" if tool_calls else choice.get("finish_reason", "stop"),
                provider="openrouter",
                model=self.model,
                raw_response=data,
            )

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        images: list[bytes] | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        prepared_msgs = self._prepare_messages(messages, images)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": prepared_msgs,
            "stream": True,
        }
        if tools:
            formatted_tools = to_openai_tools(tools)
            if formatted_tools:
                payload["tools"] = formatted_tools

        async with httpx.AsyncClient(timeout=45.0) as client:
            async with client.stream(
                "POST",
                self.base_url,
                headers=self.headers,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    logger.error(f"[OpenRouter] Stream Error {response.status_code}: {err_body.decode('utf-8', errors='replace')}")
                    raise RuntimeError(f"OpenRouter stream error {response.status_code}")

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content
                        except Exception:
                            pass