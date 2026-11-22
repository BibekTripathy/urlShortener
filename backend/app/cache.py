"""Redirect cache: Redis when configured, otherwise an in-process LRU."""

import json
import time
from collections import OrderedDict
from datetime import datetime
from typing import Protocol

CacheEntry = tuple[str, datetime | None]  # (url, expires_at)


class Cache(Protocol):
    async def get(self, code: str) -> CacheEntry | None: ...
    async def set(self, code: str, entry: CacheEntry) -> None: ...
    async def close(self) -> None: ...


def _dump(entry: CacheEntry) -> str:
    url, exp = entry
    return json.dumps([url, exp.isoformat() if exp else None])


def _load(raw: str | bytes) -> CacheEntry:
    url, exp = json.loads(raw)
    return url, datetime.fromisoformat(exp) if exp else None


class MemoryCache:
    def __init__(self, max_items: int, ttl: int) -> None:
        self._data: OrderedDict[str, tuple[float, CacheEntry]] = OrderedDict()
        self.max_items, self.ttl = max_items, ttl

    async def get(self, code: str) -> CacheEntry | None:
        item = self._data.get(code)
        if item is None:
            return None
        stored_at, entry = item
        if time.monotonic() - stored_at > self.ttl:
            self._data.pop(code, None)
            return None
        self._data.move_to_end(code)
        return entry

    async def set(self, code: str, entry: CacheEntry) -> None:
        self._data[code] = (time.monotonic(), entry)
        self._data.move_to_end(code)
        while len(self._data) > self.max_items:
            self._data.popitem(last=False)

    async def close(self) -> None:
        self._data.clear()


class RedisCache:
    def __init__(self, redis, ttl: int) -> None:
        self._r, self.ttl = redis, ttl

    async def get(self, code: str) -> CacheEntry | None:
        raw = await self._r.get(f"l:{code}")
        return _load(raw) if raw else None

    async def set(self, code: str, entry: CacheEntry) -> None:
        await self._r.set(f"l:{code}", _dump(entry), ex=self.ttl)

    async def close(self) -> None:
        await self._r.aclose()
