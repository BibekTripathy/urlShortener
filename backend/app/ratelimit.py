"""Per-key rate limiting: Redis (shared across workers/instances) or in-process fallback."""

import time
from collections import defaultdict, deque
from typing import Protocol


class Limiter(Protocol):
    async def allow(self, key: str) -> bool: ...


class MemoryRateLimiter:
    """Sliding window, per process. Used when Redis isn't configured."""

    def __init__(self, limit: int, window: float = 60.0) -> None:
        self.limit, self.window = limit, window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def allow(self, key: str) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


class RedisRateLimiter:
    """Fixed window shared by every worker: INCR + EXPIRE in one round trip."""

    def __init__(self, redis, limit: int, window: int = 60) -> None:
        self._r, self.limit, self.window = redis, limit, window

    async def allow(self, key: str) -> bool:
        bucket = f"rl:{key}:{int(time.time() // self.window)}"
        async with self._r.pipeline(transaction=True) as p:
            count, _ = await p.incr(bucket).expire(bucket, self.window).execute()
        return count <= self.limit
