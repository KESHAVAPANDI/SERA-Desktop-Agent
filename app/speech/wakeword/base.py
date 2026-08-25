from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import numpy as np


class WakeWordStatus(str, Enum):
    NOT_CONFIGURED = "NOT CONFIGURED"
    READY = "READY"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    ERROR = "ERROR"


@dataclass
class WakeWordDetectionResult:
    detected: bool
    phrase: str = "Hey SERA"
    confidence: float = 0.0
    timestamp: float = 0.0


class WakeWordProvider(ABC):
    """Abstract Base Class for local wake-word detection providers."""

    @abstractmethod
    def initialize(self) -> bool:
        """Loads models or sets up detection state."""
        pass

    @abstractmethod
    def process_audio_chunk(self, audio_chunk: np.ndarray) -> WakeWordDetectionResult:
        """Processes a streaming 16kHz mono audio chunk."""
        pass

    @abstractmethod
    def get_status(self) -> WakeWordStatus:
        """Returns the current status of the wake-word provider."""
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the provider is fully configured with model weights."""
        pass
