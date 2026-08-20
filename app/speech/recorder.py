import asyncio
import logging
import threading
import time
import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


class AudioRecorder:
    """Fixed-duration microphone audio recording service with zero VAD delay and cancellation."""

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

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def cancel(self) -> None:
        """Signals active recording to immediately halt."""
        self._cancel_flag = True

    async def record_for(self, seconds: float = 5.0) -> np.ndarray:
        """Records from the microphone for exactly `seconds` duration.

        No VAD, no speech detection, no silence timeouts.
        Returns:
            1D numpy array of float32 samples.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._record_sync, seconds)

    def _record_sync(self, seconds: float) -> np.ndarray:
        with self._lock:
            self._is_recording = True
            self._cancel_flag = False

        total_frames = int(self.sample_rate * seconds)
        recorded_chunks = []
        frames_collected = 0

        def callback(indata, frames, time_info, status):
            if status:
                logger.debug(f"[AudioRecorder] InputStream status: {status}")
            recorded_chunks.append(indata[:, 0].copy())

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                blocksize=self.block_size,
                callback=callback,
            ):
                t_start = time.perf_counter()
                target_time = t_start + seconds

                while time.perf_counter() < target_time:
                    if self._cancel_flag:
                        logger.info("[AudioRecorder] Recording cancelled by user/runtime.")
                        break
                    time.sleep(0.01)

            if not recorded_chunks:
                return np.zeros(0, dtype=np.float32)

            audio_data = np.concatenate(recorded_chunks)
            # Ensure exact length or trim if slight overage
            if len(audio_data) > total_frames:
                audio_data = audio_data[:total_frames]
            return audio_data

        except Exception as e:
            logger.error(f"[AudioRecorder] Error during audio capture: {e}")
            return np.zeros(0, dtype=np.float32)
        finally:
            with self._lock:
                self._is_recording = False
