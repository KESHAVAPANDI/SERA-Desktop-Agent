"""
Offline Validation Test for Unified Semantic Interpreter (Phase 3A-D).
Validates that Qwen3.5-4B via Ollama operates strictly offline with zero external network access.
"""

import socket
import pytest
from app.core.semantic.interpreter import SemanticInterpreter
from app.core.semantic.schema import CompactSemanticContext


@pytest.fixture(autouse=True)
def enforce_strictly_offline(monkeypatch):
    """
    Blocks all non-localhost network connections at the OS socket level.
    Any attempt to reach an external server (e.g. Gemini, OpenAI, Google) will immediately raise.
    Only 127.0.0.1 / localhost connections to Ollama are allowed.
    """
    orig_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0]
        # Resolve localhost names if needed
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ConnectionRefusedError(
                f"[OFFLINE ENFORCEMENT] External network connection to {address} was blocked!"
            )
        return orig_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


@pytest.mark.asyncio
async def test_offline_semantic_interpretation_open_app():
    """Verify standard application launch intent works with external internet blocked."""
    interpreter = SemanticInterpreter(timeout=20.0)
    intent = await interpreter.interpret_async("Launch Google Chrome please.")
    
    assert intent is not None
    assert intent.intent == "open_application"
    assert intent.target is not None
    assert "chrome" in intent.target.value.lower()
    assert intent.confidence >= 0.5


@pytest.mark.asyncio
async def test_offline_semantic_interpretation_contextual_reference():
    """Verify contextual reference resolution works with external internet blocked."""
    interpreter = SemanticInterpreter(timeout=20.0)
    ctx = CompactSemanticContext(
        utterance="Open the first result.",
        active_browser="chrome",
        last_verified_action="youtube_search",
        relevant_entities=[
            {"ordinal": 1, "title": "Top Video", "url": "https://youtube.com/watch?v=123"}
        ]
    )
    intent = await interpreter.interpret_async("Open the first result.", context=ctx)
    
    assert intent is not None
    assert intent.intent in ("open_reference", "open_application")
    assert intent.reference is not None
    assert intent.reference.ordinal == 1
    assert intent.reference.type == "search_result"
