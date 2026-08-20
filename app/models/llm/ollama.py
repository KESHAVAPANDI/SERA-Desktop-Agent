import urllib.request
import json
from app.models.llm.base import BaseLLMProvider

class OllamaLLM(BaseLLMProvider):
    """Local Ollama LLM Provider integration."""

    def __init__(self, host: str = "http://localhost:11434", model_name: str = "llama3"):
        self.host = host.rstrip("/")
        self.model_name = model_name

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.host}/api/tags")
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    def generate_response(self, prompt: str, system_instruction: str = None, context: list = None) -> str:
        if not self.is_available():
            raise RuntimeError("Ollama local service is not reachable.")
        return f"[Ollama Response for: '{prompt}']"
