"""Сервис жизненного цикла платёжных операций"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import OperationAlreadyExists, OperationNotFound
from app.models import Operation, OperationEvent, OperationStatus
from app.repositories import OperationEventRepository, OperationRepository
from app.schemas.operations import CreateOperationRequest, OperationEventResponse, OperationResponse
from app.services.provider_service import ProviderClient
from app.workers.dispatcher import PaymentDispatcher

logger = logging.getLogger(__name__)


class OperationService:
    """Создание, чтение и submit платёжных операций"""

    def __init__(
        self,
        session: AsyncSession,
        dispatcher: PaymentDispatcher | None = None,
    ) -> None:
        """Сохраняет сессию, репозитории и опциональный диспетчер отправки провайдеру"""
        self._session = session
        self._operations = OperationRepository(session)
        self._events = OperationEventRepository(session)
        self._dispatcher = dispatcher

    async def create(self, payload: CreateOperationRequest) -> OperationResponse:
        """Создаёт операцию в статусе CREATED и пишет первое событие истории"""
        existing = await self._operations.get(payload.operation_id)
        if existing is not None:
            raise OperationAlreadyExists(payload.operation_id)

        operation = Operation(
            operation_id=payload.operation_id,
            amount=payload.amount,
            currency=payload.currency,
            description=payload.description,
            status=OperationStatus.CREATED,
            provider_payment_id=None,
            submit_intent=False,
        )
        event = OperationEvent(
            operation_id=payload.operation_id,
            event_id=1,
            type="CREATED",
            from_status=None,
            to_status=OperationStatus.CREATED.value,
            message="Operation created",
            occurred_at=datetime.now(UTC),
        )
        self._operations.add(operation)
        self._events.add(event)
        await self._session.commit()
        await self._session.refresh(operation)
        return cast(OperationResponse, OperationResponse.model_validate(operation))

    async def get(self, operation_id: str) -> OperationResponse:
        """Возвращает текущее состояние операции по идентификатору"""
        operation = await self._operations.get(operation_id)
        if operation is None:
            raise OperationNotFound(operation_id)
        return cast(OperationResponse, OperationResponse.model_validate(operation))

    async def list_events(self, operation_id: str) -> list[OperationEventResponse]:
        """Возвращает историю переходов операции в порядке фиксации"""
        operation = await self._operations.get(operation_id)
        if operation is None:
            raise OperationNotFound(operation_id)

        events = await self._events.list_by_operation(operation_id)
        return [OperationEventResponse.model_validate(event) for event in events]

    async def submit(self, operation_id: str) -> tuple[OperationResponse, int]:
        """Надёжно планирует отправку: 202 при новом намерении, 200 при повторе"""
        operation = await self._operations.get(operation_id)
        if operation is None:
            raise OperationNotFound(operation_id)

        claimed = await self._claim_submit_intent(operation_id)
        if not claimed:
            return await self.get(operation_id), 200

        if self._dispatcher is not None:
            # Вызов провайдера после commit: write-lock снят
            await self._dispatcher.dispatch(
                self._session,
                operation_id=operation.operation_id,
                amount=operation.amount,
                currency=operation.currency,
            )

        return await self.get(operation_id), 202

    async def apply_provider_accepted(self, operation_id: str, provider_payment_id: str) -> None:
        """Сохраняет providerPaymentId без перевода в финальный статус и без отката финала"""
        operation = await self._operations.get(operation_id)
        if operation is None:
            return

        if operation.provider_payment_id is not None:
            logger.info(
                "Skip providerPaymentId update; already set | operationId=%s | existing=%s | incoming=%s",
                operation_id,
                operation.provider_payment_id,
                provider_payment_id,
            )
            return

        updated = await self._operations.set_provider_payment_id_if_empty(
            operation_id,
            provider_payment_id,
        )
        if not updated:
            return

        await self._session.commit()
        logger.info(
            "Saved providerPaymentId | operationId=%s | providerPaymentId=%s | status=%s",
            operation_id,
            provider_payment_id,
            operation.status,
        )

    async def _claim_submit_intent(self, operation_id: str) -> bool:
        """Атомарно переводит CREATED в PROCESSING и фиксирует намерение отправки"""
        claimed = await self._operations.claim_created_to_processing(operation_id)
        if not claimed:
            await self._session.rollback()
            return False

        event_id = await self._events.next_event_id(operation_id)
        self._events.add(
            OperationEvent(
                operation_id=operation_id,
                event_id=event_id,
                type="PROCESSING",
                from_status=OperationStatus.CREATED.value,
                to_status=OperationStatus.PROCESSING.value,
                message="Submit intent saved",
                occurred_at=datetime.now(UTC),
            )
        )
        await self._session.commit()
        return True


def build_operation_service(session: AsyncSession, provider: ProviderClient) -> OperationService:
    """Собирает сервис операций с диспетчером отправки провайдеру"""
    return OperationService(session, dispatcher=PaymentDispatcher(provider))
