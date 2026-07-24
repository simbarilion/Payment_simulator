"""Сервис жизненного цикла платёжных операций"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import OperationAlreadyExists, OperationNotFound
from app.models import Operation, OperationEvent, OperationStatus
from app.schemas.operations import CreateOperationRequest, OperationResponse


class OperationService:
    """Создание и чтение платёжных операций"""

    def __init__(self, session: AsyncSession) -> None:
        """Сохраняет сессию БД для работы сервиса"""
        self._session = session

    async def create(self, payload: CreateOperationRequest) -> OperationResponse:
        """Создаёт операцию в статусе CREATED и пишет первое событие истории"""
        existing = await self._session.get(Operation, payload.operation_id)
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
        self._session.add(operation)
        self._session.add(event)
        await self._session.commit()
        await self._session.refresh(operation)
        return cast(OperationResponse, OperationResponse.model_validate(operation))

    async def get(self, operation_id: str) -> OperationResponse:
        """Возвращает текущее состояние операции по идентификатору"""
        operation = await self._session.get(Operation, operation_id)
        if operation is None:
            raise OperationNotFound(operation_id)
        return cast(OperationResponse, OperationResponse.model_validate(operation))
