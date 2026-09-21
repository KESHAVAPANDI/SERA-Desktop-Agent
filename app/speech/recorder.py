import asyncio
import logging
import threading
import time
import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


class AudioRecorder:
    """Microphone audio recording service supporting both dynamic Hold-To-Talk and fixed wake-word duration."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        dtype: str = "float32",
        block_duration: float = 0.05,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.block_size = int(sample_rate * block_duration)
        self._is_recording = False
        self._lock = threading.Lock()
        self._cancel_flag = False

        self._stream: sd.InputStream | None = None
        self._active_chunks: list[np.ndarray] = []

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def cancel(self) -> None:
        """Signals active recording to immediately halt."""
        self._cancel_flag = True
        self.stop_recording()

    def start_recording(self) -> bool:
        """Starts streaming microphone audio into internal buffer for Hold-To-Talk."""
        with self._lock:
            if self._is_recording:
                return False
            self._is_recording = True
            self._cancel_flag = False
            self._active_chunks = []

        def callback(indata, frames, time_info, status):
            if status:
                logger.debug(f"[AudioRecorder] InputStream status: {status}")
            with self._lock:
                if self._is_recording:
                    self._active_chunks.append(indata[:, 0].copy())

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                blocksize=self.block_size,
                callback=callback,
            )
            self._stream.start()
            logger.info("[AudioRecorder] Hold-To-Talk recording stream opened.")
            return True
        except Exception as e:
            logger.error(f"[AudioRecorder] Failed to open recording stream: {e}")
            with self._lock:
                self._is_recording = False
            return False

    def stop_recording(self) -> np.ndarray:
        """Stops streaming microphone audio and returns concatenated float32 numpy array."""
        with self._lock:
            if not self._is_recording and not self._stream:
                return np.zeros(0, dtype=np.float32)
            self._is_recording = False

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.debug(f"[AudioRecorder] Error closing stream: {e}")
            finally:
                self._stream = None

        with self._lock:
            if not self._active_chunks:
                return np.zeros(0, dtype=np.float32)
            audio_data = np.concatenate(self._active_chunks)
            self._active_chunks = []

        logger.info(f"[AudioRecorder] Recorded {len(audio_data)} samples ({len(audio_data)/self.sample_rate:.2f}s).")
        return audio_data

    def get_current_audio(self) -> np.ndarray:
        """Returns snapshot of accumulated float32 numpy array without stopping the stream."""
        with self._lock:
            if not self._active_chunks:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(self._active_chunks)

    async def record_for(self, seconds: float = 5.0) -> np.ndarray:
        """Records from the microphone for exactly `seconds` duration (for wake-word capture)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._record_sync, seconds)

    def _record_sync(self, seconds: float) -> np.ndarray:
        if not self.start_recording():
            return np.zeros(0, dtype=np.float32)

        t_start = time.perf_counter()
        target_time = t_start + seconds

        while time.perf_counter() < target_time:
            if self._cancel_flag:
                logger.info("[AudioRecorder] Recording cancelled.")
                break
            time.sleep(0.02)

        audio_data = self.stop_recording()
        total_frames = int(self.sample_rate * seconds)
        if len(audio_data) > total_frames:
            audio_data = audio_data[:total_frames]
        return audio_data
