"""Тесты recovery незавершённых операций после перезапуска"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Operation, OperationStatus
from app.schemas.operations import CreateOperationRequest
from app.services.operation_service import OperationService
from app.services.provider_service import ProviderClient, ProviderPaymentAccepted
from app.services.recovery_service import RecoveryService


@pytest.mark.asyncio
async def test_recovery_resumes_processing_operations(
    session_factory: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    """Recovery находит PROCESSING и повторяет вызов провайдера с тем же operationId"""
    service = OperationService(db_session)
    await service.create(
        CreateOperationRequest(
            operationId="operation-recovery",
            amount="1000.00",
            currency="RUB",
            description="recovery",
        )
    )
    assert await service._claim_submit_intent("operation-recovery") is True

    operation = await db_session.get(Operation, "operation-recovery")
    assert operation is not None
    assert operation.status == OperationStatus.PROCESSING
    assert operation.provider_payment_id is None

    provider = MagicMock(spec=ProviderClient)
    provider.create_payment_with_retries = AsyncMock(
        return_value=ProviderPaymentAccepted(
            provider_payment_id="pid-recovery",
            status="ACCEPTED",
        )
    )
    recovered = await RecoveryService(session_factory, provider).resume_pending()

    assert recovered == 1
    provider.create_payment_with_retries.assert_awaited_once_with(
        operation_id="operation-recovery",
        amount="1000.00",
        currency="RUB",
    )

    async with session_factory() as session:
        loaded = await session.get(Operation, "operation-recovery")
        assert loaded is not None
        assert loaded.provider_payment_id == "pid-recovery"
        assert loaded.status == OperationStatus.PROCESSING


@pytest.mark.asyncio
async def test_recovery_skips_when_no_processing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Если незавершённых операций нет, recovery ничего не вызывает"""
    provider = MagicMock(spec=ProviderClient)
    provider.create_payment_with_retries = AsyncMock()

    recovered = await RecoveryService(session_factory, provider).resume_pending()

    assert recovered == 0
    provider.create_payment_with_retries.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_stops_on_cancellation(
    session_factory: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    """При отмене задачи recovery прерывается между операциями"""
    service = OperationService(db_session)
    for suffix in ("a", "b"):
        await service.create(
            CreateOperationRequest(
                operationId=f"operation-cancel-{suffix}",
                amount="1.00",
                currency="RUB",
                description=None,
            )
        )
        await service._claim_submit_intent(f"operation-cancel-{suffix}")

    provider = MagicMock(spec=ProviderClient)
    started = asyncio.Event()

    async def slow_create_payment(**kwargs):
        started.set()
        await asyncio.sleep(60)
        return ProviderPaymentAccepted(provider_payment_id="x", status="ACCEPTED")

    provider.create_payment_with_retries = AsyncMock(side_effect=slow_create_payment)
    recovery = RecoveryService(session_factory, provider)
    task = asyncio.create_task(recovery.resume_pending())

    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
