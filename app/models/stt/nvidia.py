import io
import logging
import os
import time
import wave
import httpx
import numpy as np

from app.models.stt.base import STTProvider, STTResult

logger = logging.getLogger(__name__)


class NVIDIASTTProvider(STTProvider):
    """Speech-to-Text provider hosted on NVIDIA NIM (e.g. nvidia/canary-qwen-2.5b)."""

    DEFAULT_ENDPOINT = "https://integrate.api.nvidia.com/v1/audio/transcriptions"
    DEFAULT_MODEL = "nvidia/canary-qwen-2.5b"

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        model: str | None = None,
        timeout: float = 20.0,
    ):
        self.api_key = api_key or os.environ.get("NVIDIA_API_KEY", "")
        self.endpoint = endpoint or self.DEFAULT_ENDPOINT
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout

        if not self.api_key:
            logger.warning("[NVIDIASTTProvider] NVIDIA_API_KEY is not set in environment.")

    def _audio_to_wav_bytes(self, audio: np.ndarray | bytes, sample_rate: int = 16000) -> bytes:
        """Converts raw float32 or int16 numpy array to standard 16kHz 16-bit PCM WAV bytes."""
        if isinstance(audio, bytes):
            return audio

        if isinstance(audio, np.ndarray):
            # Convert float32 [-1.0, 1.0] to int16 [-32768, 32767]
            if audio.dtype == np.float32 or audio.dtype == np.float64:
                clipped = np.clip(audio, -1.0, 1.0)
                pcm_data = (clipped * 32767).astype(np.int16)
            elif audio.dtype == np.int16:
                pcm_data = audio
            else:
                pcm_data = audio.astype(np.int16)

            wav_buf = io.BytesIO()
            with wave.open(wav_buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(pcm_data.tobytes())
            return wav_buf.getvalue()

        raise ValueError(f"Unsupported audio type: {type(audio)}")

    async def transcribe(
        self,
        audio: np.ndarray | bytes,
        sample_rate: int = 16000,
        language: str = "en-US",
    ) -> STTResult:
        """Sends audio to NVIDIA hosted ASR endpoint and returns normalized STTResult."""
        if not self.api_key:
            raise RuntimeError("NVIDIA_API_KEY is missing. Cannot transcribe with NVIDIA ASR.")

        t0 = time.perf_counter()
        wav_bytes = self._audio_to_wav_bytes(audio, sample_rate)
        duration_s = len(wav_bytes) / (sample_rate * 2) if sample_rate > 0 else 5.0

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        files = {
            "file": ("command.wav", wav_bytes, "audio/wav"),
        }

        # Format language for NVIDIA Canary (e.g. en-US or en)
        lang_code = "en" if language.lower() in ("en", "en-us", "english") else language

        data = {
            "model": self.model,
            "language": lang_code,
            "response_format": "json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self.endpoint,
                headers=headers,
                files=files,
                data=data,
            )

            if resp.status_code == 429:
                logger.warning(f"[NVIDIASTTProvider] 429 Rate Limit encountered on {self.model}.")
                raise RuntimeError(f"NVIDIA STT rate limit exceeded (429): {resp.text}")

            if resp.status_code != 200:
                logger.warning(f"[NVIDIASTTProvider] HTTP {resp.status_code} from {self.endpoint}: {resp.text}")
                raise RuntimeError(f"NVIDIA STT API error (HTTP {resp.status_code}): {resp.text}")

            resp_json = resp.json()
            raw_text = resp_json.get("text") or resp_json.get("transcription") or ""
            if not raw_text and "choices" in resp_json and resp_json["choices"]:
                raw_text = resp_json["choices"][0].get("message", {}).get("content", "")

            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            logger.debug(f"[NVIDIASTTProvider] Transcription completed in {elapsed}ms: '{raw_text}'")

            return STTResult(
                text=raw_text.strip(),
                language=language,
                duration=round(duration_s, 2),
                provider="nvidia",
                model=self.model,
                confidence=resp_json.get("confidence", 0.95),
                raw_metadata=resp_json,
            )
