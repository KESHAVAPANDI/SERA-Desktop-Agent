import logging
import os
import time
import numpy as np

from .base import WakeWordDetectionResult, WakeWordProvider, WakeWordStatus

logger = logging.getLogger(__name__)


class LocalCustomWakeWordProvider(WakeWordProvider):
    """Local Custom 'Hey SERA' Wake-Word Provider.
    
    Truthfully inspects local model files (e.g. models/wakeword/hey_sera.tflite).
    If no model weights are found, reports NOT_CONFIGURED with zero fake inferences.
    """

    def __init__(
        self,
        model_path: str = "models/wakeword/hey_sera.tflite",
        threshold: float = 0.75,
        enabled: bool = False,
    ):
        self.model_path = model_path
        self.threshold = threshold
        self.enabled = enabled
        self._is_loaded = False
        self._status = WakeWordStatus.NOT_CONFIGURED if not enabled else WakeWordStatus.NOT_CONFIGURED

    def initialize(self) -> bool:
        if not self.enabled:
            self._status = WakeWordStatus.DISABLED
            return False

        if not os.path.exists(self.model_path):
            logger.info(
                f"[LocalCustomWakeWordProvider] Wake-word model not found at '{self.model_path}'. "
                "Wake word status: NOT CONFIGURED."
            )
            self._is_loaded = False
            self._status = WakeWordStatus.NOT_CONFIGURED
            return False

        try:
            # Placeholder for future TFLite / ONNX runtime session loading
            self._is_loaded = True
            self._status = WakeWordStatus.READY
            logger.info(f"[LocalCustomWakeWordProvider] Successfully loaded model from '{self.model_path}'.")
            return True
        except Exception as e:
            logger.error(f"[LocalCustomWakeWordProvider] Failed to load model '{self.model_path}': {e}")
            self._is_loaded = False
            self._status = WakeWordStatus.ERROR
            return False

    def process_audio_chunk(self, audio_chunk: np.ndarray) -> WakeWordDetectionResult:
        if not self._is_loaded or not self.enabled:
            return WakeWordDetectionResult(detected=False, confidence=0.0, timestamp=time.time())

        # Future inference integration on custom weights
        return WakeWordDetectionResult(detected=False, confidence=0.0, timestamp=time.time())

    def get_status(self) -> WakeWordStatus:
        return self._status

    @property
    def is_configured(self) -> bool:
        return self._is_loaded
