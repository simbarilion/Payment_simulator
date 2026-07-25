"""Сервис восстановления незавершённых операций после перезапуска"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories import OperationRepository
from app.services.provider_service import ProviderClient
from app.workers.dispatcher import PaymentDispatcher

logger = logging.getLogger(__name__)


class RecoveryService:
    """Продолжает отправку операций в PROCESSING с прежним Idempotency-Key"""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: ProviderClient,
    ) -> None:
        """Сохраняет фабрику сессий и диспетчер провайдера"""
        self._session_factory = session_factory
        self._dispatcher = PaymentDispatcher(provider)

    async def resume_pending(self) -> int:
        """Находит PROCESSING и повторно вызывает провайдера; возвращает число обработанных операций"""
        async with self._session_factory() as session:
            pending = await OperationRepository(session).list_processing()
            jobs = [(op.operation_id, op.amount, op.currency) for op in pending]

        if not jobs:
            logger.info("Recovery: no PROCESSING operations")
            return 0

        logger.info("Recovery: found %s PROCESSING operation(s)", len(jobs))
        recovered = 0
        for operation_id, amount, currency in jobs:
            task = asyncio.current_task()
            if task is not None and task.cancelled():
                logger.info("Recovery interrupted by shutdown | recovered=%s", recovered)
                raise asyncio.CancelledError

            logger.info(
                "Recovery: dispatching | operationId=%s",
                operation_id,
            )
            async with self._session_factory() as session:
                await self._dispatcher.dispatch(
                    session,
                    operation_id=operation_id,
                    amount=amount,
                    currency=currency,
                )
            recovered += 1

        logger.info("Recovery finished | recovered=%s", recovered)
        return recovered


def start_recovery_task(
    session_factory: async_sessionmaker[AsyncSession],
    provider: ProviderClient,
) -> asyncio.Task[int]:
    """Запускает recovery в фоне и возвращает задачу для graceful shutdown"""
    service = RecoveryService(session_factory=session_factory, provider=provider)
    return asyncio.create_task(service.resume_pending(), name="recovery-pending-operations")
