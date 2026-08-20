from app.models.llm.base import LLMProvider, LLMResponse, ToolCall
from app.models.llm.cerebras import CerebrasProvider
from app.models.llm.embeddings import EmbeddingProvider, MistralEmbeddingProvider
from app.models.llm.gemini import GeminiProvider
from app.models.llm.groq import GroqProvider
from app.models.llm.health import ModelHealthRegistry, ProviderHealth, ProviderHealthStatus
from app.models.llm.latency import ProviderLatencyMetrics
from app.models.llm.mistral import MistralProvider
from app.models.llm.openai_compatible import OpenAICompatibleProvider
from app.models.llm.openrouter import OpenRouterProvider
from app.models.llm.zai import ZAIProvider


def create_provider(
    provider: str,
    model: str,
    base_url: str | None = None,
    timeout: float = 30.0,
) -> LLMProvider:
    """Factory function for instantiating LLM providers."""
    prov_lower = provider.lower()

    if prov_lower == "gemini":
        return GeminiProvider(model=model)

    if prov_lower == "groq":
        return GroqProvider(model=model)

    if prov_lower == "openrouter":
        return OpenRouterProvider(model=model)

    if prov_lower == "cerebras":
        return CerebrasProvider(model=model, base_url=base_url, timeout=timeout)

    if prov_lower == "mistral":
        return MistralProvider(model=model, base_url=base_url, timeout=timeout)

    if prov_lower == "zai":
        return ZAIProvider(model=model, base_url=base_url, timeout=timeout)

    if prov_lower == "openai_compatible":
        return OpenAICompatibleProvider(
            provider_name="custom",
            base_url=base_url or "https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
            model=model,
            timeout=timeout,
        )

    raise ValueError(f"Unsupported LLM provider: '{provider}'")


def create_embedding_provider(
    provider: str = "mistral",
    model: str = "mistral-embed",
    base_url: str | None = None,
) -> EmbeddingProvider:
    """Factory function for instantiating embedding providers."""
    if provider.lower() == "mistral":
        return MistralEmbeddingProvider(model=model, base_url=base_url)
    raise ValueError(f"Unsupported embedding provider: '{provider}'")