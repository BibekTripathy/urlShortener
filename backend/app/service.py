import secrets
import string
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Link

ALPHABET = string.ascii_letters + string.digits


class LinkError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status, self.detail = status, detail


def new_code(length: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def validate_url(url: str, max_len: int, own_host: str) -> None:
    if len(url) > max_len:
        raise LinkError(422, f"url longer than {max_len} characters")
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise LinkError(422, "url must be an absolute http(s) URL")
    if parts.hostname.lower() == own_host.lower():
        raise LinkError(422, "cannot shorten links to this service")


def is_expired(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:  # SQLite drops tzinfo
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC)


async def create_link(
    s: AsyncSession, url: str, alias: str | None, expires_in_days: int | None, code_len: int
) -> Link:
    expires_at = datetime.now(UTC) + timedelta(days=expires_in_days) if expires_in_days else None
    attempts = 1 if alias else 5
    for _ in range(attempts):
        link = Link(code=alias or new_code(code_len), url=url, expires_at=expires_at, clicks=0)
        s.add(link)
        try:
            await s.commit()
            return link
        except IntegrityError:
            await s.rollback()
    if alias:
        raise LinkError(409, "alias already taken")
    raise LinkError(503, "could not allocate a code, try again")


async def get_link(s: AsyncSession, code: str) -> Link | None:
    return (await s.execute(select(Link).where(Link.code == code))).scalar_one_or_none()


async def add_click(s: AsyncSession, code: str) -> None:
    await s.execute(update(Link).where(Link.code == code).values(clicks=Link.clicks + 1))
    await s.commit()
