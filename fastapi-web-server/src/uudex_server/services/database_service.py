from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from uudex_server.core.settings import get_settings

# Lazy loaded engine and session
_engine = None
_async_session = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.db_uri, echo=False, future=True)
    return _engine


def get_async_session():
    global _async_session
    if _async_session is None:
        _async_session = sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _async_session


async def init_db():
    async with get_engine().begin() as conn:
        # Create tables
        await conn.run_sync(SQLModel.metadata.create_all)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session"""
    session = get_async_session()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# For FastAPI dependency injection
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_db_session() as session:
        yield session


async def shutdown_db():
    """Cleanup database connections"""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


if __name__ == "__main__":
    from sqlmodel import select

    from uudex_server.models import Participant
    # from uudex_server.app.model import Participant

    settings = get_settings(".env-develop")
    session = get_db_session()
    statement = select(Participant)
    results = session.exec(statement)
    for rdr in results:
        print(rdr)

    # with create_session() as session:
    #     statement = select(Participant)
    #     results = session.exec(statement)
    #     for rdr in results:
    #         print(rdr)
