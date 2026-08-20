import time
from dataclasses import dataclass, field


@dataclass
class ProviderLatencyMetrics:
    """Standardized latency and telemetry metrics for model providers."""
    provider: str
    model: str
    role: str
    timestamp: float = field(default_factory=time.time)
    request_latency_ms: float | None = None  # Network start to initial response
    ttft_ms: float | None = None  # Request start to first token
    total_ms: float = 0.0  # Request start to completed output
    success: bool = True
    failure_type: str | None = None  # RATE_LIMIT, AUTH, TIMEOUT, BAD_REQUEST, SERVER_ERROR
    error_message: str | None = None
    tokens_count: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "role": self.role,
            "timestamp": self.timestamp,
            "request_latency_ms": self.request_latency_ms,
            "ttft_ms": self.ttft_ms,
            "total_ms": self.total_ms,
            "success": self.success,
            "failure_type": self.failure_type,
            "error_message": self.error_message,
            "tokens_count": self.tokens_count,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }
