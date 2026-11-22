from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./dev.db"
    redis_url: str | None = None
    base_url: str = "http://localhost:8000"
    cors_origins: list[str] = ["http://localhost:5173"]
    code_length: int = 7
    max_url_length: int = 2048
    cache_ttl_seconds: int = 3600
    cache_max_items: int = 10_000
    rate_limit_per_minute: int = 30
    auto_create_tables: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
