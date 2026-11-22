"""Click buffering: redirects only bump a counter; a flusher writes batches to the DB.

Avoids one UPDATE per redirect (row-lock contention on popular links, pool starvation).
"""

import asyncio
import logging
import uuid
from collections import Counter
from typing import Protocol

from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from .models import Link

log = logging.getLogger(__name__)
PENDING = "clicks:pending"


class ClickBuffer(Protocol):
    async def incr(self, code: str) -> None: ...
    async def pending(self, code: str) -> int: ...
    async def drain(self) -> dict[str, int]: ...


class MemoryClickBuffer:
    def __init__(self) -> None:
        self._c: Counter[str] = Counter()

    async def incr(self, code: str) -> None:
        self._c[code] += 1

    async def pending(self, code: str) -> int:
        return self._c[code]

    async def drain(self) -> dict[str, int]:
        out, self._c = dict(self._c), Counter()
        return out


class RedisClickBuffer:
    """Shared by all workers. drain() atomically RENAMEs the hash so no click is lost
    or double-counted, even with several workers flushing at once."""

    def __init__(self, redis) -> None:
        self._r = redis

    async def incr(self, code: str) -> None:
        await self._r.hincrby(PENDING, code, 1)

    async def pending(self, code: str) -> int:
        return int(await self._r.hget(PENDING, code) or 0)

    async def drain(self) -> dict[str, int]:
        tmp = f"clicks:flushing:{uuid.uuid4().hex}"
        try:
            await self._r.rename(PENDING, tmp)
        except Exception as e:  # no such key → nothing to flush
            if "no such key" in str(e).lower():
                return {}
            raise
        raw = await self._r.hgetall(tmp)
        await self._r.delete(tmp)
        return {k.decode() if isinstance(k, bytes) else k: int(v) for k, v in raw.items()}


async def flush(buf: ClickBuffer, sessionmaker: async_sessionmaker) -> int:
    counts = await buf.drain()
    if not counts:
        return 0
    async with sessionmaker() as s:
        for code, n in sorted(counts.items()):  # sorted → consistent lock order
            await s.execute(update(Link).where(Link.code == code).values(clicks=Link.clicks + n))
        await s.commit()
    return sum(counts.values())


async def flush_forever(buf: ClickBuffer, sessionmaker: async_sessionmaker, every: float) -> None:
    while True:
        await asyncio.sleep(every)
        try:
            await flush(buf, sessionmaker)
        except Exception:
            log.exception("click flush failed")
