import logging
from app.models.llm.openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class CerebrasProvider(OpenAICompatibleProvider):
    """Cerebras Ultra-Fast Inference Provider."""

    DEFAULT_BASE_URL = "https://api.cerebras.ai/v1"
    DEFAULT_MODEL = "gpt-oss-120b"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ):
        selected_model = model or self.DEFAULT_MODEL
        super().__init__(
            provider_name="cerebras",
            base_url=base_url or self.DEFAULT_BASE_URL,
            api_key_env="CEREBRAS_API_KEY",
            model=selected_model,
            timeout=timeout,
            custom_capabilities={
                "text": True,
                "reasoning": True,
                "tool_calling": True,
                "structured_output": True,
                "streaming": True,
                "vision": False,
                "embeddings": False,
                "audio": False,
            },
        )
