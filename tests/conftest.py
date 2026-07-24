"""Общие фикстуры тестов"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.dependencies import get_session
from app.main import app
from app.models import Base


def _create_all(connection: Connection) -> None:
    """Синхронно создаёт таблицы для тестовой БД"""
    Base.metadata.create_all(bind=connection)


@pytest.fixture
async def db_session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    """Создаёт временную SQLite БД и отдаёт сессию"""
    db_file = tmp_path / "test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file.as_posix()}",
        connect_args={"timeout": 30},
    )
    async with engine.begin() as conn:
        await conn.run_sync(_create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession):
    """HTTP-клиент с подменой сессии БД на тестовую"""

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()
