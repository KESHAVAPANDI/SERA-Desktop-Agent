from abc import ABC, abstractmethod
import logging
import threading
import time
from typing import Callable
import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


class WakeWordProvider(ABC):
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


class OpenWakeWordDetector(WakeWordProvider):
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
        self._on_detected: Callable[[], None] | None = None
        self._last_detection_time = 0.0
        self._lock = threading.Lock()
        self._oww_model = None

        # Energy & acoustic sliding window for reliable local detection
        self._buffer: list[np.ndarray] = []
        self._buffer_max_chunks = int(2.0 * sample_rate / chunk_size)  # 2.0s buffer

    def _init_model(self):
        if self._oww_model is not None:
            return self._oww_model

        try:
            import openwakeword
            from openwakeword.model import Model
            # Initialize openwakeword with onnx inference
            self._oww_model = Model(
                inference_framework="onnx",
            )
            logger.info(f"[OpenWakeWordDetector] Loaded openwakeword ONNX model successfully.")
        except Exception as e:
            logger.debug(f"[OpenWakeWordDetector] OpenWakeWord ONNX model initialization note: {e}")
            self._oww_model = None
        return self._oww_model

    def start(self, on_detected: Callable[[], None]) -> None:
        """Starts the background audio listener thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._paused = False
            self._on_detected = on_detected

        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="WakeWordListener")
        self._thread.start()
        logger.info(f"[OpenWakeWordDetector] Wake word detector online for '{self.phrase}'.")

    def stop(self) -> None:
        """Stops background audio listener."""
        with self._lock:
            self._running = False
            self._paused = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        logger.info("[OpenWakeWordDetector] Wake word detector stopped.")

    def is_running(self) -> bool:
        return self._running and not self._paused

    def pause(self) -> None:
        """Temporarily pauses detector and signals thread to yield microphone."""
        with self._lock:
            self._paused = True
        logger.debug("[OpenWakeWordDetector] Paused — microphone yielded to recorder.")

    def resume(self) -> None:
        """Resumes detector and reacquires microphone stream."""
        with self._lock:
            self._paused = False
        logger.debug("[OpenWakeWordDetector] Resumed — listening for wake word.")

    def trigger_manually(self) -> bool:
        """Thread-safe trigger for wake-word activation."""
        now = time.time()
        with self._lock:
            if self._paused:
                return False
            if (now - self._last_detection_time) * 1000 < self.debounce_ms:
                return False
            self._last_detection_time = now

        if self._on_detected:
            logger.info(f"[OpenWakeWordDetector] Wake word '{self.phrase}' triggered!")
            self._on_detected()
            return True
        return False

    def _listen_loop(self) -> None:
        """Audio streaming loop with dynamic mic yielding when paused."""
        model = self._init_model()

        while self._running:
            if self._paused:
                time.sleep(0.05)
                continue

            try:
                # Open audio stream while not paused
                with sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="float32",
                    blocksize=self.chunk_size,
                ) as stream:
                    while self._running and not self._paused:
                        data, overflowed = stream.read(self.chunk_size)
                        if self._paused or not self._running:
                            break

                        audio_data = data[:, 0]
                        # Compute energy RMS
                        rms = float(np.sqrt(np.mean(audio_data ** 2)))

                        # Check prediction if energy exceeds noise floor
                        detected = False
                        if rms > 0.015:
                            audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)

                            if model:
                                try:
                                    prediction = model.predict(audio_int16)
                                    for k, score in prediction.items():
                                        if score >= self.sensitivity:
                                            detected = True
                                            break
                                except Exception:
                                    pass

                        if detected:
                            self.trigger_manually()
                            # Pause immediately to yield mic for command recording
                            self.pause()
                            break

            except Exception as e:
                # Stream unavailable or yielding to another audio capture
                time.sleep(0.1)
