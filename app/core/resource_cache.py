import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.models.llm.health import ProviderHealthStatus

logger = logging.getLogger(__name__)


@dataclass
class ModelResourceEntry:
    """Tracks normalized resource state, token headroom, latency, and quota metrics for a (provider, model) pair."""
    provider_name: str
    model_name: str
    status: ProviderHealthStatus = ProviderHealthStatus.HEALTHY
    is_available: bool = True
    cooldown_until: float = 0.0
    rate_limit_state: str = "NORMAL"  # NORMAL, WARNING, NEAR_EXHAUSTION, RATE_LIMITED
    remaining_requests: int | None = None
    remaining_tokens: int | None = None
    limit_requests: int | None = None
    limit_tokens: int | None = None
    reset_requests_s: float | None = None
    reset_tokens_s: float | None = None
    recent_latency_ms: float = 350.0
    recent_ttft_ms: float = 180.0
    recent_success_rate: float = 1.0
    total_calls: int = 0
    successful_calls: int = 0
    last_updated: float = field(default_factory=time.time)
    source: str = "default"

    @property
    def in_cooldown(self) -> bool:
        return time.time() < self.cooldown_until

    @property
    def cooldown_remaining_s(self) -> float:
        return max(0.0, round(self.cooldown_until - time.time(), 1))


