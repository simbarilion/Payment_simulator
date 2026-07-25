"""Тесты приёма callback-квитанций POST /receipts"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Operation, OperationEvent, OperationStatus


def _receipt_payload(
    *,
    operation_id: str = "operation-receipt",
    provider_payment_id: str = "aa5b7856-e9f2-4fd5-955b-38b1f28d9c57",
    result: str = "COMPLETED",
    message: str = "Payment completed",
) -> dict[str, object]:
    """Собирает тело квитанции по контракту провайдера"""
    return {
        "providerPaymentId": provider_payment_id,
        "operationId": operation_id,
        "result": result,
        "message": message,
        "occurredAt": "2026-07-15T12:00:00Z",
    }


@pytest.mark.asyncio
async def test_receipt_completed_finalizes_operation(
    client: AsyncClient,
    create_operation: Callable[..., Awaitable[None]],
    db_session: AsyncSession,
) -> None:
    """Квитанция COMPLETED переводит PROCESSING в COMPLETED и пишет событие"""
    await create_operation("operation-receipt")
    await client.post("/operations/operation-receipt/submit")

    response = await client.post("/receipts", json=_receipt_payload())

    assert response.status_code == 204
    operation = await db_session.get(Operation, "operation-receipt")
    assert operation is not None
    assert operation.status == OperationStatus.COMPLETED
    assert operation.provider_payment_id == "aa5b7856-e9f2-4fd5-955b-38b1f28d9c57"

    events = (
        await db_session.scalars(
            select(OperationEvent)
            .where(OperationEvent.operation_id == "operation-receipt")
            .order_by(OperationEvent.event_id)
        )
    ).all()
    assert [e.type for e in events] == ["CREATED", "PROCESSING", "COMPLETED"]


@pytest.mark.asyncio
async def test_early_receipt_sets_provider_payment_id_before_submit_response(
    client: AsyncClient,
    create_operation: Callable[..., Awaitable[None]],
    db_session: AsyncSession,
) -> None:
    """Ранняя квитанция до ответа провайдера выставляет providerPaymentId и финализирует"""
    await create_operation("operation-early")
    await client.post("/operations/operation-early/submit")
    operation = await db_session.get(Operation, "operation-early")
    assert operation is not None
    operation.provider_payment_id = None
    await db_session.commit()

    response = await client.post(
        "/receipts",
        json=_receipt_payload(operation_id="operation-early", result="REJECTED", message="Payment rejected"),
    )

    assert response.status_code == 204
    operation = await db_session.get(Operation, "operation-early")
    assert operation is not None
    assert operation.status == OperationStatus.REJECTED
    assert operation.provider_payment_id == "aa5b7856-e9f2-4fd5-955b-38b1f28d9c57"


@pytest.mark.asyncio
async def test_duplicate_receipt_does_not_add_second_transition(
    client: AsyncClient,
    create_operation: Callable[..., Awaitable[None]],
    db_session: AsyncSession,
) -> None:
    """Повтор той же квитанции отвечает 204 и не создаёт второй переход"""
    await create_operation("operation-dup-receipt")
    await client.post("/operations/operation-dup-receipt/submit")
    payload = _receipt_payload(operation_id="operation-dup-receipt")
    assert (await client.post("/receipts", json=payload)).status_code == 204

    response = await client.post("/receipts", json=payload)

    assert response.status_code == 204
    events = (
        await db_session.scalars(
            select(OperationEvent)
            .where(OperationEvent.operation_id == "operation-dup-receipt")
            .order_by(OperationEvent.event_id)
        )
    ).all()
    assert [e.type for e in events] == ["CREATED", "PROCESSING", "COMPLETED"]


@pytest.mark.asyncio
async def test_late_opposite_receipt_is_ignored(
    client: AsyncClient,
    create_operation: Callable[..., Awaitable[None]],
    db_session: AsyncSession,
) -> None:
    """Поздняя квитанция с противоположным результатом не меняет финальный статус"""
    await create_operation("operation-late")
    await client.post("/operations/operation-late/submit")
    await client.post("/receipts", json=_receipt_payload(operation_id="operation-late"))

    response = await client.post(
        "/receipts",
        json=_receipt_payload(
            operation_id="operation-late",
            result="REJECTED",
            message="Late reject",
        ),
    )

    assert response.status_code == 204
    operation = await db_session.get(Operation, "operation-late")
    assert operation is not None
    assert operation.status == OperationStatus.COMPLETED

    events = (
        await db_session.scalars(
            select(OperationEvent)
            .where(OperationEvent.operation_id == "operation-late")
            .order_by(OperationEvent.event_id)
        )
    ).all()
    assert [e.type for e in events] == ["CREATED", "PROCESSING", "COMPLETED", "RECEIPT_IGNORED"]
    assert events[-1].from_status == "COMPLETED"
    assert events[-1].to_status == "COMPLETED"


@pytest.mark.asyncio
async def test_mismatched_provider_payment_id_returns_409(
    client: AsyncClient,
    create_operation: Callable[..., Awaitable[None]],
    db_session: AsyncSession,
) -> None:
    """Несовпадающий providerPaymentId после установления связи возвращает 409"""
    await create_operation("operation-conflict")
    await client.post("/operations/operation-conflict/submit")
    operation = await db_session.get(Operation, "operation-conflict")
    assert operation is not None
    assert operation.provider_payment_id is not None

    response = await client.post(
        "/receipts",
        json=_receipt_payload(
            operation_id="operation-conflict",
            provider_payment_id="other-provider-payment-id",
        ),
    )

    assert response.status_code == 409
    assert response.json()["error"] == "provider_payment_id_conflict"


@pytest.mark.asyncio
async def test_receipt_for_missing_operation_returns_404(client: AsyncClient) -> None:
    """Квитанция по неизвестной операции возвращает 404"""
    response = await client.post("/receipts", json=_receipt_payload(operation_id="missing"))
    assert response.status_code == 404
