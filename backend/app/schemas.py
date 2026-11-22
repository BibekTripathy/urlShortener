import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

ALIAS_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
RESERVED = {"api", "docs", "redoc", "openapi.json", "healthz", "assets", "static", "favicon.ico"}


class LinkCreate(BaseModel):
    url: str = Field(min_length=1)
    alias: str | None = None
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)

    @field_validator("url")
    @classmethod
    def strip_url(cls, v: str) -> str:
        return v.strip()

    @field_validator("alias")
    @classmethod
    def check_alias(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not ALIAS_RE.fullmatch(v):
            raise ValueError("alias must be 3-32 chars: letters, digits, '-' or '_'")
        if v.lower() in RESERVED:
            raise ValueError("alias is reserved")
        return v


class LinkOut(BaseModel):
    code: str
    short_url: str
    url: str
    clicks: int
    created_at: datetime
    expires_at: datetime | None
