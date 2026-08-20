import logging
from app.models.llm.openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class ZAIProvider(OpenAICompatibleProvider):
    """Z.AI GLM Model Provider."""

    DEFAULT_BASE_URL = "https://api.z.ai/api/paas/v4"
    DEFAULT_MODEL = "glm-5"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ):
        selected_model = model or self.DEFAULT_MODEL
        m_lower = selected_model.lower()

        is_vision = any(k in m_lower for k in ["vision", "vl", "glm-4v"])

        super().__init__(
            provider_name="zai",
            base_url=base_url or self.DEFAULT_BASE_URL,
            api_key_env="ZAI_API_KEY",
            model=selected_model,
            timeout=timeout,
            custom_capabilities={
                "text": True,
                "reasoning": True,
                "tool_calling": True,
                "structured_output": True,
                "streaming": True,
                "vision": is_vision,
                "embeddings": False,
                "audio": False,
            },
        )
