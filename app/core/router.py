import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator

from app.core.resource_cache import ResourceStateCache
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
    """Adaptive resource-aware ROLE → PROVIDER → MODEL router with preflight capacity feasibility scoring,
    quota headroom validation, and zero blind sequential fallbacks."""

    def __init__(
        self,
        providers: dict[str, LLMProvider] | None = None,
        role_chains: dict[str, list[RoleCandidate]] | None = None,
        health_registry: ModelHealthRegistry | None = None,
        resource_cache: ResourceStateCache | None = None,
        event_bus: Any | None = None,
        debug_routing: bool = True,
    ):
        self.health_registry = health_registry or ModelHealthRegistry()
        self.resource_cache = resource_cache or ResourceStateCache()
        self.event_bus = event_bus
        self.debug_routing = debug_routing
        self.role_chains: dict[str, list[RoleCandidate]] = role_chains or {}
        self.legacy_providers: dict[str, LLMProvider] = providers or {}
        self.execution_modes: dict[str, str] = {}  # role -> PRIMARY_ONLY | FALLBACK_ORDER | RESOURCE_AWARE | CUSTOM
        self.last_routing_explanations: dict[str, Any] = {}

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

    @property
    def providers(self) -> dict[str, Any]:
        """Returns map of provider_name to provider instance across all candidate chains."""
        result = dict(self.legacy_providers)
        for chain in self.role_chains.values():
            for cand in chain:
                if cand.provider:
                    result[cand.provider_name] = cand.provider
        return result

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

    def register_role_chain(self, role: str, candidates: list[RoleCandidate], mode: str = "RESOURCE_AWARE") -> None:
        """Registers a candidate chain and execution mode for a role."""
        self.role_chains[role] = candidates
        self.execution_modes[role] = mode

    def set_execution_mode(self, role: str, mode: str) -> None:
        """Sets execution mode for a role (PRIMARY_ONLY, FALLBACK_ORDER, RESOURCE_AWARE, CUSTOM)."""
        self.execution_modes[role] = mode

    def get_execution_mode(self, role: str) -> str:
        """Gets execution mode for a role, defaulting to RESOURCE_AWARE."""
        return self.execution_modes.get(role, "RESOURCE_AWARE")

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
            "thank you", "thanks", "good morning", "good evening",
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

    def select_candidate_preflight(
        self,
        role: str,
        messages: list[dict[str, Any]],
        images: list[bytes] | None = None,
    ) -> tuple[RoleCandidate, list[RoleCandidate], dict[str, Any]]:
        """Preflight selects the optimal candidate using ResourceStateCache scoring,
        disqualifying models with active cooldowns or insufficient token headroom.
        
        Returns:
            (selected_candidate, ordered_fallback_candidates, telemetry_explanation)
        """
        t0 = time.perf_counter()
        candidates = self.role_chains.get(role, [])
        if not candidates:
            legacy_provider = self.legacy_providers.get(role)
            if legacy_provider:
                syn_candidate = RoleCandidate(
                    provider_name=getattr(legacy_provider, "provider_name", role),
                    model_name=getattr(legacy_provider, "model", "default"),
                    provider=legacy_provider,
                    role=role,
                )
                return syn_candidate, [], {"decision_ms": 0.1, "reasons": ["Legacy fallback provider"]}
            raise RuntimeError(f"No candidates or legacy provider configured for role '{role}'")

        mode = self.get_execution_mode(role)
        estimated_tokens = self.resource_cache.estimate_request_tokens(messages)

        # -------------------------------------------------------------
        # Mode 1: PRIMARY ONLY
        # -------------------------------------------------------------
        if mode == "PRIMARY_ONLY":
            prim = candidates[0]
            explanation = {
                "role": role,
                "mode": mode,
                "estimated_tokens": estimated_tokens,
                "selected_model": str(prim),
                "reasons": ["✓ Primary-Only mode enforced by configuration"],
                "decision_ms": round((time.perf_counter() - t0) * 1000, 2),
            }
            self.last_routing_explanations[role] = explanation
            return prim, [], explanation

        # -------------------------------------------------------------
        # Mode 2: FALLBACK ORDER (Strict ordered sequence)
        # -------------------------------------------------------------
        if mode == "FALLBACK_ORDER":
            healthy_cands = []
            for idx, c in enumerate(candidates):
                entry = self.resource_cache.get_or_create(c.provider_name, c.model_name)
                if not entry.in_cooldown and entry.status != ProviderHealthStatus.DISABLED:
                    healthy_cands.append(c)

            selected = healthy_cands[0] if healthy_cands else candidates[0]
            fallbacks = healthy_cands[1:] if len(healthy_cands) > 1 else [c for c in candidates if c != selected]
            explanation = {
                "role": role,
                "mode": mode,
                "estimated_tokens": estimated_tokens,
                "selected_model": str(selected),
                "reasons": ["✓ Sequential candidate ordering"],
                "decision_ms": round((time.perf_counter() - t0) * 1000, 2),
            }
            self.last_routing_explanations[role] = explanation
            return selected, fallbacks, explanation

        # -------------------------------------------------------------
        # Mode 3: RESOURCE AWARE (Intelligent preflight feasibility scoring)
        # -------------------------------------------------------------
        scored_candidates: list[tuple[float, RoleCandidate, list[str], dict[str, Any]]] = []
        rejected_candidates: list[dict[str, Any]] = []

        for idx, cand in enumerate(candidates):
            is_eligible, score, reasons, meta = self.resource_cache.evaluate_candidate(
                provider_name=cand.provider_name,
                model_name=cand.model_name,
                role=role,
                estimated_tokens=estimated_tokens,
                architect_priority_rank=idx,
                provider_instance=cand.provider,
                images_present=bool(images),
                health_registry=self.health_registry,
            )

            if is_eligible:
                scored_candidates.append((score, cand, reasons, meta))
            else:
                rejected_candidates.append({
                    "model": str(cand),
                    "reasons": reasons,
                    "meta": meta,
                })

        # Sort eligible candidates descending by score
        scored_candidates.sort(key=lambda item: item[0], reverse=True)

        if scored_candidates:
            best_score, selected_cand, best_reasons, best_meta = scored_candidates[0]
            fallback_cands = [item[1] for item in scored_candidates[1:]]
        else:
            raise RuntimeError(f"All model candidates rejected during preflight for role '{role}'")

        decision_ms = round((time.perf_counter() - t0) * 1000, 2)
        explanation = {
            "role": role,
            "mode": mode,
            "estimated_tokens": estimated_tokens,
            "selected_model": str(selected_cand),
            "selected_score": best_score,
            "reasons": best_reasons,
            "rejected_candidates": rejected_candidates,
            "candidate_count": len(candidates),
            "eligible_count": len(scored_candidates),
            "decision_ms": decision_ms,
            "timestamp": time.time(),
        }
        self.last_routing_explanations[role] = explanation

        if self.debug_routing:
            print(
                f"[ROUTER] Role: {role} | Selected: {selected_cand} | Score: {best_score} | "
                f"Est Tokens: {estimated_tokens} | Decision: {decision_ms}ms"
            )

        return selected_cand, fallback_cands, explanation

    async def generate_with_role(
        self,
        role: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        images: list[bytes] | None = None,
        **kwargs,
    ) -> tuple[LLMResponse, RoleCandidate]:
        """Generates response using preflight resource-aware selection with zero blind fallbacks."""
        selected, fallbacks, explanation = self.select_candidate_preflight(role, messages, images=images)
        dispatch_chain = [selected] + fallbacks

        last_error = None

        for idx, candidate in enumerate(dispatch_chain):
            p_name = candidate.provider_name
            m_name = candidate.model_name
            provider = candidate.provider

            caps = provider.capabilities() if hasattr(provider, "capabilities") else {}
            if images and not caps.get("vision", False):
                continue

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
                self.resource_cache.get_or_create(p_name, m_name).recent_latency_ms = elapsed_ms
                return response, candidate

            except Exception as e:
                err_str = str(e)
                status_code = 429 if ("429" in err_str or "rate_limit" in err_str.lower()) else (401 if "401" in err_str else (402 if "402" in err_str else None))
                self.health_registry.record_failure(p_name, m_name, err_str, status_code=status_code)
                if status_code == 429:
                    self.resource_cache.record_429(p_name, m_name, retry_after=10.0, error_message=err_str)
                else:
                    self.resource_cache.record_failure(p_name, m_name, status_code=status_code, error_message=err_str)

                logger.warning(
                    f"[ModelRouter] Failure on {candidate} for role '{role}': {e}. Transitioning to next candidate in preflight list..."
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
        """Streams generated tokens using preflight resource-aware candidate selection."""
        selected, fallbacks, explanation = self.select_candidate_preflight(role, messages, images=images)
        dispatch_chain = [selected] + fallbacks

        last_error = None

        for idx, candidate in enumerate(dispatch_chain):
            p_name = candidate.provider_name
            m_name = candidate.model_name
            provider = candidate.provider

            caps = provider.capabilities() if hasattr(provider, "capabilities") else {}
            if images and not caps.get("vision", False):
                continue

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
                    self.resource_cache.get_or_create(p_name, m_name).recent_latency_ms = elapsed_ms
                    return

            except Exception as e:
                err_str = str(e)
                status_code = 429 if ("429" in err_str or "rate_limit" in err_str.lower()) else None
                self.health_registry.record_failure(p_name, m_name, err_str, status_code=status_code)
                if status_code == 429:
                    self.resource_cache.record_429(p_name, m_name, retry_after=10.0, error_message=err_str)
                else:
                    self.resource_cache.record_failure(p_name, m_name, status_code=status_code, error_message=err_str)
                last_error = e

        raise RuntimeError(
            f"All model candidates failed streaming for role '{role}'. Last error: {last_error}"
        )

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
    res_cache = ResourceStateCache()
    role_chains: dict[str, list[RoleCandidate]] = {}
    legacy_providers: dict[str, LLMProvider] = {}
    execution_modes: dict[str, str] = {}

    # 1. Parse 'roles' configuration if present
    if roles_cfg:
        for r_name, r_info in roles_cfg.items():
            chain: list[RoleCandidate] = []
            execution_modes[r_name] = r_info.get("mode", "RESOURCE_AWARE")

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
                    execution_modes[m_role] = "RESOURCE_AWARE"
                except Exception as e:
                    logger.debug(f"[create_model_router] Failed legacy init for {m_role}: {e}")

    router = ModelRouter(
        providers=legacy_providers,
        role_chains=role_chains,
        health_registry=health_reg,
        resource_cache=res_cache,
        debug_routing=config_data.get("telemetry", {}).get("manual_debug_mode", True),
    )
    router.execution_modes = execution_modes
    return router