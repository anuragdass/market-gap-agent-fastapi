from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import Base


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=get_engine(), expire_on_commit=False)


async def init_db_schema() -> None:
    """Dev/test convenience only: creates tables directly for the SQLite
    fallback. Postgres schema is owned by Alembic migrations -- see
    `migrations/` and `make migrate` -- and is never auto-created here.
    """
    settings = get_settings()
    if not settings.database_url.startswith("sqlite"):
        return
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
