"""Тесты создания операции POST /operations"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Operation, OperationEvent, OperationStatus


@pytest.mark.asyncio
async def test_create_operation_returns_201(client: AsyncClient) -> None:
    """POST /operations создаёт операцию в CREATED и возвращает 201"""
    response = await client.post(
        "/operations",
        json={
            "operationId": "operation-123",
            "amount": "1000.00",
            "currency": "RUB",
            "description": "Оплата заказа",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "operationId": "operation-123",
        "amount": "1000.00",
        "currency": "RUB",
        "description": "Оплата заказа",
        "status": "CREATED",
        "providerPaymentId": None,
    }


@pytest.mark.asyncio
async def test_create_operation_persists_created_event(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """При создании фиксируется событие CREATED с event_id=1"""
    await client.post(
        "/operations",
        json={
            "operationId": "operation-evt",
            "amount": "10.50",
            "currency": "RUB",
            "description": None,
        },
    )

    operation = await db_session.get(Operation, "operation-evt")
    assert operation is not None
    assert operation.status == OperationStatus.CREATED
    assert operation.submit_intent is False

    events = (
        await db_session.scalars(
            select(OperationEvent)
            .where(OperationEvent.operation_id == "operation-evt")
            .order_by(OperationEvent.event_id)
        )
    ).all()
    assert len(events) == 1
    assert events[0].event_id == 1
    assert events[0].type == "CREATED"
    assert events[0].from_status is None
    assert events[0].to_status == "CREATED"


@pytest.mark.asyncio
async def test_create_operation_duplicate_returns_409(client: AsyncClient) -> None:
    """Повторное создание того же operationId возвращает 409"""
    payload = {
        "operationId": "operation-dup",
        "amount": "1.00",
        "currency": "RUB",
        "description": "dup",
    }
    assert (await client.post("/operations", json=payload)).status_code == 201
    response = await client.post("/operations", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "amount",
    ["0", "0.00", "-1.00", "10.123", "abc", ""],
)
async def test_create_operation_rejects_invalid_amount(client: AsyncClient, amount: str) -> None:
    """Некорректный amount отклоняется валидацией"""
    response = await client.post(
        "/operations",
        json={
            "operationId": f"op-bad-{amount or 'empty'}",
            "amount": amount,
            "currency": "RUB",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_operation_rejects_non_rub_currency(client: AsyncClient) -> None:
    """Валюта кроме RUB отклоняется"""
    response = await client.post(
        "/operations",
        json={
            "operationId": "operation-usd",
            "amount": "10.00",
            "currency": "USD",
        },
    )
    assert response.status_code == 422
