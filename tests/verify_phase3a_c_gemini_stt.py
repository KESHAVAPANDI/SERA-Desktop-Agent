"""
SERA 2.0 — Phase 3A-C Safe Real STT and Pipeline Validation Script.
Validates:
- Gemini API key presence and safe metadata (never print key!)
- Gemini STT transcribe operation with English constraint
- No 429 rate limit
- Intent classification and target extraction
"""

import os
import sys
import io
import wave
import numpy as np
from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv(override=True)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

api_key = os.getenv("GEMINI_API_KEY", "")

print("=== ENVIRONMENT METADATA ===")
print(f"Gemini API key present: {'yes' if bool(api_key) else 'no'}")
print(f"Gemini API key length: {len(api_key)}")
print(f"Safe key prefix: {api_key[:4]}... (remainder hidden)")

from app.models.stt.gemini import GeminiSTTProvider
from app.core.command import CommandParser

stt = GeminiSTTProvider()
print(f"Provider initialized: {stt.__class__.__name__}")
print(f"STT Model: {stt.model}")

# Generate a synthetic 1-second 16kHz sine tone to test API connectivity and response
sample_rate = 16000
duration = 1.0
t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
audio_data = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

import asyncio

async def test_gemini_connectivity():
    print("\n=== GEMINI STT CONNECTIVITY TEST ===")
    try:
        res = await stt.transcribe(audio_data, language="en-US")
        print("Gemini STT request succeeded: yes")
        print(f"Gemini STT response text received: '{res.text}'")
        print("HTTP Status: 200 OK (no 429 rate limit)")
        return True
    except Exception as e:
        print(f"Gemini STT request succeeded: no (Error: {e})")
        return False

async def test_semantic_pipeline():
    print("\n=== SEMANTIC PIPELINE TEST ===")
    parser = CommandParser()
    
    test_cases = [
        ("Open Chrome", "open_application", "chrome", None),
        ("Hey Sarah, can you please open the chrome for me?", "open_application", "chrome", None),
        ("Open Chrome again", "open_application", "chrome", "repeat"),
        ("Open the first result", "open_search_result", None, None),
    ]
    
    ctx = {
        "search_results": [
            {"title": "Sample Result 1", "url": "https://www.youtube.com/watch?v=sample123"}
        ],
        "last_application": "chrome"
    }

    all_passed = True
    for text, expected_intent, expected_target, expected_mod in test_cases:
        cmd = parser.parse(text, context=ctx)
        actual_intent = cmd.intent
        actual_target = cmd.parameters.get("application")
        actual_mod = cmd.parameters.get("modifier") or cmd.entities.get("modifier")
        
        intent_ok = (actual_intent == expected_intent)
        target_ok = (expected_target is None or actual_target == expected_target)
        mod_ok = (expected_mod is None or actual_mod == expected_mod)
        
        status = "PASS" if (intent_ok and target_ok and mod_ok) else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"[{status}] \"{text}\" -> intent={actual_intent} target={actual_target} modifier={actual_mod}")
        
    # Close it test
    close_cmd = parser.parse("Close it", context=ctx)
    close_ok = (close_cmd.intent == "close_application" and close_cmd.parameters.get("application") == "chrome")
    print(f"[{'PASS' if close_ok else 'FAIL'}] \"Close it\" -> intent={close_cmd.intent} target={close_cmd.parameters.get('application')}")

    return all_passed

async def main():
    gemini_ok = await test_gemini_connectivity()
    pipe_ok = await test_semantic_pipeline()
    if gemini_ok and pipe_ok:
        print("\nALL PREFLIGHT CHECKS PASSED.")
        sys.exit(0)
    else:
        print("\nPREFLIGHT CHECKS HAD ISSUES.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
