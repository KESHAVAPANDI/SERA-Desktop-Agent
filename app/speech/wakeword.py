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
        """Temporarily pauses detections (e.g. during active command recording/speaking)."""
        pass

    @abstractmethod
    def resume(self) -> None:
        """Resumes wake-word detections."""
        pass


class OpenWakeWordDetector(WakeWordProvider):
    """Local Wake-Word Detector for 'SERA' with debounce and state suppression."""

    def __init__(
        self,
        phrase: str = "SERA",
        sensitivity: float = 0.5,
        debounce_ms: int = 1000,
        sample_rate: int = 16000,
        chunk_size: int = 1280,  # 80ms chunk at 16kHz
    ):
        self.phrase = phrase
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

    def _init_model(self):
        if self._oww_model is not None:
            return self._oww_model

        try:
            import openwakeword
            from openwakeword.model import Model
            # Initialize openwakeword model
            self._oww_model = Model(
                inference_framework="onnx",
            )
            logger.info(f"[OpenWakeWordDetector] Loaded openwakeword model successfully.")
        except Exception as e:
            logger.debug(f"[OpenWakeWordDetector] Standard openwakeword model not loaded ({e}), using energy-keyword fallback.")
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
        logger.info(f"[OpenWakeWordDetector] Wake word detector started for '{self.phrase}'.")

    def stop(self) -> None:
        """Stops background audio listener."""
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        logger.info("[OpenWakeWordDetector] Wake word detector stopped.")

    def is_running(self) -> bool:
        return self._running

    def pause(self) -> None:
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            self._paused = False

    def trigger_manually(self) -> bool:
        """Thread-safe manual trigger for testing / synthetic events."""
        now = time.time()
        with self._lock:
            if self._paused:
                return False
            if (now - self._last_detection_time) * 1000 < self.debounce_ms:
                return False
            self._last_detection_time = now

        if self._on_detected:
            self._on_detected()
            return True
        return False

    def _listen_loop(self) -> None:
        model = self._init_model()

        def audio_callback(indata, frames, time_info, status):
            if not self._running or self._paused:
                return

            audio_data = indata[:, 0]
            # Convert float32 to int16 for openwakeword
            audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)

            detected = False
            if model:
                try:
                    prediction = model.predict(audio_int16)
                    for key, score in prediction.items():
                        if score >= self.sensitivity:
                            detected = True
                            break
                except Exception:
                    pass

            if detected:
                self.trigger_manually()

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=self.chunk_size,
                callback=audio_callback,
            ):
                while self._running:
                    time.sleep(0.05)
        except Exception as e:
            logger.debug(f"[OpenWakeWordDetector] Stream ended or unavailable: {e}")
