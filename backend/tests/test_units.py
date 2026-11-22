import asyncio
from datetime import UTC, datetime, timedelta

from app.cache import MemoryCache, _dump, _load
from app.ratelimit import RateLimiter
from app.service import is_expired, new_code


def test_new_code_alphabet_and_uniqueness():
    codes = {new_code(7) for _ in range(5000)}
    assert len(codes) == 5000
    assert all(c.isalnum() and len(c) == 7 for c in codes)


def test_is_expired_handles_naive_and_none():
    assert not is_expired(None)
    assert is_expired(datetime.now(UTC) - timedelta(seconds=1))
    assert is_expired((datetime.now(UTC) - timedelta(seconds=1)).replace(tzinfo=None))
    assert not is_expired(datetime.now(UTC) + timedelta(days=1))


async def test_memory_cache_lru_eviction():
    c = MemoryCache(max_items=2, ttl=60)
    await c.set("a", ("1", None))
    await c.set("b", ("2", None))
    await c.get("a")
    await c.set("c", ("3", None))
    assert await c.get("b") is None and await c.get("a") == ("1", None)


async def test_memory_cache_ttl():
    c = MemoryCache(max_items=10, ttl=0)
    await c.set("a", ("1", None))
    await asyncio.sleep(0.01)
    assert await c.get("a") is None


def test_cache_serialization_roundtrip():
    exp = datetime(2030, 1, 1, tzinfo=UTC)
    assert _load(_dump(("https://x", exp))) == ("https://x", exp)
    assert _load(_dump(("https://x", None))) == ("https://x", None)


def test_rate_limiter():
    rl = RateLimiter(limit=2, window=60)
    assert [rl.allow("ip"), rl.allow("ip"), rl.allow("ip"), rl.allow("other")] == [
        True, True, False, True]
