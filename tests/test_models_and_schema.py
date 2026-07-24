"""Тесты инициализации схемы SQLite и ORM-моделей операций"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Operation, OperationEvent, OperationStatus


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
    """Событие истории связано с операцией и хранит event_id"""
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
