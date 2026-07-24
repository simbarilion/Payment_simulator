"""Тесты инициализации схемы SQLite и ORM-моделей операций"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Operation, OperationEvent, OperationStatus
from app.models.base import Base


@pytest.fixture
async def db_session(tmp_path: Path):
    """Создаёт временную SQLite БД и отдаёт сессию"""
    db_file = tmp_path / "test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file.as_posix()}",
        connect_args={"timeout": 30},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_all_creates_operation_tables(tmp_path: Path) -> None:
    """create_all создаёт таблицы operations и operation_events"""
    db_file = tmp_path / "schema.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file.as_posix()}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        table_names = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())

    await engine.dispose()

    assert "operations" in table_names
    assert "operation_events" in table_names


@pytest.mark.asyncio
async def test_operation_persists_created_state(db_session: AsyncSession) -> None:
    """Операция сохраняется со статусом CREATED и пустым providerPaymentId"""
    operation = Operation(
        operation_id="operation-123",
        amount="1000.00",
        currency="RUB",
        description="Оплата заказа",
        status=OperationStatus.CREATED,
        provider_payment_id=None,
        submit_intent=False,
    )
    db_session.add(operation)
    await db_session.commit()

    loaded = await db_session.scalar(select(Operation).where(Operation.operation_id == "operation-123"))

    assert loaded is not None
    assert loaded.status == OperationStatus.CREATED
    assert loaded.amount == "1000.00"
    assert loaded.currency == "RUB"
    assert loaded.provider_payment_id is None
    assert loaded.submit_intent is False


@pytest.mark.asyncio
async def test_operation_event_linked_with_monotonic_event_id(db_session: AsyncSession) -> None:
    """Событие истории связано с операцией и хранит монотонный event_id"""
    operation = Operation(
        operation_id="operation-456",
        amount="10.50",
        currency="RUB",
        description=None,
        status=OperationStatus.CREATED,
        provider_payment_id=None,
        submit_intent=False,
    )
    db_session.add(operation)
    await db_session.flush()

    event = OperationEvent(
        operation_id=operation.operation_id,
        event_id=1,
        type="CREATED",
        from_status=None,
        to_status=OperationStatus.CREATED.value,
        message="Operation created",
        occurred_at=datetime(2026, 7, 15, 12, 0, 0, tzinfo=UTC),
    )
    db_session.add(event)
    await db_session.commit()

    loaded_events = (
        await db_session.scalars(
            select(OperationEvent)
            .where(OperationEvent.operation_id == "operation-456")
            .order_by(OperationEvent.event_id)
        )
    ).all()

    assert len(loaded_events) == 1
    assert loaded_events[0].event_id == 1
    assert loaded_events[0].type == "CREATED"
    assert loaded_events[0].from_status is None
    assert loaded_events[0].to_status == "CREATED"
