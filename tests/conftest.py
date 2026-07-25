"""Общие фикстуры тестов"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.dependencies import provider_client_dep
from app.db.dependencies import get_session
from app.main import app
from app.models import Base
from app.services.provider_service import ProviderClient, ProviderPaymentAccepted


def _create_all(connection: Connection) -> None:
    """Синхронно создаёт таблицы для тестовой БД"""
    Base.metadata.create_all(bind=connection)


@pytest.fixture
async def db_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """Создаёт временный async-движок SQLite со схемой"""
    db_file = tmp_path / "test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file.as_posix()}",
        connect_args={"timeout": 30},
    )
    async with engine.begin() as conn:
        await conn.run_sync(_create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Фабрика сессий на тестовом движке"""
    return async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Отдаёт сессию тестовой БД"""
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client_test_db(db_session: AsyncSession):
    """HTTP-клиент с подменой сессии БД на тестовую (без мока провайдера)"""

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest.fixture
def provider() -> ProviderClient:
    """Клиент провайдера-заглушка с успешным 202"""
    client = MagicMock(spec=ProviderClient)
    client.create_payment_with_retries = AsyncMock(
        return_value=ProviderPaymentAccepted(
            provider_payment_id="aa5b7856-e9f2-4fd5-955b-38b1f28d9c57",
            status="ACCEPTED",
        )
    )
    return client


@pytest.fixture
async def client(db_session: AsyncSession, provider: ProviderClient):
    """HTTP-клиент с тестовой БД и заглушкой провайдера"""

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[provider_client_dep] = lambda: provider
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest.fixture
def create_operation(client: AsyncClient) -> Callable[..., Awaitable[None]]:
    """Фабрика создания операции через API для сценариев submit/events"""

    async def _create(
        operation_id: str,
        *,
        amount: str = "1000.00",
        currency: str = "RUB",
        description: str | None = "Оплата заказа",
    ) -> None:
        payload: dict[str, object] = {
            "operationId": operation_id,
            "amount": amount,
            "currency": currency,
        }
        if description is not None:
            payload["description"] = description
        response = await client.post("/operations", json=payload)
        assert response.status_code == 201

    return _create
