import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from . import service
from .cache import Cache, MemoryCache, RedisCache
from .clicks import ClickBuffer, MemoryClickBuffer, RedisClickBuffer, flush, flush_forever
from .config import Settings, get_settings
from .db import Database
from .models import Link
from .ratelimit import Limiter, MemoryRateLimiter, RedisRateLimiter
from .schemas import ALIAS_RE, LinkCreate, LinkOut


def create_app(settings: Settings | None = None, redis=None) -> FastAPI:
    settings = settings or get_settings()
    db = Database(settings.database_url)
    if redis is None and settings.redis_url:
        from redis.asyncio import Redis

        redis = Redis.from_url(settings.redis_url)
    cache: Cache
    limiter: Limiter
    clicks: ClickBuffer
    if redis is not None:
        cache = RedisCache(redis, settings.cache_ttl_seconds)
        limiter = RedisRateLimiter(redis, settings.rate_limit_per_minute)
        clicks = RedisClickBuffer(redis)
    else:
        cache = MemoryCache(settings.cache_max_items, settings.cache_ttl_seconds)
        limiter = MemoryRateLimiter(settings.rate_limit_per_minute)
        clicks = MemoryClickBuffer()
    own_host = urlsplit(settings.base_url).hostname or ""

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.auto_create_tables:
            await db.create_all()
        flusher = asyncio.create_task(
            flush_forever(clicks, db.sessionmaker, settings.click_flush_seconds)
        )
        yield
        flusher.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await flusher
        await flush(clicks, db.sessionmaker)  # don't lose buffered clicks on shutdown
        await cache.close()
        await db.dispose()

    app = FastAPI(title="urlShortener API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.state.db, app.state.cache, app.state.clicks = db, cache, clicks
    Session = Annotated[AsyncSession, Depends(db.session)]

    def to_out(link: Link, pending: int = 0) -> LinkOut:
        return LinkOut(
            code=link.code,
            short_url=f"{settings.base_url.rstrip('/')}/{link.code}",
            url=link.url,
            clicks=link.clicks + pending,
            created_at=link.created_at,
            expires_at=link.expires_at,
        )

    def guard(fn):
        async def run(*a, **kw):
            try:
                return await fn(*a, **kw)
            except service.LinkError as e:
                raise HTTPException(e.status, e.detail) from None
        return run

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.post("/api/v1/links", status_code=201, response_model=LinkOut)
    async def create(body: LinkCreate, request: Request, s: Session) -> LinkOut:
        ip = request.client.host if request.client else "unknown"
        if not await limiter.allow(ip):
            raise HTTPException(429, "rate limit exceeded")

        async def work() -> LinkOut:
            service.validate_url(body.url, settings.max_url_length, own_host)
            link = await service.create_link(
                s, body.url, body.alias, body.expires_in_days, settings.code_length
            )
            await cache.set(link.code, (link.url, link.expires_at))
            return to_out(link)

        return await guard(work)()

    @app.get("/api/v1/links/{code}", response_model=LinkOut)
    async def info(code: str, s: Session) -> LinkOut:
        link = await service.get_link(s, code)
        if link is None:
            raise HTTPException(404, "link not found")
        return to_out(link, await clicks.pending(code))

    @app.get("/{code}", include_in_schema=False)
    async def redirect(code: str) -> RedirectResponse:
        if not ALIAS_RE.fullmatch(code):
            raise HTTPException(404, "link not found")
        entry = await cache.get(code)
        if entry is None:
            async with db.sessionmaker() as s:
                link = await service.get_link(s, code)
            if link is None:
                raise HTTPException(404, "link not found")
            entry = (link.url, link.expires_at)
            await cache.set(code, entry)
        url, expires_at = entry
        if service.is_expired(expires_at):
            raise HTTPException(410, "link expired")
        await clicks.incr(code)
        return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})

    return app


app = create_app()
