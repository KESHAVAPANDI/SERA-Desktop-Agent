import logging
from typing import Any
import numpy as np

from app.models.stt.base import STTProvider, STTResult
from app.models.stt.nvidia import NVIDIASTTProvider
from app.models.stt.whisper import FasterWhisperSTTProvider

logger = logging.getLogger(__name__)


class PrimaryWithFallbackSTT(STTProvider):
    """Coordinates Primary (NVIDIA Canary-Qwen 2.5B) and Fallback (Faster-Whisper Small) STT."""

    def __init__(
        self,
        primary: STTProvider | None = None,
        fallback: STTProvider | None = None,
        primary_enabled: bool = True,
    ):
        self.primary = primary
        self.fallback = fallback
        self.primary_enabled = primary_enabled

    async def transcribe(
        self,
        audio: np.ndarray | bytes,
        sample_rate: int = 16000,
        language: str = "en-US",
    ) -> STTResult:
        """Attempts transcription on Primary (NVIDIA), falling back cleanly to Faster-Whisper."""
        # 1. Primary Attempt (NVIDIA Hosted)
        if self.primary and self.primary_enabled:
            try:
                print(f"[STT] Provider: NVIDIA")
                print(f"[STT] Model: {getattr(self.primary, 'model', 'Canary-Qwen 2.5B')}")
                result = await self.primary.transcribe(audio, sample_rate=sample_rate, language=language)
                return result
            except Exception as e:
                print(f"[STT] NVIDIA STT unavailable ({e})")
                print("[STT] Falling back to Faster-Whisper")
                logger.warning(f"[PrimaryWithFallbackSTT] NVIDIA failed: {e}. Falling back to Faster-Whisper.")

        # 2. Fallback Attempt (Faster-Whisper)
        if self.fallback:
            print(f"[STT] Provider: Faster-Whisper")
            print(f"[STT] Model: {getattr(self.fallback, 'model_size', 'small')}")
            return await self.fallback.transcribe(audio, sample_rate=sample_rate, language=language)

        raise RuntimeError("No working STT provider available (Primary failed and no fallback configured).")


def create_stt_pipeline(config_data: dict | None = None) -> PrimaryWithFallbackSTT:
    """Builds the configured primary (NVIDIA) and fallback (Faster-Whisper) STT pipeline."""
    cfg = config_data or {}
    stt_cfg = cfg.get("stt", {})
    stt_fallback_cfg = cfg.get("stt_fallback", {})

    # 1. Primary Provider (NVIDIA Hosted Canary-Qwen 2.5B)
    primary_prov = stt_cfg.get("provider", "nvidia")
    primary_model = stt_cfg.get("model", "nvidia/canary-qwen-2.5b")
    primary_endpoint = stt_cfg.get("endpoint", "https://integrate.api.nvidia.com/v1/audio/transcriptions")

    primary = None
    if primary_prov == "nvidia":
        primary = NVIDIASTTProvider(
            endpoint=primary_endpoint,
            model=primary_model,
        )

    # 2. Fallback Provider (Faster-Whisper Small)
    fallback_model = stt_fallback_cfg.get("model", "small")
    fallback_device = stt_fallback_cfg.get("device", "cuda")
    fallback_compute = stt_fallback_cfg.get("compute_type", "float16")

    fallback = FasterWhisperSTTProvider(
        model_size=fallback_model,
        device=fallback_device,
        compute_type=fallback_compute,
        lazy_load=False,
    )

    return PrimaryWithFallbackSTT(
        primary=primary,
        fallback=fallback,
        primary_enabled=True,
    )
