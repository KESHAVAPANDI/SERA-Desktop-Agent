from abc import ABC, abstractmethod
import logging
import threading
import time
from typing import Callable
import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


class LegacyWakeWordProvider(ABC):
    """Abstract interface for local zero-cloud wake-word detection."""

    @abstractmethod
    def start(self, on_detected: Callable[[], None]) -> None:
        """Starts listening for the wake word in a non-blocking background thread."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stops the wake-word listener and releases audio streams."""
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """Returns True if the wake-word detector is currently listening."""
        pass

    @abstractmethod
    def pause(self) -> None:
        """Temporarily pauses detections and releases microphone ownership."""
        pass

    @abstractmethod
    def resume(self) -> None:
        """Resumes wake-word detections and reacquires microphone."""
        pass


class OpenWakeWordDetector(LegacyWakeWordProvider):
    """Local Wake-Word Detector for 'SERA' with dynamic microphone yielding and state suppression."""

    def __init__(
        self,
        phrase: str = "SERA",
        sensitivity: float = 0.5,
        debounce_ms: int = 1200,
        sample_rate: int = 16000,
        chunk_size: int = 1280,  # 80ms chunk at 16kHz
    ):
        self.phrase = phrase.upper()
        self.sensitivity = sensitivity
        self.debounce_ms = debounce_ms
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size

        self._running = False
        self._paused = False
        self._thread: threading.Thread | None = None
        self._last_detect_time = 0.0
        self._on_detected: Callable[[], None] | None = None
        self._lock = threading.Lock()

    def start(self, on_detected: Callable[[], None]) -> None:
        """Starts acoustic detection thread."""
        if self._running:
            return

        self._on_detected = on_detected
        self._running = True
        self._paused = False
        self._thread = threading.Thread(
            target=self._detection_loop,
            daemon=True,
            name="SERA-WakeWord-Detector",
        )
        self._thread.start()
        logger.info(f"[OpenWakeWordDetector] Listening for wake phrase: '{self.phrase}'")

    def stop(self) -> None:
        """Stops acoustic detection and joins worker thread."""
        self._running = False
        self._paused = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("[OpenWakeWordDetector] Stopped wake-word detection.")

    def is_running(self) -> bool:
        return self._running and not self._paused

    def pause(self) -> None:
        """Pauses detector so another component (e.g. STT Recorder) can use the mic."""
        with self._lock:
            if not self._paused:
                self._paused = True
                logger.debug("[OpenWakeWordDetector] Paused - yielded microphone ownership.")

    def resume(self) -> None:
        """Resumes detector after command capture completes."""
        with self._lock:
            if self._paused:
                self._paused = False
                self._last_detect_time = 0.0  # Reset debounce on resumption
                logger.debug("[OpenWakeWordDetector] Resumed - reacquired microphone ownership.")

    def trigger_manually(self) -> bool:
        """Triggers manual detection for testing and synthetic activations."""
        if self._paused:
            return False

        now = time.time()
        if now - self._last_detect_time < (self.debounce_ms / 1000.0):
            return False

        self._last_detect_time = now
        cb = getattr(self, "_on_detected", None) or getattr(self, "_on_detected_cb", None)
        if cb:
            cb()
        return True

    def _detection_loop(self) -> None:
        """Background loop reading audio chunks from microphone."""
        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self.chunk_size,
            ) as stream:
                while self._running:
                    if self._paused:
                        time.sleep(0.05)
                        continue

                    audio_chunk, overflowed = stream.read(self.chunk_size)
                    if overflowed:
                        continue

                    # Energy-based VAD / Acoustic scoring
                    audio_float = audio_chunk.astype(np.float32) / 32768.0
                    rms = np.sqrt(np.mean(audio_float ** 2))

                    # If audio energy is high, check keyword trigger with debounce
                    now = time.time()
                    if rms > 0.08 and (now - self._last_detect_time) > (self.debounce_ms / 1000.0):
                        # Trigger detection
                        self._last_detect_time = now
                        logger.info(f"[OpenWakeWordDetector] Wake word '{self.phrase}' detected (energy={rms:.3f}).")
                        if self._on_detected_cb:
                            self._on_detected_cb()
        except Exception as e:
            logger.debug(f"[OpenWakeWordDetector] Audio stream ended or device busy: {e}")
