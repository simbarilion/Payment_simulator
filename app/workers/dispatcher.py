"""Фоновый диспетчер отправки платежей провайдеру"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.provider_service import ProviderClient

logger = logging.getLogger(__name__)


class PaymentDispatcher:
    """Отправляет платёж провайдеру после фиксации намерения и сохраняет providerPaymentId"""

    def __init__(self, provider: ProviderClient) -> None:
        """Сохраняет клиент провайдера"""
        self._provider = provider

    async def dispatch(
        self,
        session: AsyncSession,
        operation_id: str,
        amount: str,
        currency: str,
    ) -> None:
        """Вызывает провайдера без удержания блокировки операции; при ошибке оставляет PROCESSING"""
        try:
            accepted = await self._provider.create_payment_with_retries(
                operation_id=operation_id,
                amount=amount,
                currency=currency,
            )
        except Exception:
            logger.exception(
                "Provider call failed after retries; operation stays PROCESSING | operationId=%s",
                operation_id,
            )
            return

        # Импорт внутри метода разрывает цикл operation_service - dispatcher
        from app.services.operation_service import OperationService

        await OperationService(session).apply_provider_accepted(
            operation_id,
            accepted.provider_payment_id,
        )
