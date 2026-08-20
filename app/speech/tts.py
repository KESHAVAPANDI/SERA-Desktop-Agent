import io
import os
import sys
import unicodedata
import warnings

import sounddevice as sd
from dotenv import load_dotenv
from fishaudio import FishAudio
from fishaudio.types.tts import TTSConfig
from scipy.io.wavfile import WavFileWarning, read as read_wav

warnings.filterwarnings("ignore", category=WavFileWarning)

load_dotenv()

# Ensure Windows stdout handles UTF-8
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def sanitize_text_for_voice(text: str) -> str:
    """Normalizes unicode whitespace, dashes, and smart quotes for reliable speech and console output."""
    if not text:
        return ""
    normalized = (
        text.replace("\u202f", " ")
        .replace("\u00a0", " ")
        .replace("\u200b", "")
        .replace("\u2013", "-")
        .replace("\u2014", "--")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    return normalized


class FishTTS:

    def __init__(
        self,
        model: str = "s2-pro",
        reference_id: str | None = None,
    ):

        api_key = os.getenv(
            "FISH_API_KEY"
        )

        if not api_key:

            raise RuntimeError(
                "FISH_API_KEY is missing "
                "from .env"
            )

        self.client = FishAudio(
            api_key=api_key
        )

        self.model = model

        self.reference_id = (
            reference_id
            or os.getenv(
                "FISH_REFERENCE_ID"
            )
        )

        if not self.reference_id:

            raise RuntimeError(
                "FISH_REFERENCE_ID is missing. "
                "Choose a Fish Audio voice and "
                "add its ID to .env."
            )

    def speak(
        self,
        text: str,
    ):

        if not text or not text.strip():
            return

        cleaned_text = sanitize_text_for_voice(text)

        try:
            print(f"\n[SERA TTS] {cleaned_text}")
        except Exception:
            print(f"\n[SERA TTS] {cleaned_text.encode('ascii', errors='ignore').decode('ascii')}")

        try:
            audio = self.client.tts.convert(
                text=cleaned_text,
                model=self.model,
                reference_id=self.reference_id,
                format="wav",
                config=TTSConfig(
                    temperature=0.3,
                    top_p=0.7,
                ),
            )

            rate, data = read_wav(io.BytesIO(audio))
            sd.play(data, rate)
            sd.wait()
        except Exception as error:
            print(f"[SERA TTS ERROR] {error}")