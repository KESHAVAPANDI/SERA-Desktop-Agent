import logging

logger = logging.getLogger(__name__)

class WakeWordDetector:
    """Wake Word Detector service (e.g. 'Hey SERA')."""

    def __init__(self, wake_words: list[str] = None):
        self.wake_words = [w.lower() for w in (wake_words or ["sera", "hey sera", "hello sera"])]

    def check_wake_word(self, text: str) -> bool:
        """Checks if any configured wake word is present in transcribed text."""
        cleaned = text.lower().strip()
        return any(wake_word in cleaned for wake_word in self.wake_words)
