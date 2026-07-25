"""Тесты отправки операции POST /operations/{id}/submit"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Operation, OperationEvent, OperationStatus
from app.services.provider_service import ProviderClient, ProviderPaymentAccepted


async def _create(client: AsyncClient, operation_id: str) -> None:
    """Создаёт операцию для сценариев submit"""
    response = await client.post(
        "/operations",
        json={
            "operationId": operation_id,
            "amount": "1000.00",
            "currency": "RUB",
            "description": "Оплата заказа",
        },
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_first_submit_returns_202_and_calls_provider(
    client: AsyncClient,
    provider: ProviderClient,
    db_session: AsyncSession,
) -> None:
    """Первый submit сохраняет намерение, возвращает 202 и вызывает провайдера"""
    await _create(client, "operation-submit")

    response = await client.post("/operations/operation-submit/submit")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "PROCESSING"
    assert body["providerPaymentId"] == "aa5b7856-e9f2-4fd5-955b-38b1f28d9c57"
    provider.create_payment_with_retries.assert_awaited_once_with(
        operation_id="operation-submit",
        amount="1000.00",
        currency="RUB",
    )

    operation = await db_session.get(Operation, "operation-submit")
    assert operation is not None
    assert operation.submit_intent is True
    assert operation.status == OperationStatus.PROCESSING

    events = (
        await db_session.scalars(
            select(OperationEvent)
            .where(OperationEvent.operation_id == "operation-submit")
            .order_by(OperationEvent.event_id)
        )
    ).all()
    assert [e.type for e in events] == ["CREATED", "PROCESSING"]


@pytest.mark.asyncio
async def test_repeat_submit_returns_200_without_second_provider_call(
    client: AsyncClient,
    provider: ProviderClient,
) -> None:
    """Повторный submit возвращает 200 и не создаёт второе намерение/вызов"""
    await _create(client, "operation-repeat")
    first = await client.post("/operations/operation-repeat/submit")
    assert first.status_code == 202

    second = await client.post("/operations/operation-repeat/submit")

    assert second.status_code == 200
    assert second.json()["status"] == "PROCESSING"
    assert provider.create_payment_with_retries.await_count == 1


@pytest.mark.asyncio
async def test_submit_missing_operation_returns_404(client: AsyncClient) -> None:
    """Submit несуществующей операции возвращает 404"""
    response = await client.post("/operations/missing/submit")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_provider_failure_keeps_processing(
    client: AsyncClient,
    provider: ProviderClient,
    db_session: AsyncSession,
) -> None:
    """Сбой провайдера после ретраев оставляет операцию в PROCESSING"""
    provider.create_payment_with_retries = AsyncMock(side_effect=httpx.ConnectError("network down"))
    await _create(client, "operation-fail")

    response = await client.post("/operations/operation-fail/submit")

    assert response.status_code == 202
    assert response.json()["status"] == "PROCESSING"
    assert response.json()["providerPaymentId"] is None

    operation = await db_session.get(Operation, "operation-fail")
    assert operation is not None
    assert operation.status == OperationStatus.PROCESSING
    assert operation.submit_intent is True


@pytest.mark.asyncio
async def test_create_payment_with_retries_retries_on_503() -> None:
    """create_payment_with_retries повторяет вызов при 503 и затем принимает ответ"""
    http = AsyncMock()
    client = ProviderClient(
        base_url="http://provider",
        http=http,
        max_attempts=3,
        retry_base_delay_seconds=0,
    )
    client.create_payment = AsyncMock(
        side_effect=[
            httpx.HTTPStatusError(
                "unavailable",
                request=MagicMock(),
                response=MagicMock(status_code=503),
            ),
            ProviderPaymentAccepted(provider_payment_id="pid-1", status="ACCEPTED"),
        ]
    )

    result = await client.create_payment_with_retries(
        operation_id="operation-retry",
        amount="1.00",
        currency="RUB",
    )

    assert result.provider_payment_id == "pid-1"
    assert client.create_payment.await_count == 2


@pytest.mark.asyncio
async def test_claim_submit_intent_wins_only_once(db_session: AsyncSession) -> None:
    """Конкурентный claim: ровно один переход от CREATED к PROCESSING"""
    from app.schemas.operations import CreateOperationRequest
    from app.services.operation_service import OperationService

    service = OperationService(db_session)
    await service.create(
        CreateOperationRequest(
            operationId="operation-race",
            amount="10.00",
            currency="RUB",
            description=None,
        )
    )

    assert await service._claim_submit_intent("operation-race") is True
    assert await service._claim_submit_intent("operation-race") is False
