# bot/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    BOT_TOKEN: str
    USE_WEBHOOK: bool = False
    WEBHOOK_URL: str = ""
    WEBHOOK_SECRET: str = ""
    WEBHOOK_PORT: int = 8443
    WEBHOOK_PATH: str = "/webhook"

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"

    TMDB_API_KEY: str
    TMDB_BASE_URL: str = "https://api.themoviedb.org/3"
    TMDB_IMG_BASE: str = "https://image.tmdb.org/t/p"

    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 1500

    YOUTUBE_API_KEY: str
    YOUTUBE_BASE_URL: str = "https://www.googleapis.com/youtube/v3"

    STREAMING_API_KEY: str
    STREAMING_API_HOST: str = "streaming-availability.p.rapidapi.com"

    ADMIN_IDS: list[int] = []

    FREE_DAILY_SEARCHES: int = 10
    FREE_DAILY_EXPLAINS: int = 3
    FREE_DAILY_RECOMMENDS: int = 5
    FREE_WATCHLIST_LIMIT: int = 20
    REDEEM_HOURLY_LIMIT: int = 5
    REDEEM_DAILY_LIMIT: int = 10

    CACHE_MOVIE_TTL: int = 86400
    CACHE_SEARCH_TTL: int = 21600
    CACHE_STREAMING_TTL: int = 43200

    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 1800

    ITEMS_PER_PAGE: int = 5

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif not url.startswith("postgresql+asyncpg://"):
            url = f"postgresql+asyncpg://{url}"
        return url

    @property
    def webhook_full_url(self) -> str:
        return f"{self.WEBHOOK_URL}{self.WEBHOOK_PATH}"


@lru_cache
def get_settings() -> Settings:
    return Settings()