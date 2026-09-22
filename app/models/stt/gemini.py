import io
import logging
import os
import time
import wave
import numpy as np

from google import genai
from google.genai import types

from app.models.stt.base import STTProvider, STTResult

logger = logging.getLogger(__name__)


class GeminiSTTProvider(STTProvider):
    """Speech-to-Text provider powered by Google Gemini API (gemini-3.5-transcribe)."""

    DEFAULT_MODEL = "gemini-3.5-transcribe"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 20.0,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout

        if not self.api_key:
            logger.warning("[GeminiSTTProvider] GEMINI_API_KEY is not set in environment.")

        self._client = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            if not self.api_key:
                raise RuntimeError("GEMINI_API_KEY is missing. Cannot initialize Gemini STT client.")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _audio_to_wav_bytes(self, audio: np.ndarray | bytes, sample_rate: int = 16000) -> bytes:
        """Converts raw float32 or int16 numpy array to standard 16kHz 16-bit PCM WAV bytes."""
        if isinstance(audio, bytes):
            return audio

        if isinstance(audio, np.ndarray):
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

    def _extract_transcript_text(self, response) -> str:
        """Extracts transcription text from Gemini API response candidates."""
        if not response or not getattr(response, "candidates", None):
            return ""

        text_parts = []
        for candidate in response.candidates:
            if not candidate.content or not candidate.content.parts:
                continue
            for part in candidate.content.parts:
                if hasattr(part, "audio_transcription") and part.audio_transcription:
                    at_text = getattr(part.audio_transcription, "text", None)
                    if at_text:
                        text_parts.append(at_text)
                elif hasattr(part, "text") and part.text:
                    text_parts.append(part.text)

        if text_parts:
            return " ".join(text_parts).strip()

        return (getattr(response, "text", None) or "").strip()

    def _transcribe_sync(self, wav_bytes: bytes, language: str) -> tuple[str, dict]:
        """Synchronous API call executed in a thread pool with explicit English language constraint."""
        audio_part = types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav")
        prompt = (
            "Transcribe the spoken audio accurately into English text. "
            "Always transcribe into English verbatim. "
            "Output only the verbatim English transcription without commentary, code blocks, or preamble."
        )

        lang_codes = [language] if language else ["en-US"]
        if "en-US" not in lang_codes and "en" not in lang_codes:
            lang_codes.extend(["en-US", "en"])

        config = types.GenerateContentConfig(
            temperature=0.0,
            audio_transcription_config=types.AudioTranscriptionConfig(
                language_codes=lang_codes,
                mode="VERBATIM",
            ),
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=[audio_part, prompt],
            config=config,
        )

        transcript_text = self._extract_transcript_text(response)

        # Check for non-Latin / non-English script violation (e.g. Devanagari, Arabic, etc.)
        non_english_chars = [c for c in transcript_text if ord(c) > 0x024F and not c.isspace()]
        if non_english_chars:
            logger.warning(
                f"[GeminiSTTProvider] Language policy violation: Non-English characters detected in transcript: '{transcript_text}'"
            )

        return transcript_text, {"language_policy": "en-US", "enforced_languages": lang_codes}

    async def transcribe(
        self,
        audio: np.ndarray | bytes,
        sample_rate: int = 16000,
        language: str = "en-US",
    ) -> STTResult:
        """Transcribes audio using Google Gemini 3.5 Transcribe model."""
        import asyncio

        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is missing. Cannot transcribe with Gemini STT.")

        t0 = time.perf_counter()
        wav_bytes = self._audio_to_wav_bytes(audio, sample_rate)
        duration_s = len(wav_bytes) / (sample_rate * 2) if sample_rate > 0 else 5.0

        raw_text, raw_meta = await asyncio.to_thread(self._transcribe_sync, wav_bytes, language)
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        logger.debug(f"[GeminiSTTProvider] Transcription completed in {elapsed}ms: '{raw_text}'")

        return STTResult(
            text=raw_text.strip(),
            language=language,
            duration=round(duration_s, 2),
            provider="gemini",
            model=self.model,
            confidence=0.98 if raw_text else 0.0,
            raw_metadata=raw_meta,
        )
