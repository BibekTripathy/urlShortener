from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from app.models import Link


async def shorten(client, **body):
    return await client.post("/api/v1/links", json=body)


async def test_health(client):
    r = await client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


async def test_create_and_redirect(client):
    r = await shorten(client, url="https://example.com/a?b=1")
    assert r.status_code == 201
    data = r.json()
    assert len(data["code"]) == 7
    assert data["short_url"] == f"http://sho.rt/{data['code']}"
    rr = await client.get(f"/{data['code']}")
    assert rr.status_code == 302
    assert rr.headers["location"] == "https://example.com/a?b=1"
    assert rr.headers["cache-control"] == "no-store"


async def test_clicks_counted(client):
    code = (await shorten(client, url="https://example.com")).json()["code"]
    for _ in range(3):
        await client.get(f"/{code}")
    info = await client.get(f"/api/v1/links/{code}")
    assert info.json()["clicks"] == 3


async def test_custom_alias_and_conflict(client):
    r = await shorten(client, url="https://example.com", alias="my-link")
    assert r.status_code == 201 and r.json()["code"] == "my-link"
    r2 = await shorten(client, url="https://other.com", alias="my-link")
    assert r2.status_code == 409


@pytest.mark.parametrize("alias", ["ab", "has space", "x" * 33, "api", "docs", "bad/slash"])
async def test_invalid_alias(client, alias):
    assert (await shorten(client, url="https://example.com", alias=alias)).status_code == 422


@pytest.mark.parametrize(
    "url", ["ftp://example.com", "javascript:alert(1)", "example.com", "http://", "",
            "https://sho.rt/abc", "https://e.com/" + "a" * 2100],
)
async def test_invalid_urls(client, url):
    assert (await shorten(client, url=url)).status_code == 422


async def test_unknown_code(client):
    assert (await client.get("/nope123")).status_code == 404
    assert (await client.get("/api/v1/links/nope123")).status_code == 404


async def test_expiry(client):
    r = await shorten(client, url="https://example.com", expires_in_days=1)
    data = r.json()
    assert data["expires_at"] is not None
    # force expiry in DB and bypass cache
    async with client.app.state.db.sessionmaker() as s:
        link = (await s.execute(Link.__table__.select().where(Link.code == data["code"]))).first()
        await s.execute(
            Link.__table__.update().where(Link.id == link.id)
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await s.commit()
    await client.app.state.cache.close()
    assert (await client.get(f"/{data['code']}")).status_code == 410


async def test_expiry_bounds(client):
    assert (await shorten(client, url="https://e.com", expires_in_days=0)).status_code == 422


async def test_redirect_served_from_cache(client):
    code = (await shorten(client, url="https://example.com/cached")).json()["code"]
    assert await client.app.state.cache.get(code) is not None
    assert (await client.get(f"/{code}")).headers["location"] == "https://example.com/cached"


async def test_rate_limit(tmp_path):
    s = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path}/rl.db", base_url="http://sho.rt",
                 rate_limit_per_minute=2)
    app = create_app(s)
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app), AsyncClient(
        transport=transport, base_url="http://t"
    ) as c:
        codes = [(await shorten(c, url="https://e.com")).status_code for _ in range(3)]
    assert codes == [201, 201, 429]


async def test_cors(client):
    r = await client.options("/api/v1/links", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
