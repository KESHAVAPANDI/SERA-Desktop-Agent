import os
from dotenv import load_dotenv
from app.models.tts.base import BaseTTSProvider

load_dotenv()

class FishAudioTTS(BaseTTSProvider):
    """Fish Audio API Text-To-Speech implementation."""

    def __init__(self, api_key: str = None, default_model: str = "s2.1-pro-free"):
        self.api_key = api_key or os.getenv("FISH_API_KEY")
        self.default_model = default_model
        self.client = None

        if self.api_key:
            try:
                from fishaudio import FishAudio
                self.client = FishAudio(api_key=self.api_key)
            except Exception:
                self.client = None

    def is_available(self) -> bool:
        return self.client is not None

    def speak(self, text: str, output_path: str = None, voice_model: str = None) -> bytes:
        if not self.is_available():
            raise RuntimeError("Fish Audio client is not available or FISH_API_KEY is missing.")

        model_name = voice_model or self.default_model
        audio_bytes = self.client.tts.convert(
            text=text,
            model=model_name,
            format="mp3"
        )

        if output_path:
            with open(output_path, "wb") as f:
                f.write(audio_bytes)

        return audio_bytes
