from abc import abstractmethod
from app.models.base import BaseModelProvider

class BaseTTSProvider(BaseModelProvider):
    """Abstract base class for Text-To-Speech providers."""

    @abstractmethod
    def speak(self, text: str, output_path: str = None) -> bytes:
        """Converts text into audio speech bytes and optionally saves to output_path."""
        pass
