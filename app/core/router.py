import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator

from app.models.llm.base import LLMProvider, LLMResponse
from app.models.llm.health import ModelHealthRegistry, ProviderHealthStatus
from app.models.llm.latency import ProviderLatencyMetrics

logger = logging.getLogger(__name__)


@dataclass
class RoleCandidate:
    """Represents a specific (provider, model) candidate for a defined system role."""
    provider_name: str
    model_name: str
    provider: LLMProvider
    role: str

    def __str__(self) -> str:
        return f"{self.provider_name}/{self.model_name}"


class ModelRouter:
    """True ROLE → PROVIDER → FALLBACK router with fine-grained model-level health tracking."""

    def __init__(
        self,
        providers: dict[str, LLMProvider] | None = None,
        role_chains: dict[str, list[RoleCandidate]] | None = None,
        health_registry: ModelHealthRegistry | None = None,
        debug_routing: bool = True,
    ):
        self.health_registry = health_registry or ModelHealthRegistry()
        self.debug_routing = debug_routing
        self.role_chains: dict[str, list[RoleCandidate]] = role_chains or {}
        self.legacy_providers: dict[str, LLMProvider] = providers or {}

        # If legacy providers dict was passed, synthesize role chains for full backward compatibility
        if not self.role_chains and self.legacy_providers:
            for r_name, p_obj in self.legacy_providers.items():
                m_name = getattr(p_obj, "model", "default")
                p_name = getattr(p_obj, "provider_name", r_name)
                candidate = RoleCandidate(
                    provider_name=p_name,
                    model_name=m_name,
                    provider=p_obj,
                    role=r_name,
                )
                self.role_chains[r_name] = [candidate]

    def has_role(self, role: str) -> bool:
        """Returns True if at least one candidate is registered for this role."""
        return role in self.role_chains and len(self.role_chains[role]) > 0

    def get_provider(self, role: str) -> LLMProvider:
        """Returns the primary provider for the given role (backward compatibility)."""
        candidates = self.role_chains.get(role, [])
        if not candidates:
            if role in self.legacy_providers:
                return self.legacy_providers[role]
            raise ValueError(f"No provider candidates configured for role: '{role}'")
        return candidates[0].provider

    def get_role_candidates(self, role: str) -> list[RoleCandidate]:
        """Returns the ordered candidate chain for a role."""
        return self.role_chains.get(role, [])

    def select_role_for_task(self, query: str, has_image: bool = False) -> str:
        """Selects optimal model role based on user task characteristics."""
        if has_image:
            if self.has_role("vision"):
                return "vision"
            elif self.has_role("vision_qwen"):
                return "vision_qwen"
            elif self.has_role("vision_gemini"):
                return "vision_gemini"

        q_lower = query.lower()

        # Deterministic local fast queries
        fast_keywords = [
            "what time", "current time", "date today", "what is the date",
            "battery", "battery status", "wifi status", "cpu usage",
            "volume", "set volume", "brightness", "set brightness",
            "hello", "hi", "hey sera", "how are you", "who are you",
        ]
        if any(kw in q_lower for kw in fast_keywords) and self.has_role("fast"):
            return "fast"

        # Desktop automation and tool planning requests
        desktop_keywords = [
            "open", "launch", "close", "click", "type", "search for",
            "take a screenshot", "inspect", "calculate", "press",
        ]
        if any(kw in q_lower for kw in desktop_keywords) and self.has_role("desktop"):
            return "desktop"

        return "reasoning"

    async def generate_with_role(
        self,
        role: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        images: list[bytes] | None = None,
        **kwargs,
    ) -> tuple[LLMResponse, RoleCandidate]:
        """Generates response using role's candidate chain with model-level health failover."""
        candidates = self.role_chains.get(role, [])
        if not candidates:
            # Fallback to legacy routing if role is not in role_chains
            legacy_resp, used_role = await self.generate_with_fallback(
                messages=messages,
                tools=tools,
                images=images,
                preferred_role=role,
                **kwargs,
            )
            syn_candidate = RoleCandidate(
                provider_name=legacy_resp.provider or used_role,
                model_name=legacy_resp.model or "unknown",
                provider=self.legacy_providers.get(used_role, candidates[0].provider if candidates else None),
                role=role,
            )
            return legacy_resp, syn_candidate

        last_error = None

        for idx, candidate in enumerate(candidates):
            p_name = candidate.provider_name
            m_name = candidate.model_name
            provider = candidate.provider

            # 1. Model-Level Health & Cooldown Check
            is_avail = self.health_registry.is_model_available(p_name, m_name)
            if hasattr(provider, "health") and hasattr(provider.health, "is_available"):
                if not provider.health.is_available():
                    is_avail = False

            if not is_avail:
                cooldown_rem = self.health_registry.get_cooldown_remaining_s(p_name, m_name)
                health = getattr(provider, "health", self.health_registry.get_health(p_name, m_name))
                if self.debug_routing:
                    print(
                        f"[ROUTER] Role: {role} | Skipped: {p_name} / {m_name} "
                        f"({getattr(health, 'status', 'RATE_LIMITED')}, Cooldown: {cooldown_rem}s)"
                    )
                logger.debug(
                    f"[ModelRouter] Skipped {candidate} for role '{role}' ({cooldown_rem}s remaining)."
                )
                continue

            # 2. Capability Validation (e.g. vision or tools required)
            caps = provider.capabilities()
            if images and not caps.get("vision", False):
                logger.debug(f"[ModelRouter] Skipped {candidate}: lacks vision capability.")
                continue

            if self.debug_routing:
                reason = "primary candidate healthy" if idx == 0 else f"fallback candidate #{idx + 1}"
                print(f"[ROUTER] Role: {role} | Selected: {p_name} / {m_name} | Reason: {reason}")

            # 3. Attempt Generation
            t0 = time.perf_counter()
            try:
                supports_tools = caps.get("tool_calling", True)
                applied_tools = tools if supports_tools else None

                response = await provider.generate(
                    messages=messages,
                    tools=applied_tools,
                    images=images,
                    **kwargs,
                )

                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                self.health_registry.record_success(p_name, m_name, elapsed_ms)
                return response, candidate

            except Exception as e:
                err_str = str(e)
                status_code = None
                if "429" in err_str or "rate_limit" in err_str:
                    status_code = 429
                elif "402" in err_str or "payment" in err_str:
                    status_code = 402
                elif "401" in err_str or "auth" in err_str:
                    status_code = 401

                self.health_registry.record_failure(p_name, m_name, err_str, status_code=status_code)

                if status_code == 429:
                    logger.warning(
                        f"[ModelRouter] Quota/rate-limit on {candidate} for role '{role}'. Switching immediately to next fallback..."
                    )
                else:
                    logger.warning(
                        f"[ModelRouter] Failure on {candidate} for role '{role}': {e}. Switching to next fallback..."
                    )
                last_error = e

        raise RuntimeError(
            f"All model candidates failed for role '{role}'. Last error: {last_error}"
        )

    async def stream_with_role(
        self,
        role: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        images: list[bytes] | None = None,
        **kwargs,
    ) -> AsyncIterator[tuple[str, RoleCandidate]]:
        """Streams generated tokens from the role's candidate chain with failover."""
        candidates = self.role_chains.get(role, [])
        if not candidates:
            async for token, used_role in self.generate_stream_with_fallback(
                messages=messages,
                tools=tools,
                images=images,
                preferred_role=role,
                **kwargs,
            ):
                syn_candidate = RoleCandidate(
                    provider_name=used_role,
                    model_name="stream_model",
                    provider=self.legacy_providers.get(used_role),
                    role=role,
                )
                yield token, syn_candidate
            return

        last_error = None

        for idx, candidate in enumerate(candidates):
            p_name = candidate.provider_name
            m_name = candidate.model_name
            provider = candidate.provider

            is_avail = self.health_registry.is_model_available(p_name, m_name)
            if hasattr(provider, "health") and hasattr(provider.health, "is_available"):
                if not provider.health.is_available():
                    is_avail = False

            if not is_avail:
                cooldown_rem = self.health_registry.get_cooldown_remaining_s(p_name, m_name)
                health = getattr(provider, "health", self.health_registry.get_health(p_name, m_name))
                if self.debug_routing:
                    print(
                        f"[ROUTER] Role: {role} | Skipped Stream: {p_name} / {m_name} "
                        f"({getattr(health, 'status', 'RATE_LIMITED')}, Cooldown: {cooldown_rem}s)"
                    )
                continue

            caps = provider.capabilities()
            if images and not caps.get("vision", False):
                continue

            if self.debug_routing:
                reason = "primary candidate healthy" if idx == 0 else f"fallback candidate #{idx + 1}"
                print(f"[ROUTER] Stream Role: {role} | Selected: {p_name} / {m_name} | Reason: {reason}")

            t0 = time.perf_counter()
            try:
                supports_tools = caps.get("tool_calling", True)
                applied_tools = tools if supports_tools else None

                has_yielded = False
                async for token in provider.stream(
                    messages=messages,
                    tools=applied_tools,
                    images=images,
                    **kwargs,
                ):
                    has_yielded = True
                    yield token, candidate

                if has_yielded:
                    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                    self.health_registry.record_success(p_name, m_name, elapsed_ms)
                    return

            except Exception as e:
                err_str = str(e)
                status_code = 429 if "429" in err_str else (402 if "402" in err_str else None)
                self.health_registry.record_failure(p_name, m_name, err_str, status_code=status_code)
                last_error = e

        raise RuntimeError(
            f"All model candidates failed streaming for role '{role}'. Last error: {last_error}"
        )

    # -------------------------------------------------------------
    # Backward Compatibility Methods
    # -------------------------------------------------------------
    async def generate_with_fallback(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        images: list[bytes] | None = None,
        preferred_role: str = "reasoning",
        **kwargs,
    ) -> tuple[LLMResponse, str]:
        """Backward-compatible generate wrapper."""
        target_role = preferred_role
        if images and "vision" not in target_role:
            target_role = "vision" if self.has_role("vision") else "vision_qwen"

        try:
            resp, candidate = await self.generate_with_role(
                role=target_role,
                messages=messages,
                tools=tools,
                images=images,
                **kwargs,
            )
            return resp, target_role
        except Exception:
            # Fallback to standard reasoning or fast if primary role failed
            alt_roles = ["reasoning", "fast", "fallback"]
            for alt in alt_roles:
                if alt != target_role and self.has_role(alt):
                    try:
                        resp, candidate = await self.generate_with_role(
                            role=alt,
                            messages=messages,
                            tools=tools,
                            images=images,
                            **kwargs,
                        )
                        return resp, alt
                    except Exception:
                        continue
            raise

    async def generate_stream_with_fallback(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        images: list[bytes] | None = None,
        preferred_role: str = "reasoning",
        **kwargs,
    ) -> AsyncIterator[tuple[str, str]]:
        """Backward-compatible streaming wrapper."""
        target_role = preferred_role
        if images and "vision" not in target_role:
            target_role = "vision" if self.has_role("vision") else "vision_qwen"

        try:
            async for token, candidate in self.stream_with_role(
                role=target_role,
                messages=messages,
                tools=tools,
                images=images,
                **kwargs,
            ):
                yield token, target_role
            return
        except Exception:
            alt_roles = ["reasoning", "fast", "fallback"]
            for alt in alt_roles:
                if alt != target_role and self.has_role(alt):
                    try:
                        async for token, candidate in self.stream_with_role(
                            role=alt,
                            messages=messages,
                            tools=tools,
                            images=images,
                            **kwargs,
                        ):
                            yield token, alt
                        return
                    except Exception:
                        continue
            raise

    def refresh_provider_health(self) -> dict[str, dict]:
        """Performs a safe, zero-inference health refresh checking rate-limit cooldown windows."""
        return self.health_registry.get_summary()


