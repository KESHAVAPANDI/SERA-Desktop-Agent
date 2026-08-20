import asyncio
import json
import os
import uuid
from typing import Any, AsyncIterator
from app.models.llm.schema import to_gemini_tools
from google import genai

from app.models.llm.base import (
    LLMProvider,
    LLMResponse,
    ToolCall,
)


class GeminiProvider(LLMProvider):

    def __init__(self, model: str):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        self.model = model
        self.client = genai.Client(api_key=api_key)

    def capabilities(self):
        return {
            "text": True,
            "vision": True,
            "tool_calling": True,
            "structured_output": True,
            "streaming": True,
            "reasoning": True,
        }

    def _format_messages_to_prompt(self, messages: list[dict[str, Any]]) -> str:
        contents = []
        for message in messages:
            role = message["role"]
            content = message.get("content") or ""
            tool_calls = message.get("tool_calls")
            if tool_calls:
                content += f" [tool_calls: {tool_calls}]"

            if role == "system":
                contents.append(f"System instructions:\n{content}")
            else:
                contents.append(f"{role}: {content}")
        return "\n\n".join(contents)

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
        prompt = self._format_messages_to_prompt(messages)
        config = {}
        if tools:
            config["tools"] = [{"function_declarations": to_gemini_tools(tools)}]

        contents: list[Any] = [prompt]
        if images:
            for img_bytes in images:
                contents.append(genai.types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config if config else None,
        )

        text = None
        tool_calls = []

        try:
            candidates = response.candidates or []
            for candidate in candidates:
                content = candidate.content
                if not content:
                    continue

                for part in content.parts:
                    function_call = getattr(part, "function_call", None)
                    if function_call:
                        arguments = dict(function_call.args or {})
                        tool_calls.append(
                            ToolCall(
                                id=str(uuid.uuid4()),
                                name=function_call.name,
                                arguments=arguments,
                            )
                        )
                    else:
                        part_text = getattr(part, "text", None)
                        if part_text:
                            if text:
                                text += part_text
                            else:
                                text = part_text
        except Exception as error:
            print(f"[Gemini] Response parsing error: {error}")

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            provider="gemini",
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
        prompt = self._format_messages_to_prompt(messages)
        config = {}
        if tools:
            config["tools"] = [{"function_declarations": to_gemini_tools(tools)}]

        contents: list[Any] = [prompt]
        if images:
            for img_bytes in images:
                contents.append(genai.types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))

        def _get_stream():
            return self.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config if config else None,
            )

        stream = await asyncio.to_thread(_get_stream)

        def _get_next_chunk(it):
            try:
                return next(it)
            except StopIteration:
                return None

        stream_iter = iter(stream)
        while True:
            chunk = await asyncio.to_thread(_get_next_chunk, stream_iter)
            if chunk is None:
                break
            if getattr(chunk, "text", None):
                yield chunk.text