"""Сервис обработки callback-квитанций провайдера"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import OperationNotFound, ProviderPaymentIdConflict
from app.models import Operation, OperationEvent, OperationStatus
from app.repositories import OperationEventRepository, OperationRepository
from app.schemas.receipts import ReceiptRequest

logger = logging.getLogger(__name__)

_FINAL_STATUSES = {OperationStatus.COMPLETED, OperationStatus.REJECTED}


class ReceiptService:
    """Приём и применение callback-квитанций в одной транзакции"""

    def __init__(self, session: AsyncSession) -> None:
        """Сохраняет сессию и репозитории"""
        self._session = session
        self._operations = OperationRepository(session)
        self._events = OperationEventRepository(session)

    async def process(self, receipt: ReceiptRequest) -> None:
        """Обрабатывает квитанцию по правилам ТЗ и фиксирует результат одним commit"""
        operation = await self._operations.get(receipt.operation_id)
        if operation is None:
            raise OperationNotFound(receipt.operation_id)

        if operation.provider_payment_id is not None and operation.provider_payment_id != receipt.provider_payment_id:
            raise ProviderPaymentIdConflict(receipt.operation_id)

        if operation.provider_payment_id is None:
            await self._operations.set_provider_payment_id_if_empty(
                receipt.operation_id,
                receipt.provider_payment_id,
            )
            # перечитываем актуальные поля после flush
            operation = await self._operations.get(receipt.operation_id)
            assert operation is not None

        target_status = OperationStatus(receipt.result)
        current_status = OperationStatus(operation.status)

        if current_status in _FINAL_STATUSES:
            if current_status == target_status:
                logger.info(
                    "Duplicate receipt ignored without new transition | operationId=%s | status=%s",
                    receipt.operation_id,
                    current_status.value,
                )
                await self._session.commit()
                return

            await self._add_ignored_event(operation, receipt, current_status)
            await self._session.commit()
            logger.info(
                "Conflicting late receipt ignored | operationId=%s | current=%s | receipt=%s",
                receipt.operation_id,
                current_status.value,
                receipt.result,
            )
            return

        from_status = current_status.value
        await self._operations.set_status(operation, target_status)
        event_id = await self._events.next_event_id(receipt.operation_id)
        self._events.add(
            OperationEvent(
                operation_id=receipt.operation_id,
                event_id=event_id,
                type=target_status.value,
                from_status=from_status,
                to_status=target_status.value,
                message=receipt.message or f"Payment {target_status.value.lower()}",
                occurred_at=receipt.occurred_at,
            )
        )
        await self._session.commit()
        logger.info(
            "Receipt applied | operationId=%s | providerPaymentId=%s | status=%s",
            receipt.operation_id,
            receipt.provider_payment_id,
            target_status.value,
        )

    async def _add_ignored_event(
        self,
        operation: Operation,
        receipt: ReceiptRequest,
        current_status: OperationStatus,
    ) -> None:
        """Фиксирует проигнорированную позднюю квитанцию без смены статуса"""
        event_id = await self._events.next_event_id(operation.operation_id)
        self._events.add(
            OperationEvent(
                operation_id=operation.operation_id,
                event_id=event_id,
                type="RECEIPT_IGNORED",
                from_status=current_status.value,
                to_status=current_status.value,
                message=receipt.message or "Conflicting receipt ignored",
                occurred_at=receipt.occurred_at,
            )
        )