def create_model_router_from_config(config_data: dict) -> ModelRouter:
    """Instantiates a production role-aware ModelRouter from config.yaml schema."""
    from app.models.llm import create_provider

    roles_cfg = config_data.get("roles", {})
    models_cfg = config_data.get("models", {})
    health_reg = ModelHealthRegistry()
    role_chains: dict[str, list[RoleCandidate]] = {}
    legacy_providers: dict[str, LLMProvider] = {}

    # 1. Parse 'roles' configuration if present
    if roles_cfg:
        for r_name, r_info in roles_cfg.items():
            chain: list[RoleCandidate] = []

            # Primary candidate
            prim = r_info.get("primary", {})
            p_prov = prim.get("provider")
            p_model = prim.get("model")
            if p_prov and p_model:
                try:
                    p_obj = create_provider(provider=p_prov, model=p_model)
                    chain.append(RoleCandidate(
                        provider_name=p_prov,
                        model_name=p_model,
                        provider=p_obj,
                        role=r_name,
                    ))
                except Exception as e:
                    logger.debug(f"[create_model_router] Failed to init primary {p_prov}/{p_model}: {e}")

            # Fallback candidates
            for fb in r_info.get("fallbacks", []):
                fb_prov = fb.get("provider")
                fb_model = fb.get("model")
                if fb_prov and fb_model:
                    try:
                        fb_obj = create_provider(provider=fb_prov, model=fb_model)
                        chain.append(RoleCandidate(
                            provider_name=fb_prov,
                            model_name=fb_model,
                            provider=fb_obj,
                            role=r_name,
                        ))
                    except Exception as e:
                        logger.debug(f"[create_model_router] Failed to init fallback {fb_prov}/{fb_model}: {e}")

            if chain:
                role_chains[r_name] = chain
                legacy_providers[r_name] = chain[0].provider

    # 2. Parse legacy 'models' section if role_chains is incomplete
    if models_cfg:
        for m_role, m_info in models_cfg.items():
            prov_name = m_info.get("provider")
            model_name = m_info.get("model")
            if prov_name and model_name and m_role not in role_chains:
                try:
                    prov_obj = create_provider(provider=prov_name, model=model_name)
                    legacy_providers[m_role] = prov_obj
                    role_chains[m_role] = [
                        RoleCandidate(
                            provider_name=prov_name,
                            model_name=model_name,
                            provider=prov_obj,
                            role=m_role,
                        )
                    ]
                except Exception as e:
                    logger.debug(f"[create_model_router] Failed legacy init for {m_role}: {e}")

    return ModelRouter(
        providers=legacy_providers,
        role_chains=role_chains,
        health_registry=health_reg,
        debug_routing=config_data.get("telemetry", {}).get("manual_debug_mode", True),
    )