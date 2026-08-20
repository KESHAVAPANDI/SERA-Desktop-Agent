import time
from dataclasses import dataclass, field
from enum import Enum


class ProviderHealthStatus(str, Enum):
    REGISTERED = "REGISTERED"
    HEALTHY = "HEALTHY"
    RATE_LIMITED = "RATE_LIMITED"
    UNAVAILABLE = "UNAVAILABLE"
    AUTH_ERROR = "AUTH_ERROR"
    DEGRADED = "DEGRADED"
    DISABLED = "DISABLED"


@dataclass
class ProviderHealth:
    """Tracks runtime health, latency telemetry, and rate-limiting status for a model provider/model."""
    status: ProviderHealthStatus = ProviderHealthStatus.HEALTHY
    last_success: float | None = None
    last_failure: float | None = None
    last_429: float | None = None
    retry_after: float = 0.0
    consecutive_failures: int = 0
    recent_latencies_ms: list[float] = field(default_factory=list)
    last_error_message: str | None = None
    last_status_code: int | None = None

    def is_available(self) -> bool:
        """Returns True if provider/model is healthy or cooldown window has elapsed."""
        now = time.time()
        if self.status == ProviderHealthStatus.DISABLED:
            return False

        if self.status == ProviderHealthStatus.RATE_LIMITED:
            if self.last_429 and (now - self.last_429) < max(self.retry_after, 5.0):
                return False
            # Cooldown window expired, allow next attempt
            return True

        if self.status in (ProviderHealthStatus.UNAVAILABLE, ProviderHealthStatus.AUTH_ERROR):
            # Backoff for persistent auth/quota/payment errors (retry every 60s)
            if self.last_failure and (now - self.last_failure) < 60.0:
                return False
            return True

        return True

    def get_cooldown_remaining_s(self) -> float:
        """Returns remaining seconds in rate-limit cooldown window, or 0.0 if ready."""
        now = time.time()
        if self.status == ProviderHealthStatus.RATE_LIMITED and self.last_429:
            rem = (self.last_429 + max(self.retry_after, 5.0)) - now
            return max(0.0, round(rem, 1))
        if self.status in (ProviderHealthStatus.UNAVAILABLE, ProviderHealthStatus.AUTH_ERROR) and self.last_failure:
            rem = (self.last_failure + 60.0) - now
            return max(0.0, round(rem, 1))
        return 0.0

    def record_success(self, latency_ms: float) -> None:
        """Records successful response and resets failure streak."""
        self.status = ProviderHealthStatus.HEALTHY
        self.last_success = time.time()
        self.consecutive_failures = 0
        self.last_error_message = None
        self.last_status_code = 200
        self.recent_latencies_ms.append(latency_ms)
        if len(self.recent_latencies_ms) > 20:
            self.recent_latencies_ms.pop(0)

    def record_failure(
        self,
        error_message: str,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        """Records failure and updates health status categorization."""
        now = time.time()
        self.last_failure = now
        self.consecutive_failures += 1
        self.last_error_message = error_message
        self.last_status_code = status_code

        err_lower = error_message.lower()
        if status_code == 429 or "rate_limit" in err_lower or "quota" in err_lower or "balance" in err_lower or "resource_exhausted" in err_lower:
            self.status = ProviderHealthStatus.RATE_LIMITED
            self.last_429 = now
            self.retry_after = retry_after if retry_after is not None else 10.0
        elif status_code in (401, 403, 402) or "payment" in err_lower or "unauthorized" in err_lower:
            self.status = ProviderHealthStatus.AUTH_ERROR
        elif status_code in (500, 502, 503, 504) or "unavailable" in err_lower:
            self.status = ProviderHealthStatus.UNAVAILABLE
        elif self.consecutive_failures >= 3:
            self.status = ProviderHealthStatus.DEGRADED
        else:
            self.status = ProviderHealthStatus.DEGRADED


class ModelHealthRegistry:
    """Manages fine-grained health tracking at the (provider, model) pair level."""

    def __init__(self):
        self._health_map: dict[str, ProviderHealth] = {}

    def _key(self, provider: str, model: str) -> str:
        return f"{provider.lower().strip()}:{model.lower().strip()}"

    def get_health(self, provider: str, model: str) -> ProviderHealth:
        key = self._key(provider, model)
        if key not in self._health_map:
            self._health_map[key] = ProviderHealth()
        return self._health_map[key]

    def is_model_available(self, provider: str, model: str) -> bool:
        return self.get_health(provider, model).is_available()

    def get_cooldown_remaining_s(self, provider: str, model: str) -> float:
        return self.get_health(provider, model).get_cooldown_remaining_s()

    def record_success(self, provider: str, model: str, latency_ms: float) -> None:
        self.get_health(provider, model).record_success(latency_ms)

    def record_failure(
        self,
        provider: str,
        model: str,
        error_message: str,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        self.get_health(provider, model).record_failure(error_message, status_code, retry_after)

    def get_summary(self) -> dict[str, dict]:
        return {
            key: {
                "status": h.status.value,
                "consecutive_failures": h.consecutive_failures,
                "last_error": h.last_error_message,
                "cooldown_s": h.get_cooldown_remaining_s(),
            }
            for key, h in self._health_map.items()
        }
