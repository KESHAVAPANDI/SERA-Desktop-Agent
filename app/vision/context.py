import threading
import time
from app.vision.models import ScreenContext


class ScreenContextCache:
    """Thread-safe TTL cache for ScreenContext indexed by image hash."""

    def __init__(self, enabled: bool = True, ttl_seconds: float = 5.0):
        self.enabled = enabled
        self.ttl_seconds = ttl_seconds
        self._cached_context: ScreenContext | None = None
        self._cached_hash: str | None = None
        self._cached_at: float = 0.0
        self._lock = threading.Lock()

    def get(self, screen_hash: str) -> ScreenContext | None:
        """Retrieves cached ScreenContext if valid, not expired, and hashes match."""
        if not self.enabled:
            return None

        with self._lock:
            if not self._cached_context or not self._cached_hash:
                return None

            # Check expiration
            if time.time() - self._cached_at > self.ttl_seconds:
                self._cached_context = None
                self._cached_hash = None
                return None

            # Check hash match
            if self._cached_hash == screen_hash:
                return self._cached_context

            return None

    def set(self, screen_hash: str, context: ScreenContext) -> None:
        """Stores ScreenContext with current timestamp and hash."""
        if not self.enabled:
            return

        with self._lock:
            self._cached_context = context
            self._cached_hash = screen_hash
            self._cached_at = time.time()

    def clear(self) -> None:
        """Invalidates current cached context."""
        with self._lock:
            self._cached_context = None
            self._cached_hash = None
            self._cached_at = 0.0
