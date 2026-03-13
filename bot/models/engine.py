# bot/models/engine.py
import logging
import asyncio
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import redis.asyncio as aioredis
from bot.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()

engine = create_async_engine(
    _settings.async_database_url,
    pool_size=_settings.DB_POOL_SIZE,
    max_overflow=_settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=_settings.DB_POOL_RECYCLE,
    echo=False,
)

AsyncSessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_bot_loop: asyncio.AbstractEventLoop | None = None


def get_bot_loop() -> asyncio.AbstractEventLoop | None:
    return _bot_loop


class _RedisProxy:
    __slots__ = ("_client",)

    def __init__(self):
        self._client: aioredis.Redis | None = None

    def _init_client(self, url: str, **kwargs):
        self._client = aioredis.from_url(url, **kwargs)

    async def _close_client(self):
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None

    def __getattr__(self, name: str):
        c = self._client
        if c is None:
            raise RuntimeError("Redis not initialised – call init_db() first")
        return getattr(c, name)


redis_client: aioredis.Redis = _RedisProxy()  # type: ignore[assignment]


@asynccontextmanager
async def get_session():
    session = AsyncSessionFactory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db():
    global _bot_loop
    _bot_loop = asyncio.get_running_loop()

    await redis_client._close_client()
    redis_client._init_client(
        _settings.REDIS_URL,
        decode_responses=True,
        max_connections=20,
    )
    await redis_client.ping()
    logger.info("Redis connected on bot event loop")

    from bot.models.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialised")


async def close_db():
    await engine.dispose()
    await redis_client._close_client()
    logger.info("Database and Redis connections closed")