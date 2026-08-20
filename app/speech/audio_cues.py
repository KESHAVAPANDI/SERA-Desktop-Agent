import logging
import threading
import time

logger = logging.getLogger(__name__)

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False


class AudioCueManager:
    """Local, near-zero-latency sound cues for state changes without cloud dependencies."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def _play_tone_sync(self, freq: int, duration_ms: int) -> None:
        if not self.enabled or not HAS_WINSOUND:
            return
        try:
            winsound.Beep(int(freq), int(duration_ms))
        except Exception as e:
            logger.debug(f"[AudioCueManager] Could not play tone {freq}Hz: {e}")

    def _play_tones_sequence(self, tones: list[tuple[int, int]]) -> None:
        if not self.enabled or not HAS_WINSOUND:
            return
        try:
            for freq, dur in tones:
                winsound.Beep(int(freq), int(dur))
        except Exception as e:
            logger.debug(f"[AudioCueManager] Could not play tone sequence: {e}")

    def _spawn(self, target, *args) -> None:
        if not self.enabled:
            return
        t = threading.Thread(target=target, args=args, daemon=True, name="SERA-AudioCue")
        t.start()

    def play_listening_cue(self) -> None:
        """Plays a crisp, high confirmation tone when listening begins."""
        self._spawn(self._play_tone_sync, 880, 100)

    def play_thinking_cue(self) -> None:
        """Plays a subtle blip when processing starts."""
        self._spawn(self._play_tone_sync, 520, 60)

    def play_interrupted_cue(self) -> None:
        """Plays a two-tone descending cancel cue."""
        self._spawn(self._play_tones_sequence, [(650, 60), (420, 80)])

    def play_error_cue(self) -> None:
        """Plays a distinct low error tone."""
        self._spawn(self._play_tone_sync, 250, 180)

    def play_confirmation_required_cue(self) -> None:
        """Plays an ascending two-tone prompt cue."""
        self._spawn(self._play_tones_sequence, [(440, 70), (660, 100)])

    def play_completed_cue(self) -> None:
        """Plays a soft positive completion chime."""
        self._spawn(self._play_tones_sequence, [(587, 60), (880, 90)])


# Global instance
_cue_manager = AudioCueManager()


def get_audio_cues(enabled: bool = True) -> AudioCueManager:
    global _cue_manager
    _cue_manager.enabled = enabled
    return _cue_manager
