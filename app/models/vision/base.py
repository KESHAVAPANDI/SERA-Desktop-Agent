from abc import abstractmethod
from app.models.base import BaseModelProvider

class BaseVisionProvider(BaseModelProvider):
    """Abstract base class for vision models."""

    @abstractmethod
    def analyze_image(self, image_bytes: bytes, prompt: str = "Describe what is visible in this screenshot.") -> str:
        """Analyzes image content using vision model."""
        pass
