import asyncio
import io
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.router import ModelRouter, RoleCandidate, create_model_router_from_config
from app.models.llm import create_embedding_provider, create_provider
from app.models.llm.base import LLMProvider, LLMResponse, ToolCall
from app.models.llm.embeddings import MistralEmbeddingProvider
from app.models.llm.health import ModelHealthRegistry, ProviderHealth, ProviderHealthStatus
from app.models.llm.latency import ProviderLatencyMetrics


def make_mock_provider(
    name: str,
    model: str,
    text_resp: str = "mock output",
    tool_calls: list | None = None,
    caps: dict | None = None,
    fail_with: Exception | None = None,
) -> LLMProvider:
    prov = MagicMock(spec=LLMProvider)
    prov.provider_name = name
    prov.model = model
    prov.capabilities.return_value = caps or {
        "text": True,
        "reasoning": True,
        "tool_calling": True,
        "structured_output": True,
        "streaming": True,
        "vision": False,
        "embeddings": False,
        "audio": False,
    }
    if fail_with:
        prov.generate = AsyncMock(side_effect=fail_with)

        async def _mock_fail_stream(*args, **kwargs):
            raise fail_with
            yield "never"

        prov.stream = _mock_fail_stream
    else:
        resp = LLMResponse(
            text=text_resp,
            tool_calls=tool_calls or [],
            provider=name,
            model=model,
        )
        prov.generate = AsyncMock(return_value=resp)

        async def _mock_stream(*args, **kwargs):
            for token in text_resp.split(" "):
                yield token + " "

        prov.stream = _mock_stream
    return prov


