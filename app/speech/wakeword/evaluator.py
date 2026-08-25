import logging
import numpy as np

from .base import WakeWordDetectionResult, WakeWordProvider

logger = logging.getLogger(__name__)


class WakeWordEvaluator:
    """Benchmark and evaluation harness for Wake-Word detection models."""

    def __init__(self, provider: WakeWordProvider):
        self.provider = provider

    def evaluate_stream(self, audio_data: np.ndarray, chunk_size: int = 1280) -> list[WakeWordDetectionResult]:
        results = []
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i : i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            res = self.provider.process_audio_chunk(chunk)
            if res.detected:
                results.append(res)
        return results
