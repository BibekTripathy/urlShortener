"""Redis code paths, exercised against fakeredis (no server needed)."""

from datetime import UTC, datetime

import pytest
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient

from app.cache import RedisCache
from app.config import Settings
from app.main import create_app
from app.ratelimit import RedisRateLimiter


@pytest.fixture
def redis():
    return FakeAsyncRedis()


async def test_redis_cache_roundtrip(redis):
    c = RedisCache(redis, ttl=60)
    exp = datetime(2030, 1, 1, tzinfo=UTC)
    await c.set("abc", ("https://x", exp))
    assert await c.get("abc") == ("https://x", exp)
    assert await c.get("missing") is None
    assert 0 < await redis.ttl("l:abc") <= 60


async def test_redis_rate_limiter_shared_across_instances(redis):
    # two limiter objects = two workers sharing one Redis
    a, b = RedisRateLimiter(redis, limit=3), RedisRateLimiter(redis, limit=3)
    results = [await a.allow("ip"), await b.allow("ip"), await a.allow("ip"), await b.allow("ip")]
    assert results == [True, True, True, False]
    assert await a.allow("other-ip")


async def test_app_with_redis(tmp_path, redis):
    s = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path}/r.db", base_url="http://sho.rt",
                 rate_limit_per_minute=2)
    app = create_app(s, redis=redis)
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app), AsyncClient(
        transport=transport, base_url="http://t"
    ) as c:
        r = await c.post("/api/v1/links", json={"url": "https://example.com"})
        code = r.json()["code"]
        assert await redis.get(f"l:{code}") is not None
        assert (await c.get(f"/{code}")).headers["location"] == "https://example.com"
        await c.post("/api/v1/links", json={"url": "https://example.com"})
        assert (await c.post("/api/v1/links", json={"url": "https://e.com"})).status_code == 429
