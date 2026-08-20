import asyncio
import base64
import json
import os
from typing import Any, AsyncIterator

from groq import Groq

from app.models.llm.base import (
    LLMProvider,
    LLMResponse,
    ToolCall,
)
from app.models.llm.schema import to_openai_tools


class GroqProvider(LLMProvider):

    def __init__(self, model: str):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not configured.")

        self.model = model
        self.client = Groq(api_key=api_key)

    def capabilities(self):
        is_vision_model = any(k in self.model.lower() for k in ["qwen", "vision", "vl", "llama-3.2", "llama-3.3"])
        return {
            "text": True,
            "vision": is_vision_model,
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
        """Prepares messages, embedding base64 images into user message if provided."""
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
        return await asyncio.to_thread(
            self._generate_sync,
            messages,
            tools,
            images,
            kwargs,
        )

    def _generate_sync(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        images: list[bytes] | None,
        kwargs: dict[str, Any],
    ) -> LLMResponse:
        prepared_msgs = self._prepare_messages(messages, images)
        params: dict[str, Any] = {
            "model": self.model,
            "messages": prepared_msgs,
        }
        if tools:
            params["tools"] = to_openai_tools(tools)
            params["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**params)
        message = response.choices[0].message
        tool_calls = []

        if message.tool_calls:
            for call in message.tool_calls:
                arguments = json.loads(call.function.arguments)
                tool_calls.append(
                    ToolCall(
                        id=call.id,
                        name=call.function.name,
                        arguments=arguments,
                    )
                )

        # Strip think tokens if model is a reasoning model like Qwen
        text_content = message.content or ""
        if "</think>" in text_content:
            text_content = text_content.split("</think>", 1)[1].strip()

        return LLMResponse(
            text=text_content,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            provider="groq",
            model=self.model,
            raw_response=response,
        )

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        images: list[bytes] | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Asynchronously streams generated tokens from Groq API."""
        prepared_msgs = self._prepare_messages(messages, images)
        params: dict[str, Any] = {
            "model": self.model,
            "messages": prepared_msgs,
            "stream": True,
        }
        if tools:
            params["tools"] = to_openai_tools(tools)
            params["tool_choice"] = "auto"

        def _get_stream():
            return self.client.chat.completions.create(**params)

        stream = await asyncio.to_thread(_get_stream)

        def _get_next_chunk(it):
            try:
                return next(it)
            except StopIteration:
                return None

        stream_iter = iter(stream)
        in_think_block = False

        while True:
            chunk = await asyncio.to_thread(_get_next_chunk, stream_iter)
            if chunk is None:
                break
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    token = delta.content
                    if "<think>" in token:
                        in_think_block = True
                        continue
                    if "</think>" in token:
                        in_think_block = False
                        continue
                    if in_think_block:
                        continue
                    yield token