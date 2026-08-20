import io
import logging
import os
import sys
import time
import wave
import numpy as np

from app.models.stt.base import STTProvider, STTResult

logger = logging.getLogger(__name__)

# Ensure CUDA and cuDNN DLL directories are accessible on Windows
if sys.platform == "win32":
    cuda_paths = [
        r"C:\Program Files\Blackmagic Design\DaVinci Resolve",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.5\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.3\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.2\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0\bin",
    ]
    for p in cuda_paths:
        if os.path.exists(os.path.join(p, "cublas64_12.dll")):
            try:
                os.add_dll_directory(p)
            except AttributeError:
                pass
            os.environ["PATH"] = p + os.path.pathsep + os.environ["PATH"]
            break


class FasterWhisperSTTProvider(STTProvider):
    """Local fallback Speech-to-Text provider powered by Faster-Whisper Small."""

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cuda",
        compute_type: str = "float16",
        lazy_load: bool = False,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

        if not lazy_load:
            self._get_model()

    def _get_model(self):
        if self._model is not None:
            return self._model

        from faster_whisper import WhisperModel
        try:
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info(f"[FasterWhisperSTTProvider] Loaded {self.model_size} on {self.device} ({self.compute_type}).")
        except Exception as e:
            logger.warning(f"[FasterWhisperSTTProvider] GPU init failed ({e}), falling back to CPU int8...")
            self._model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",
            )
        return self._model

    def _audio_to_float32(self, audio: np.ndarray | bytes, sample_rate: int = 16000) -> np.ndarray:
        """Ensures audio input is a 1D float32 numpy array normalized to [-1.0, 1.0]."""
        if isinstance(audio, bytes):
            wav_buf = io.BytesIO(audio)
            with wave.open(wav_buf, "rb") as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                frames = wf.readframes(wf.getnframes())
                if sampwidth == 2:
                    data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                elif sampwidth == 4:
                    data = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
                else:
                    data = np.frombuffer(frames, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
                if n_channels > 1:
                    data = data.reshape(-1, n_channels)[:, 0]
                return data

        if isinstance(audio, np.ndarray):
            if audio.ndim > 1:
                audio = audio[:, 0]
            if audio.dtype == np.int16:
                return audio.astype(np.float32) / 32768.0
            return audio.astype(np.float32)

        raise ValueError(f"Unsupported audio type: {type(audio)}")

    async def transcribe(
        self,
        audio: np.ndarray | bytes,
        sample_rate: int = 16000,
        language: str = "en",
    ) -> STTResult:
        """Transcribes audio using local Faster-Whisper."""
        model = self._get_model()
        audio_data = self._audio_to_float32(audio, sample_rate)
        duration_s = len(audio_data) / sample_rate if sample_rate > 0 else 5.0

        lang_code = "en" if language.lower().startswith("en") else language

        segments, info = model.transcribe(
            audio_data,
            language=lang_code,
            task="transcribe",
            beam_size=5,
            vad_filter=False,  # Command buffer already fixed-duration
            temperature=0.0,
        )

        segments_list = list(segments)
        text_parts = []
        avg_logprobs = []
        no_speech_probs = []
        compression_ratios = []

        for s in segments_list:
            if s.text:
                text_parts.append(s.text.strip())
            avg_logprobs.append(s.avg_logprob)
            no_speech_probs.append(s.no_speech_prob)
            compression_ratios.append(s.compression_ratio)

        final_text = " ".join(text_parts).strip()
        mean_avg_logprob = float(np.mean(avg_logprobs)) if avg_logprobs else 0.0
        mean_no_speech = float(np.mean(no_speech_probs)) if no_speech_probs else 0.0
        mean_compression = float(np.mean(compression_ratios)) if compression_ratios else 1.0

        return STTResult(
            text=final_text,
            language=lang_code,
            duration=round(duration_s, 2),
            provider="faster_whisper",
            model=self.model_size,
            avg_logprob=mean_avg_logprob,
            no_speech_prob=mean_no_speech,
            compression_ratio=mean_compression,
            confidence=max(0.0, 1.0 - mean_no_speech),
            segments=[{"text": s.text, "start": s.start, "end": s.end} for s in segments_list],
            raw_metadata={"segments_count": len(segments_list)},
        )
