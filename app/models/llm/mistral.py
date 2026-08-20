import logging
from app.models.llm.openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class MistralProvider(OpenAICompatibleProvider):
    """Mistral AI Official API Provider."""

    DEFAULT_BASE_URL = "https://api.mistral.ai/v1"
    DEFAULT_MODEL = "mistral-large-latest"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ):
        selected_model = model or self.DEFAULT_MODEL
        m_lower = selected_model.lower()

        is_vision = any(k in m_lower for k in ["pixtral", "ocr", "vision"])
        is_audio = any(k in m_lower for k in ["voxtral", "audio", "transcribe"])
        is_embed = "embed" in m_lower

        super().__init__(
            provider_name="mistral",
            base_url=base_url or self.DEFAULT_BASE_URL,
            api_key_env="MISTRAL_API_KEY",
            model=selected_model,
            timeout=timeout,
            custom_capabilities={
                "text": True,
                "reasoning": True,
                "tool_calling": not is_embed and not is_audio,
                "structured_output": not is_embed and not is_audio,
                "streaming": not is_embed,
                "vision": is_vision,
                "embeddings": is_embed,
                "audio": is_audio,
            },
        )
