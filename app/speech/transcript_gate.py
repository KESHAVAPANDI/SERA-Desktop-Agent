from dataclasses import dataclass
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Known single-word or short commands that must always remain valid
VALID_SHORT_COMMANDS = {
    "mute",
    "unmute",
    "stop",
    "cancel",
    "time",
    "date",
    "battery",
    "wifi",
    "bluetooth",
    "volume",
    "brightness",
    "help",
    "status",
    "yes",
    "no",
    "confirm",
    "reject",
}

# Obvious noise, fillers, or hallucinated Whisper fragments that must be rejected
REJECTED_FILLERS = {
    "um",
    "uh",
    "uhh",
    "umm",
    "erm",
    "ah",
    "ahh",
    "oh",
    "from",
    "the",
    "a",
    "an",
    "yeah",
    "yep",
    "nope",
    "so",
    "and",
    "to",
    "of",
    "in",
    "for",
    "by",
    "with",
    "thank you. bye. bye. bye.",
    "thank you, bye, bye, bye",
    "bye bye",
    "i'm home",
    "you",
    "it",
}


@dataclass
class QualityDecision:
    accepted: bool
    reason: str
    confidence: float
    is_filler: bool = False


class TranscriptQualityGate:
    """Quality gate validating transcripts before passing them to reasoning or cloud LLMs."""

    def __init__(
        self,
        min_words: int = 1,
        max_no_speech_prob: float = 0.70,
        min_avg_logprob: float = -1.5,
    ):
        self.min_words = min_words
        self.max_no_speech_prob = max_no_speech_prob
        self.min_avg_logprob = min_avg_logprob

    def evaluate(
        self,
        transcript: Any,
        no_speech_prob: float | None = None,
        avg_logprob: float | None = None,
        duration_s: float | None = None,
    ) -> QualityDecision:
        """Evaluates whether transcript should proceed to LLM."""
        if hasattr(transcript, "text"):
            raw_text = str(transcript.text)
            if no_speech_prob is None:
                no_speech_prob = getattr(transcript, "no_speech_prob", None)
            if avg_logprob is None:
                avg_logprob = getattr(transcript, "avg_logprob", None)
            if duration_s is None:
                duration_s = getattr(transcript, "duration", None)
        else:
            raw_text = str(transcript) if transcript is not None else ""

        if not raw_text or not raw_text.strip():
            return QualityDecision(
                accepted=False,
                reason="Empty or whitespace transcript",
                confidence=0.0,
            )

        clean = raw_text.strip().lower()
        # Remove punctuation for analysis
        normalized = re.sub(r"[^\w\s]", "", clean).strip()
        words = normalized.split()

        if not words:
            return QualityDecision(
                accepted=False,
                reason="No valid words in transcript",
                confidence=0.0,
            )

        # 1. Check known single-word valid commands
        if normalized in VALID_SHORT_COMMANDS or (len(words) == 1 and words[0] in VALID_SHORT_COMMANDS):
            return QualityDecision(
                accepted=True,
                reason="Matched known valid command phrase",
                confidence=0.98,
            )

        # 2. Check known filler words / noise fragments
        if normalized in REJECTED_FILLERS or clean in REJECTED_FILLERS:
            return QualityDecision(
                accepted=False,
                reason=f"Rejected known filler word or noise fragment: '{clean}'",
                confidence=0.1,
                is_filler=True,
            )

        # 3. If single word and not in known short commands, check length
        if len(words) == 1:
            if len(words[0]) <= 3 and words[0] not in VALID_SHORT_COMMANDS:
                return QualityDecision(
                    accepted=False,
                    reason=f"Single short non-command word: '{words[0]}'",
                    confidence=0.2,
                    is_filler=True,
                )

        # 4. Whisper metadata checks
        if no_speech_prob is not None and no_speech_prob > self.max_no_speech_prob:
            return QualityDecision(
                accepted=False,
                reason=f"High no-speech probability ({no_speech_prob:.2f} > {self.max_no_speech_prob})",
                confidence=float(1.0 - no_speech_prob),
            )

        if avg_logprob is not None and avg_logprob < self.min_avg_logprob and len(words) < 3:
            return QualityDecision(
                accepted=False,
                reason=f"Low transcription confidence ({avg_logprob:.2f} < {self.min_avg_logprob})",
                confidence=0.3,
            )

        # 5. Check repetition loop hallucinations (e.g. "Bye. Bye. Bye. Bye.")
        if len(words) >= 4 and len(set(words)) == 1:
            return QualityDecision(
                accepted=False,
                reason=f"Repetitive word hallucination: '{words[0]}'",
                confidence=0.1,
                is_filler=True,
            )

        # Accept legitimate speech
        return QualityDecision(
            accepted=True,
            reason="Transcript passed quality criteria",
            confidence=0.95,
        )
