import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db",
        redis_url=None,
        base_url="http://sho.rt",
        rate_limit_per_minute=1000,
    )


@pytest.fixture
async def client(settings):
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app), AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        c.app = app
        yield c
