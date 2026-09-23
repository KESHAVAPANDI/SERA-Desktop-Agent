"""
SERA 2.0 — Ollama Local LLM Provider.

Provides async/sync connectivity to a local Ollama daemon on http://127.0.0.1:11434.
Implements the canonical LLMProvider interface with native JSON formatting,
low-latency streaming, and structured semantic generation.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, AsyncIterator, Dict, List, Optional
import httpx

from app.models.llm.base import LLMProvider, LLMResponse, ToolCall
from app.models.llm.health import ProviderHealth, ProviderHealthStatus

logger = logging.getLogger("sera.models.llm.ollama")


class OllamaProvider(LLMProvider):
    """Local Ollama LLM Provider integration."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: str = "qwen3.5:4b",
        timeout: float = 30.0,
    ):
        self.base_url = (base_url or os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.model = model
        self.timeout = timeout
        self.health = ProviderHealth()
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self._client

    def is_available(self) -> bool:
        """Synchronously checks if local Ollama daemon is reachable."""
        try:
            with httpx.Client(base_url=self.base_url, timeout=2.0) as client:
                resp = client.get("/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def is_available_async(self) -> bool:
        """Asynchronously checks if local Ollama daemon is reachable."""
        try:
            client = self._get_client()
            resp = await client.get("/api/tags")
            return resp.status_code == 200
        except Exception:
            return False

    def capabilities(self) -> Dict[str, bool]:
        """Returns capabilities of this local provider."""
        return {
            "text": True,
            "vision": "vl" in self.model.lower() or "vision" in self.model.lower(),
            "tool_calling": False,
            "structured_output": True,
            "streaming": True,
            "reasoning": False,
            "embeddings": False,
            "audio": False,
        }

    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 256,
        model: Optional[str] = None,
    ) -> str:
        """Generates a structured JSON response from Ollama."""
        target_model = model or self.model
        client = self._get_client()
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        start_time = time.perf_counter()
        try:
            resp = await client.post("/api/chat", json=payload)
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama API returned HTTP {resp.status_code}: {resp.text}")

            data = resp.json()
            content = data.get("message", {}).get("content", "")
            self.health.record_success(latency_ms)
            return content

        except Exception as err:
            self.health.record_failure(str(err))
            logger.error(f"Ollama generate_structured failed: {err}")
            raise

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        images: Optional[List[bytes]] = None,
        **kwargs,
    ) -> LLMResponse:
        """Implements canonical LLMProvider.generate."""
        client = self._get_client()
        target_model = kwargs.get("model", self.model)
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.0),
                "num_predict": kwargs.get("max_tokens", 512),
            },
        }
        if kwargs.get("response_format") == "json" or kwargs.get("format") == "json":
            payload["format"] = "json"

        start_time = time.perf_counter()
        try:
            resp = await client.post("/api/chat", json=payload)
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama HTTP {resp.status_code}: {resp.text}")

            data = resp.json()
            content = data.get("message", {}).get("content", "")
            self.health.record_success(latency_ms)

            return LLMResponse(
                text=content,
                provider="ollama",
                model=target_model,
                raw_response=data,
            )
        except Exception as err:
            self.health.record_failure(str(err))
            raise

    async def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        images: Optional[List[bytes]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Implements canonical streaming from Ollama."""
        client = self._get_client()
        target_model = kwargs.get("model", self.model)
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", 0.0),
            },
        }
        async with client.stream("POST", "/api/chat", json=payload) as response:
            if response.status_code != 200:
                raise RuntimeError(f"Ollama streaming HTTP {response.status_code}")
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                chunk_data = json.loads(line)
                piece = chunk_data.get("message", {}).get("content", "")
                if piece:
                    yield piece
