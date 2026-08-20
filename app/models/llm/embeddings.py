from abc import ABC, abstractmethod
import logging
import os
import httpx

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract interface for text embedding providers."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embeds a list of text strings into float vectors."""
        pass


class MistralEmbeddingProvider(EmbeddingProvider):
    """Embeddings provider powered by Mistral AI official API."""

    DEFAULT_BASE_URL = "https://api.mistral.ai/v1"
    DEFAULT_MODEL = "mistral-embed"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 20.0,
    ):
        self.model = model or self.DEFAULT_MODEL
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.api_key = os.environ.get("MISTRAL_API_KEY", "")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generates embedding vectors for the given text inputs."""
        if not self.api_key:
            raise RuntimeError("MISTRAL_API_KEY is not configured for embeddings.")

        if not texts:
            return []

        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": texts,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"[MistralEmbeddingProvider] HTTP {resp.status_code}: {resp.text}")

            data = resp.json().get("data", [])
            # Sort by index if present to guarantee ordering
            sorted_data = sorted(data, key=lambda x: x.get("index", 0))
            return [item.get("embedding", []) for item in sorted_data]
