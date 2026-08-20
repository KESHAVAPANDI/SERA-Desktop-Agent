import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.router import ModelRouter
from app.models.llm import create_provider
from app.models.llm.base import LLMResponse, ToolCall
from app.models.llm.cerebras import CerebrasProvider
from app.models.llm.health import ProviderHealth, ProviderHealthStatus
from app.models.llm.mistral import MistralProvider
from app.models.llm.openai_compatible import OpenAICompatibleProvider
from app.models.llm.zai import ZAIProvider


class TestPhase43Providers(unittest.IsolatedAsyncioTestCase):
    """Unit tests for Phase 4.3 Cerebras, Mistral, Z.AI providers, health tracking & routing."""

    def test_01_provider_health_transitions(self):
        health = ProviderHealth()
        self.assertEqual(health.status, ProviderHealthStatus.HEALTHY)
        self.assertTrue(health.is_available())

        # Record 429 Rate Limit
        health.record_failure("Rate limit exceeded", status_code=429, retry_after=30.0)
        self.assertEqual(health.status, ProviderHealthStatus.RATE_LIMITED)
        self.assertFalse(health.is_available())

        # Record Success resets status to HEALTHY
        health.record_success(latency_ms=250.0)
        self.assertEqual(health.status, ProviderHealthStatus.HEALTHY)
        self.assertTrue(health.is_available())
        self.assertEqual(len(health.recent_latencies_ms), 1)

    def test_02_provider_health_auth_and_unavailable(self):
        health = ProviderHealth()
        health.record_failure("Payment required", status_code=402)
        self.assertEqual(health.status, ProviderHealthStatus.AUTH_ERROR)
        self.assertFalse(health.is_available())

        health_unavail = ProviderHealth()
        health_unavail.record_failure("Service unavailable", status_code=503)
        self.assertEqual(health_unavail.status, ProviderHealthStatus.UNAVAILABLE)
        self.assertFalse(health_unavail.is_available())

    def test_03_provider_factory_instantiation(self):
        p_mistral = create_provider("mistral", model="mistral-large-latest")
        self.assertIsInstance(p_mistral, MistralProvider)
        self.assertEqual(p_mistral.model, "mistral-large-latest")
        self.assertTrue(p_mistral.capabilities()["text"])
        self.assertTrue(p_mistral.capabilities()["reasoning"])

        p_cerebras = create_provider("cerebras", model="gpt-oss-120b")
        self.assertIsInstance(p_cerebras, CerebrasProvider)
        self.assertEqual(p_cerebras.model, "gpt-oss-120b")

        p_zai = create_provider("zai", model="glm-5")
        self.assertIsInstance(p_zai, ZAIProvider)
        self.assertEqual(p_zai.model, "glm-5")

    def test_04_mistral_model_capabilities(self):
        p_large = MistralProvider(model="mistral-large-latest")
        caps_large = p_large.capabilities()
        self.assertTrue(caps_large["text"])
        self.assertTrue(caps_large["tool_calling"])
        self.assertTrue(caps_large["reasoning"])
        self.assertFalse(caps_large["embeddings"])

        p_ocr = MistralProvider(model="mistral-ocr-latest")
        caps_ocr = p_ocr.capabilities()
        self.assertTrue(caps_ocr["vision"])

        p_embed = MistralProvider(model="mistral-embed")
        caps_embed = p_embed.capabilities()
        self.assertTrue(caps_embed["embeddings"])

    @patch("httpx.AsyncClient.post")
    async def test_05_openai_compatible_generate_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Hello, I am Mistral.",
                        "tool_calls": None,
                    },
                    "finish_reason": "stop",
                }
            ]
        }
        mock_post.return_value = mock_resp

        provider = OpenAICompatibleProvider(
            provider_name="test_prov",
            base_url="https://api.example.com/v1",
            api_key_env="TEST_API_KEY",
            model="test-model",
        )
        provider._api_key = "mock_key"

        resp = await provider.generate(messages=[{"role": "user", "content": "hi"}])
        self.assertIsInstance(resp, LLMResponse)
        self.assertEqual(resp.text, "Hello, I am Mistral.")
        self.assertEqual(resp.provider, "test_prov")
        self.assertEqual(resp.model, "test-model")
        self.assertEqual(provider.health.status, ProviderHealthStatus.HEALTHY)

    @patch("httpx.AsyncClient.post")
    async def test_06_openai_compatible_tool_call_parsing(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "function": {
                                    "name": "get_current_time",
                                    "arguments": '{"timezone": "UTC"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }
        mock_post.return_value = mock_resp

        provider = OpenAICompatibleProvider(
            provider_name="test_prov",
            base_url="https://api.example.com/v1",
            api_key_env="TEST_API_KEY",
            model="test-model",
        )
        provider._api_key = "mock_key"

        resp = await provider.generate(messages=[{"role": "user", "content": "what time is it?"}])
        self.assertTrue(resp.has_tool_calls)
        self.assertEqual(len(resp.tool_calls), 1)
        self.assertEqual(resp.tool_calls[0].name, "get_current_time")
        self.assertEqual(resp.tool_calls[0].arguments, {"timezone": "UTC"})

    async def test_07_router_skips_rate_limited_provider(self):
        # Provider 1 is currently RATE_LIMITED
        rate_limited_prov = MagicMock()
        rate_limited_prov.health = ProviderHealth()
        rate_limited_prov.health.record_failure("429 Rate Limit", status_code=429, retry_after=60.0)
        rate_limited_prov.capabilities.return_value = {"text": True, "tool_calling": True}
        rate_limited_prov.generate = AsyncMock()

        # Provider 2 is HEALTHY
        healthy_prov = MagicMock()
        healthy_prov.health = ProviderHealth()
        healthy_prov.capabilities.return_value = {"text": True, "tool_calling": True}
        healthy_prov.generate = AsyncMock(return_value=LLMResponse(text="Healthy response"))

        router = ModelRouter(providers={
            "reasoning": rate_limited_prov,
            "fallback": healthy_prov,
        })

        resp, role = await router.generate_with_fallback(
            messages=[{"role": "user", "content": "test"}],
            preferred_role="reasoning",
        )

        self.assertEqual(role, "fallback")
        self.assertEqual(resp.text, "Healthy response")
        rate_limited_prov.generate.assert_not_called()
        healthy_prov.generate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
