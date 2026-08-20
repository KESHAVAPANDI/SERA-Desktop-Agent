from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import numpy as np


@dataclass
class STTResult:
    """Provider-neutral representation of a speech transcription result."""
    text: str
    language: str = "en-US"
    duration: float = 0.0
    provider: str = "unknown"
    model: str = "unknown"
    confidence: float | None = None
    avg_logprob: float | None = None
    no_speech_prob: float | None = None
    compression_ratio: float | None = None
    segments: list[dict[str, Any]] = field(default_factory=list)
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.text

    def __bool__(self) -> bool:
        return bool(self.text and self.text.strip())


class STTProvider(ABC):
    """Abstract Base Class for Speech-to-Text Providers."""

    @abstractmethod
    async def transcribe(
        self,
        audio: np.ndarray | bytes,
        sample_rate: int = 16000,
        language: str = "en-US",
    ) -> STTResult:
        """Transcribes raw audio array (float32 / int16) or WAV bytes to text."""
        pass
