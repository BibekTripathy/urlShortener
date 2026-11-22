import asyncio

import pytest
from fakeredis import FakeAsyncRedis

from app.clicks import MemoryClickBuffer, RedisClickBuffer, flush


@pytest.fixture(params=["memory", "redis"])
def buf(request):
    return MemoryClickBuffer() if request.param == "memory" else RedisClickBuffer(FakeAsyncRedis())


async def test_buffer_counts_and_drains(buf):
    for c in ["a", "a", "b"]:
        await buf.incr(c)
    assert await buf.pending("a") == 2
    assert await buf.drain() == {"a": 2, "b": 1}
    assert await buf.drain() == {}
    assert await buf.pending("a") == 0


async def test_concurrent_incr_while_draining_loses_nothing(buf):
    total = 0

    async def clicker():
        for _ in range(200):
            await buf.incr("x")
            await asyncio.sleep(0)

    async def drainer():
        nonlocal total
        for _ in range(20):
            total += (await buf.drain()).get("x", 0)
            await asyncio.sleep(0)

    await asyncio.gather(clicker(), clicker(), drainer())
    total += (await buf.drain()).get("x", 0)
    assert total == 400


async def test_flush_writes_batched_counts(client):
    code = (await client.post("/api/v1/links", json={"url": "https://e.com"})).json()["code"]
    for _ in range(5):
        await client.get(f"/{code}")
    app = client.app
    assert await app.state.clicks.pending(code) == 5
    assert await flush(app.state.clicks, app.state.db.sessionmaker) == 5
    assert await app.state.clicks.pending(code) == 0
    # DB now holds the count; API reports DB + pending
    await client.get(f"/{code}")
    assert (await client.get(f"/api/v1/links/{code}")).json()["clicks"] == 6


async def test_buffered_clicks_flushed_on_shutdown(settings):
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    settings.click_flush_seconds = 3600  # periodic flush never fires during the test
    app = create_app(settings)
    async with app.router.lifespan_context(app), AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t"
    ) as c:
        code = (await c.post("/api/v1/links", json={"url": "https://e.com"})).json()["code"]
        await c.get(f"/{code}")
        await c.get(f"/{code}")
    app2 = create_app(settings)  # fresh process, empty buffer → reads DB only
    async with app2.router.lifespan_context(app2), AsyncClient(
        transport=ASGITransport(app=app2), base_url="http://t"
    ) as c:
        assert (await c.get(f"/api/v1/links/{code}")).json()["clicks"] == 2
