import math
import threading
import time
from collections import defaultdict, deque
from functools import lru_cache


class SlidingWindowLimiter:
    """Limitador simples em memória (por processo): N requisições por janela."""

    def __init__(self, window_seconds: float = 60.0) -> None:
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, now: float | None = None) -> int | None:
        """Registra uma requisição. Retorna None se permitida, ou os segundos até liberar."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= limit:
                return max(1, math.ceil(self.window - (now - hits[0])))
            hits.append(now)
            return None


@lru_cache
def get_limiter() -> SlidingWindowLimiter:
    return SlidingWindowLimiter()
