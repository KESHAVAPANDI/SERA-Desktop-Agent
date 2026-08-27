"""
Phase 5D.5 Unit Tests — ResourceStateCache & Adaptive Resource-Aware Preflight Router
Tests quota headroom preflight calculation, composite candidate scoring,
rate-limit tracking, and 4 execution modes without network round-trips.
"""

import pytest
import time
from app.core.resource_cache import ResourceStateCache, ModelResourceEntry
from app.core.router import ModelRouter, RoleCandidate


class DummyProvider:
    def __init__(self, name: str, is_healthy: bool = True, can_tools: bool = True, can_vision: bool = False):
        self.name = name
        self._healthy = is_healthy
        self._can_tools = can_tools
        self._can_vision = can_vision

    def capabilities(self):
        return {
            "text": True,
            "streaming": True,
            "tool_calling": self._can_tools,
            "vision": self._can_vision,
        }

    def is_healthy(self):
        return self._healthy


@pytest.fixture(autouse=True)
def clean_resource_cache():
    """Reset the singleton cache before each test."""
    cache = ResourceStateCache()
    cache.reset()
    yield cache
    cache.reset()


def test_token_estimation():
    cache = ResourceStateCache()
    messages = [
        {"role": "system", "content": "You are a helpful desktop assistant."},
        {"role": "user", "content": "Open Chrome and search for RTX 5090 benchmarks."},
    ]
    # Est words: system ~7 words (10 tokens), user ~8 words (11 tokens) + 256 output = ~277 tokens
    estimated = cache.estimate_request_tokens(messages, expected_output_tokens=256)
    assert 250 <= estimated <= 400


def test_header_parsing_and_metrics_update():
    cache = ResourceStateCache()
    headers = {
        "x-ratelimit-remaining-requests": "450",
        "x-ratelimit-remaining-tokens": "18500",
        "x-ratelimit-limit-tokens": "20000",
        "x-ratelimit-reset-tokens": "2.5s",
    }
    cache.update_from_headers("Groq", "openai/gpt-oss-120b", headers, latency_ms=280.0)

    entry = cache.get_resource_state("Groq", "openai/gpt-oss-120b")
    assert entry.remaining_requests == 450
    assert entry.remaining_tokens == 18500
    assert entry.limit_tokens == 20000
    assert entry.reset_tokens_s == 2.5
    assert entry.recent_latency_ms == 280.0
    assert entry.rate_limit_state == "NORMAL"
    assert entry.is_available is True


def test_record_429_cooldown():
    cache = ResourceStateCache()
    cache.record_429("Groq", "openai/gpt-oss-120b", retry_after=15.0)

    entry = cache.get_resource_state("Groq", "openai/gpt-oss-120b")
    assert entry.rate_limit_state == "RATE_LIMITED"
    assert entry.is_available is False
    assert entry.cooldown_until > time.time()


def test_resource_aware_preflight_excludes_insufficient_quota():
    cache = ResourceStateCache()
    cache.reset()
    # Model 1 has only 100 tokens remaining
    cache.set_resource_state(
        "Groq",
        "openai/gpt-oss-120b",
        remaining_tokens=100,
        remaining_requests=10,
        recent_latency_ms=200.0,
        health="HEALTHY",
    )
    # Model 2 has 50,000 tokens remaining
    cache.set_resource_state(
        "Mistral",
        "mistral-large-2411",
        remaining_tokens=50000,
        remaining_requests=500,
        recent_latency_ms=320.0,
        health="HEALTHY",
    )

    router = ModelRouter()
    p_groq = DummyProvider("Groq", is_healthy=True)
    p_mistral = DummyProvider("Mistral", is_healthy=True)

    cand1 = RoleCandidate("Groq", "openai/gpt-oss-120b", p_groq, role="reasoning")
    cand2 = RoleCandidate("Mistral", "mistral-large-2411", p_mistral, role="reasoning")

    router.register_role_chain("reasoning", [cand1, cand2], mode="RESOURCE_AWARE")

    # Request requiring ~300 tokens
    messages = [{"role": "user", "content": "Analyze system performance and write a full report."}]
    selected, meta, expl = router.select_candidate_preflight("reasoning", messages)

    # Cand 1 should be disqualified before call due to 100 < ~300 tokens
    assert selected == cand2
    assert expl["selected_model"] == "Mistral/mistral-large-2411"
    assert any("Sufficient token headroom" in r or "Preflight" in r for r in expl["reasons"])
    assert len(expl["rejected_candidates"]) >= 1
    assert "Groq/openai/gpt-oss-120b" in expl["rejected_candidates"][0]["model"]
    assert any("Quota headroom insufficient" in r for r in expl["rejected_candidates"][0]["reasons"])
    cache.reset()


def test_four_execution_modes():
    cache = ResourceStateCache()
    router = ModelRouter()

    p_primary = DummyProvider("Groq", is_healthy=True)
    p_secondary = DummyProvider("Mistral", is_healthy=True)

    cand1 = RoleCandidate("Groq", "openai/gpt-oss-120b", p_primary, role="reasoning")
    cand2 = RoleCandidate("Mistral", "mistral-large-2411", p_secondary, role="reasoning")

    # 1. PRIMARY_ONLY Mode
    router.register_role_chain("reasoning", [cand1, cand2], mode="PRIMARY_ONLY")
    sel, meta, expl = router.select_candidate_preflight("reasoning", [{"role": "user", "content": "Hello"}])
    assert sel == cand1
    assert router.get_execution_mode("reasoning") == "PRIMARY_ONLY"

    # 2. FALLBACK_ORDER Mode
    router.set_execution_mode("reasoning", "FALLBACK_ORDER")
    sel, meta, expl = router.select_candidate_preflight("reasoning", [{"role": "user", "content": "Hello"}])
    assert sel == cand1

    # 3. RESOURCE_AWARE Mode
    router.set_execution_mode("reasoning", "RESOURCE_AWARE")
    assert router.get_execution_mode("reasoning") == "RESOURCE_AWARE"

    # 4. CUSTOM Mode
    router.set_execution_mode("reasoning", "CUSTOM")
    assert router.get_execution_mode("reasoning") == "CUSTOM"