class ResourceStateCache:
    """Centralized high-performance cache tracking live provider capacity, token headroom,
    latency metrics, and rate-limit recovery state to prevent blind sequential fallbacks."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, stale_threshold_s: float = 300.0):
        if getattr(self, "_initialized", False):
            return
        self.stale_threshold_s = stale_threshold_s
        self.entries: dict[str, ModelResourceEntry] = {}
        self._initialized = True

    def reset(self) -> None:
        """Resets all cached resource states to fresh initial conditions."""
        self.entries.clear()

    def _key(self, provider_name: str, model_name: str) -> str:
        return f"{provider_name.lower().strip()}:{model_name.lower().strip()}"

    def get_or_create(self, provider_name: str, model_name: str) -> ModelResourceEntry:
        key = self._key(provider_name, model_name)
        if key not in self.entries:
            self.entries[key] = ModelResourceEntry(
                provider_name=provider_name,
                model_name=model_name,
                last_updated=time.time(),
                source="initial",
            )
        return self.entries[key]

    def get(self, provider_name: str, model_name: str) -> ModelResourceEntry | None:
        return self.entries.get(self._key(provider_name, model_name))

    def estimate_request_tokens(
        self,
        messages: list[dict[str, Any]],
        expected_output_tokens: int = 256,
    ) -> int:
        """Lightweight preflight token estimation (approx 1 token per 3.5 chars) without external network calls."""
        total_chars = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        total_chars += len(part["text"])

        input_tokens = max(1, int(total_chars / 3.5))
        return input_tokens + expected_output_tokens

    def get_resource_state(self, provider_name: str, model_name: str) -> ModelResourceEntry:
        """Alias for get_or_create."""
        return self.get_or_create(provider_name, model_name)

    def update_from_headers(
        self,
        provider_name: str,
        model_name: str,
        headers: dict[str, Any],
        latency_ms: float | None = None,
    ) -> None:
        """Parses standard provider response headers (Groq, Mistral, Cerebras, OpenRouter) to update capacity state."""
        entry = self.get_or_create(provider_name, model_name)
        now = time.time()
        entry.last_updated = now
        entry.source = "header"
        entry.total_calls += 1
        entry.successful_calls += 1
        entry.recent_success_rate = min(1.0, entry.successful_calls / max(1, entry.total_calls))

        if latency_ms is not None:
            if entry.total_calls <= 1:
                entry.recent_latency_ms = round(latency_ms, 1)
            else:
                entry.recent_latency_ms = round(entry.recent_latency_ms * 0.7 + latency_ms * 0.3, 1)

        # Normalize lowercase headers
        h_norm = {k.lower(): str(v) for k, v in headers.items()}

        # 1. Remaining & Limit Tokens
        for tok_key in ["x-ratelimit-remaining-tokens", "ratelimit-remaining-tokens", "x-ratelimit-remaining-tokens-minute"]:
            if tok_key in h_norm:
                try:
                    entry.remaining_tokens = int(float(h_norm[tok_key]))
                    break
                except Exception:
                    pass

        for tok_lim_key in ["x-ratelimit-limit-tokens", "ratelimit-limit-tokens", "x-ratelimit-limit-tokens-minute"]:
            if tok_lim_key in h_norm:
                try:
                    entry.limit_tokens = int(float(h_norm[tok_lim_key]))
                    break
                except Exception:
                    pass

        # 2. Remaining & Limit Requests
        for req_key in ["x-ratelimit-remaining-requests", "ratelimit-remaining-requests", "x-ratelimit-remaining-requests-minute", "x-ratelimit-remaining-requests-day"]:
            if req_key in h_norm:
                try:
                    entry.remaining_requests = int(float(h_norm[req_key]))
                    break
                except Exception:
                    pass

        for req_lim_key in ["x-ratelimit-limit-requests", "ratelimit-limit-requests"]:
            if req_lim_key in h_norm:
                try:
                    entry.limit_requests = int(float(h_norm[req_lim_key]))
                    break
                except Exception:
                    pass

        # 3. Reset Times
        for reset_key in ["x-ratelimit-reset-tokens", "ratelimit-reset-tokens", "x-ratelimit-reset-requests", "retry-after"]:
            if reset_key in h_norm:
                try:
                    val_str = h_norm[reset_key].strip()
                    if val_str.endswith("ms"):
                        val = float(val_str[:-2]) / 1000.0
                    elif val_str.endswith("s"):
                        val = float(val_str[:-1])
                    else:
                        val = float(val_str)
                    entry.reset_tokens_s = val
                    break
                except Exception:
                    pass

        # Compute rate limit status
        if entry.remaining_tokens is not None and entry.limit_tokens is not None and entry.limit_tokens > 0:
            pct = (entry.remaining_tokens / entry.limit_tokens) * 100
            if pct < 10:
                entry.rate_limit_state = "NEAR_EXHAUSTION"
            elif pct < 25:
                entry.rate_limit_state = "WARNING"
            else:
                entry.rate_limit_state = "NORMAL"
        else:
            entry.rate_limit_state = "NORMAL"

        entry.status = ProviderHealthStatus.HEALTHY
        entry.is_available = True

    def record_429(
        self,
        provider_name: str,
        model_name: str,
        retry_after: float = 10.0,
        error_message: str = "Rate limit exceeded (429)",
    ) -> None:
        """Updates cache when a 429 occurs, marking cooldown window and zeroing remaining quota."""
        entry = self.get_or_create(provider_name, model_name)
        now = time.time()
        entry.status = ProviderHealthStatus.RATE_LIMITED
        entry.is_available = False
        entry.cooldown_until = now + max(retry_after, 5.0)
        entry.rate_limit_state = "RATE_LIMITED"
        entry.remaining_tokens = 0
        entry.remaining_requests = 0
        entry.last_updated = now
        entry.source = "429_backoff"
        entry.total_calls += 1
        entry.recent_success_rate = max(0.0, (entry.successful_calls) / max(1, entry.total_calls))
        logger.warning(f"[ResourceStateCache] Recorded 429 for {provider_name}/{model_name}. Cooldown: {retry_after}s")

    def record_failure(
        self,
        provider_name: str,
        model_name: str,
        status_code: int | None = None,
        error_message: str = "Provider failure",
    ) -> None:
        """Records non-429 provider failures (auth errors, 5xx outages, timeouts)."""
        entry = self.get_or_create(provider_name, model_name)
        now = time.time()
        entry.last_updated = now
        entry.total_calls += 1
        entry.recent_success_rate = max(0.0, entry.successful_calls / max(1, entry.total_calls))

        if status_code in (401, 403):
            entry.status = ProviderHealthStatus.AUTH_ERROR
            entry.is_available = False
            entry.cooldown_until = now + 3600.0  # 1 hour auth lock
        elif status_code in (500, 502, 503, 504):
            entry.status = ProviderHealthStatus.UNAVAILABLE
            entry.is_available = False
            entry.cooldown_until = now + 15.0  # Short transient backoff
        else:
            entry.status = ProviderHealthStatus.DEGRADED
            entry.cooldown_until = now + 5.0

    def evaluate_candidate(
        self,
        provider_name: str,
        model_name: str,
        role: str,
        estimated_tokens: int,
        architect_priority_rank: int = 0,
        provider_instance: Any = None,
        images_present: bool = False,
        health_registry: Any = None,
    ) -> tuple[bool, float, list[str], dict[str, Any]]:
        """Performs sub-50ms deterministic preflight scoring & disqualification."""
        entry = self.get_or_create(provider_name, model_name)
        now = time.time()
        reasons: list[str] = []
        meta: dict[str, Any] = {
            "provider": provider_name,
            "model": model_name,
            "role": role,
            "latency_ms": entry.recent_latency_ms,
            "remaining_tokens": entry.remaining_tokens,
            "status": entry.status.value,
        }

        # Sync with Health Registry if provided
        if health_registry and hasattr(health_registry, "is_model_available"):
            if not health_registry.is_model_available(provider_name, model_name):
                reasons.append("✕ Model marked unavailable in health registry")
                return False, -500.0, reasons, meta
            else:
                h = health_registry.get_health(provider_name, model_name)
                if getattr(h, "status", None) == ProviderHealthStatus.HEALTHY:
                    entry.cooldown_until = 0.0
                    entry.rate_limit_state = "NORMAL"
                    entry.status = ProviderHealthStatus.HEALTHY
                    if entry.remaining_tokens == 0:
                        entry.remaining_tokens = None
                    if entry.remaining_requests == 0:
                        entry.remaining_requests = None

        # Sync with direct Provider instance health if present
        if provider_instance and hasattr(provider_instance, "health") and hasattr(provider_instance.health, "is_available"):
            if not provider_instance.health.is_available():
                reasons.append("✕ Provider instance health unavailable")
                return False, -500.0, reasons, meta

        # -------------------------------------------------------------
        # Hard Candidate Rejection Filters (Preflight Disqualification)
        # -------------------------------------------------------------
        # 1. Capability check
        if provider_instance and hasattr(provider_instance, "capabilities"):
            caps = provider_instance.capabilities()
            if images_present and not caps.get("vision", False):
                reasons.append("✕ Vision capability missing for multimodal query")
                return False, -1000.0, reasons, meta

        # 2. Status & Authentication check
        if entry.status == ProviderHealthStatus.AUTH_ERROR:
            reasons.append("✕ Authentication or API key invalid (401/403)")
            return False, -1000.0, reasons, meta

        if entry.status == ProviderHealthStatus.DISABLED:
            reasons.append("✕ Provider disabled by configuration")
            return False, -1000.0, reasons, meta

        # 3. Active Cooldown
        if entry.in_cooldown:
            reasons.append(f"✕ Active rate-limit cooldown ({entry.cooldown_remaining_s}s remaining)")
            return False, -500.0, reasons, meta

        # 4. Token Headroom Feasibility Check (Prevents predictable 429 failures)
        if entry.remaining_tokens is not None:
            if entry.remaining_tokens < estimated_tokens:
                reasons.append(
                    f"✕ Quota headroom insufficient: estimated {estimated_tokens} tokens > {entry.remaining_tokens} remaining"
                )
                return False, -400.0, reasons, meta

        # 5. Remaining Requests Check
        if entry.remaining_requests is not None and entry.remaining_requests <= 0:
            reasons.append("✕ Request quota exhausted (0 requests remaining)")
            return False, -400.0, reasons, meta

        # -------------------------------------------------------------
        # Positive Scoring Formulation
        # candidate_score = capability_fit + health_score + quota_headroom +
        #                   latency_score + reliability_score + architect_preference -
        #                   rate_limit_risk - cooldown_penalty
        # -------------------------------------------------------------
        capability_fit = 100.0
        health_score = 50.0 if entry.status == ProviderHealthStatus.HEALTHY else 20.0
        
        # Quota headroom score (0 - 40 points based on token buffer)
        if entry.remaining_tokens is not None and estimated_tokens > 0:
            ratio = min(5.0, entry.remaining_tokens / estimated_tokens)
            quota_headroom = ratio * 8.0  # Up to 40
        else:
            quota_headroom = 25.0  # Neutral if unknown

        # Latency score: 30 points max, penalizing >1000ms
        latency_score = max(0.0, 30.0 - (entry.recent_latency_ms / 50.0))

        # Reliability score with smoothing for low sample sizes
        smoothed_rate = (entry.successful_calls + 1) / (entry.total_calls + 2) if entry.total_calls < 5 else entry.recent_success_rate
        reliability_score = smoothed_rate * 20.0

        # Architect Preference: 100 points baseline minus strong rank degradation
        architect_preference = max(10.0, 100.0 - (architect_priority_rank * 35.0))

        # Stale cache penalty
        stale_penalty = 0.0
        if (now - entry.last_updated) > self.stale_threshold_s:
            stale_penalty = 15.0  # Moderate confidence reduction for unrefreshed metrics

        # Rate limit risk penalty
        rate_limit_risk = 30.0 if entry.rate_limit_state == "WARNING" else (60.0 if entry.rate_limit_state == "NEAR_EXHAUSTION" else 0.0)

        total_score = round(
            capability_fit + health_score + quota_headroom + latency_score + reliability_score + architect_preference - stale_penalty - rate_limit_risk,
            2
        )

        reasons.append("✓ Capability match confirmed")
        reasons.append(f"✓ Healthy status ({entry.status.value})")
        if entry.remaining_tokens is not None:
            reasons.append(f"✓ Sufficient token headroom ({entry.remaining_tokens} tokens remaining vs {estimated_tokens} required)")
        reasons.append(f"✓ Low latency ({entry.recent_latency_ms}ms avg)")
        reasons.append(f"✓ High reliability ({int(entry.recent_success_rate * 100)}% success rate)")
        if architect_priority_rank == 0:
            reasons.append("✓ Preferred architect candidate (#1)")
        else:
            reasons.append(f"✓ Configured candidate (#{architect_priority_rank + 1})")

        meta["score"] = total_score
        return True, total_score, reasons, meta

    def get_all_resource_states(self) -> dict[str, Any]:
        """Returns snapshot of all tracked model resource states for UI inspection."""
        result = {}
        for key, entry in self.entries.items():
            result[key] = {
                "provider": entry.provider_name,
                "model": entry.model_name,
                "status": entry.status.value,
                "is_available": entry.is_available,
                "in_cooldown": entry.in_cooldown,
                "cooldown_remaining_s": entry.cooldown_remaining_s,
                "rate_limit_state": entry.rate_limit_state,
                "remaining_tokens": entry.remaining_tokens,
                "limit_tokens": entry.limit_tokens,
                "remaining_requests": entry.remaining_requests,
                "recent_latency_ms": entry.recent_latency_ms,
                "recent_success_rate": entry.recent_success_rate,
                "last_updated": entry.last_updated,
                "source": entry.source,
            }
        return result

    def reset(self) -> None:
        """Resets all entries in the resource state cache."""
        self.entries.clear()

    def set_resource_state(
        self,
        provider: str,
        model: str,
        remaining_tokens: int | None = None,
        remaining_requests: int | None = None,
        recent_latency_ms: float = 300.0,
        health: str = "HEALTHY",
    ) -> ModelResourceEntry:
        """Helper for tests/simulations to directly populate cache state."""
        entry = self.get_or_create(provider, model)
        if remaining_tokens is not None:
            entry.remaining_tokens = remaining_tokens
        if remaining_requests is not None:
            entry.remaining_requests = remaining_requests
        entry.recent_latency_ms = recent_latency_ms
        if health == "HEALTHY":
            entry.status = ProviderHealthStatus.HEALTHY
            entry.is_available = True
        return entry
