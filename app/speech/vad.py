import numpy as np

class VoiceActivityDetector:
    """Energy-based and threshold-based Voice Activity Detection (VAD)."""

    def __init__(self, energy_threshold: float = 0.025):
        self.energy_threshold = energy_threshold

    def calculate_energy(self, audio_chunk: np.ndarray) -> float:
        """Calculates RMS energy of audio buffer."""
        if len(audio_chunk) == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(audio_chunk))))

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """Returns True if the audio chunk exceeds energy threshold."""
        return self.calculate_energy(audio_chunk) >= self.energy_threshold