class TestPhase44Routing(unittest.IsolatedAsyncioTestCase):
    """Comprehensive test suite for Phase 4.4 production model routing and health failover."""

    def test_01_provider_latency_metrics_data_model(self):
        metrics = ProviderLatencyMetrics(
            provider="mistral",
            model="mistral-small-latest",
            role="fast",
            request_latency_ms=120.0,
            ttft_ms=145.0,
            total_ms=380.0,
            success=True,
            tokens_count=42,
        )
        d = metrics.to_dict()
        self.assertEqual(d["provider"], "mistral")
        self.assertEqual(d["model"], "mistral-small-latest")
        self.assertEqual(d["ttft_ms"], 145.0)
        self.assertTrue(d["success"])

    def test_02_model_health_registry_isolation(self):
        reg = ModelHealthRegistry()

        # Groq GPT-OSS hits 429
        reg.record_failure("groq", "openai/gpt-oss-120b", "Rate limit exceeded 429", status_code=429, retry_after=30.0)
        self.assertFalse(reg.is_model_available("groq", "openai/gpt-oss-120b"))
        self.assertEqual(reg.get_health("groq", "openai/gpt-oss-120b").status, ProviderHealthStatus.RATE_LIMITED)
        self.assertGreater(reg.get_cooldown_remaining_s("groq", "openai/gpt-oss-120b"), 0.0)

        # Groq Qwen Vision remains HEALTHY! (Model-level isolation)
        self.assertTrue(reg.is_model_available("groq", "qwen/qwen3.6-27b"))
        self.assertEqual(reg.get_health("groq", "qwen/qwen3.6-27b").status, ProviderHealthStatus.HEALTHY)

    async def test_03_primary_reasoning_selection(self):
        p_groq = make_mock_provider("groq", "openai/gpt-oss-120b", text_resp="Groq reasoning")
        p_mistral = make_mock_provider("mistral", "mistral-large-latest", text_resp="Mistral reasoning")

        router = ModelRouter(
            role_chains={
                "reasoning": [
                    RoleCandidate("groq", "openai/gpt-oss-120b", p_groq, "reasoning"),
                    RoleCandidate("mistral", "mistral-large-latest", p_mistral, "reasoning"),
                ]
            }
        )

        resp, candidate = await router.generate_with_role(
            role="reasoning",
            messages=[{"role": "user", "content": "Explain relativity"}],
        )
        self.assertEqual(candidate.provider_name, "groq")
        self.assertEqual(resp.text, "Groq reasoning")
        p_groq.generate.assert_called_once()
        p_mistral.generate.assert_not_called()

    async def test_04_reasoning_failover_on_429(self):
        p_groq = make_mock_provider("groq", "openai/gpt-oss-120b", fail_with=RuntimeError("HTTP 429 Rate limit exceeded"))
        p_mistral = make_mock_provider("mistral", "mistral-large-latest", text_resp="Mistral Large response")
        p_mistral_med = make_mock_provider("mistral", "mistral-medium-3.5", text_resp="Mistral Medium response")

        health_reg = ModelHealthRegistry()
        router = ModelRouter(
            role_chains={
                "reasoning": [
                    RoleCandidate("groq", "openai/gpt-oss-120b", p_groq, "reasoning"),
                    RoleCandidate("mistral", "mistral-large-latest", p_mistral, "reasoning"),
                    RoleCandidate("mistral", "mistral-medium-3.5", p_mistral_med, "reasoning"),
                ]
            },
            health_registry=health_reg,
        )

        resp, candidate = await router.generate_with_role(
            role="reasoning",
            messages=[{"role": "user", "content": "Explain gravity"}],
        )

        self.assertEqual(candidate.provider_name, "mistral")
        self.assertEqual(candidate.model_name, "mistral-large-latest")
        self.assertEqual(resp.text, "Mistral Large response")

        # Verify Groq is now marked RATE_LIMITED and will be skipped on subsequent turn
        self.assertFalse(health_reg.is_model_available("groq", "openai/gpt-oss-120b"))

        # Subsequent call skips Groq without calling generate()
        p_groq.generate.reset_mock()
        p_mistral.generate.reset_mock()

        resp2, candidate2 = await router.generate_with_role(
            role="reasoning",
            messages=[{"role": "user", "content": "Follow-up question"}],
        )
        p_groq.generate.assert_not_called()
        p_mistral.generate.assert_called_once()
        self.assertEqual(candidate2.model_name, "mistral-large-latest")

    async def test_05_primary_fast_text_selection(self):
        p_mistral_small = make_mock_provider("mistral", "mistral-small-latest", text_resp="The time is 5 PM.")
        router = ModelRouter(
            role_chains={
                "fast": [
                    RoleCandidate("mistral", "mistral-small-latest", p_mistral_small, "fast"),
                ]
            }
        )

        resp, candidate = await router.generate_with_role(
            role="fast",
            messages=[{"role": "user", "content": "What time is it?"}],
        )
        self.assertEqual(candidate.provider_name, "mistral")
        self.assertEqual(candidate.model_name, "mistral-small-latest")
        self.assertEqual(resp.text, "The time is 5 PM.")

    async def test_06_desktop_tool_calling_role(self):
        tool_call = ToolCall(id="call_1", name="click_ui_element", arguments={"target_name": "File", "control_type": "menu_item"})
        p_codestral = make_mock_provider("mistral", "codestral-latest", tool_calls=[tool_call])

        router = ModelRouter(
            role_chains={
                "desktop": [
                    RoleCandidate("mistral", "codestral-latest", p_codestral, "desktop"),
                ]
            }
        )

        resp, candidate = await router.generate_with_role(
            role="desktop",
            messages=[{"role": "user", "content": "Click the File menu in Notepad"}],
        )
        self.assertEqual(candidate.provider_name, "mistral")
        self.assertEqual(candidate.model_name, "codestral-latest")
        self.assertTrue(resp.has_tool_calls)
        self.assertEqual(resp.tool_calls[0].name, "click_ui_element")

    async def test_07_vision_role_and_capability_filtering(self):
        p_text_only = make_mock_provider("mistral", "mistral-small-latest", caps={"text": True, "vision": False})
        p_qwen_vis = make_mock_provider("groq", "qwen/qwen3.6-27b", caps={"text": True, "vision": True}, text_resp="I see Google Chrome browser.")

        router = ModelRouter(
            role_chains={
                "vision": [
                    RoleCandidate("mistral", "mistral-small-latest", p_text_only, "vision"),
                    RoleCandidate("groq", "qwen/qwen3.6-27b", p_qwen_vis, "vision"),
                ]
            }
        )

        # When image is passed, p_text_only should be skipped due to lack of vision capability
        resp, candidate = await router.generate_with_role(
            role="vision",
            messages=[{"role": "user", "content": "What is on the screen?"}],
            images=[b"fake_image_bytes"],
        )
        self.assertEqual(candidate.provider_name, "groq")
        self.assertEqual(candidate.model_name, "qwen/qwen3.6-27b")
        p_text_only.generate.assert_not_called()
        p_qwen_vis.generate.assert_called_once()

    async def test_08_unavailable_payment_required_skipped(self):
        p_cerebras = make_mock_provider("cerebras", "gpt-oss-120b", fail_with=RuntimeError("HTTP 402 Payment required"))
        p_groq = make_mock_provider("groq", "openai/gpt-oss-120b", text_resp="Groq fallback output")

        health_reg = ModelHealthRegistry()
        router = ModelRouter(
            role_chains={
                "reasoning": [
                    RoleCandidate("cerebras", "gpt-oss-120b", p_cerebras, "reasoning"),
                    RoleCandidate("groq", "openai/gpt-oss-120b", p_groq, "reasoning"),
                ]
            },
            health_registry=health_reg,
        )

        resp, candidate = await router.generate_with_role(
            role="reasoning",
            messages=[{"role": "user", "content": "Hello"}],
        )
        self.assertEqual(candidate.provider_name, "groq")
        self.assertEqual(health_reg.get_health("cerebras", "gpt-oss-120b").status, ProviderHealthStatus.AUTH_ERROR)

    def test_09_backward_compatible_config_parsing(self):
        cfg = {
            "roles": {
                "reasoning": {
                    "primary": {"provider": "groq", "model": "openai/gpt-oss-120b"},
                    "fallbacks": [{"provider": "mistral", "model": "mistral-large-latest"}],
                },
                "fast": {
                    "primary": {"provider": "mistral", "model": "mistral-small-latest"},
                },
            },
            "models": {
                "fallback": {"provider": "openrouter", "model": "openrouter/free"},
            },
        }

        router = create_model_router_from_config(cfg)
        self.assertTrue(router.has_role("reasoning"))
        self.assertTrue(router.has_role("fast"))
        self.assertTrue(router.has_role("fallback"))

        candidates = router.get_role_candidates("reasoning")
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].provider_name, "groq")
        self.assertEqual(candidates[1].provider_name, "mistral")

    def test_10_mistral_embeddings_provider(self):
        embed_prov = create_embedding_provider("mistral", model="mistral-embed")
        self.assertIsInstance(embed_prov, MistralEmbeddingProvider)
        self.assertEqual(embed_prov.model, "mistral-embed")

    def test_11_refresh_provider_health(self):
        health_reg = ModelHealthRegistry()
        health_reg.record_success("groq", "openai/gpt-oss-120b", 250.0)
        health_reg.record_failure("cerebras", "gpt-oss-120b", "Payment required 402", status_code=402)

        router = ModelRouter(health_registry=health_reg)
        summary = router.refresh_provider_health()

        self.assertIn("groq:openai/gpt-oss-120b", summary)
        self.assertEqual(summary["groq:openai/gpt-oss-120b"]["status"], "HEALTHY")
        self.assertIn("cerebras:gpt-oss-120b", summary)
        self.assertEqual(summary["cerebras:gpt-oss-120b"]["status"], "AUTH_ERROR")

    async def test_12_streaming_with_role_and_failover(self):
        p_fail = make_mock_provider("groq", "openai/gpt-oss-120b", fail_with=RuntimeError("Stream 429"))
        p_ok = make_mock_provider("mistral", "mistral-small-latest", text_resp="Hello world stream")

        router = ModelRouter(
            role_chains={
                "fast": [
                    RoleCandidate("groq", "openai/gpt-oss-120b", p_fail, "fast"),
                    RoleCandidate("mistral", "mistral-small-latest", p_ok, "fast"),
                ]
            }
        )

        tokens = []
        async for token, cand in router.stream_with_role("fast", messages=[{"role": "user", "content": "hi"}]):
            tokens.append(token)
            self.assertEqual(cand.provider_name, "mistral")

        self.assertGreater(len(tokens), 0)


if __name__ == "__main__":
    unittest.main()
