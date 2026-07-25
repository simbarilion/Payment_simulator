"""Репозиторий платёжных операций"""

from __future__ import annotations

from typing import cast

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Operation, OperationStatus


class OperationRepository:
    """SQL/ORM-доступ к таблице operations без commit"""

    def __init__(self, session: AsyncSession) -> None:
        """Сохраняет сессию для запросов"""
        self._session = session

    async def get(self, operation_id: str) -> Operation | None:
        """Возвращает операцию по идентификатору или None"""
        return cast(Operation | None, await self._session.get(Operation, operation_id))

    def add(self, operation: Operation) -> None:
        """Добавляет операцию в текущую сессию"""
        self._session.add(operation)

    async def claim_created_to_processing(self, operation_id: str) -> bool:
        """Атомарно переводит CREATED в PROCESSING с флагом намерения; True если строка обновлена"""
        result = await self._session.execute(
            update(Operation)
            .where(
                Operation.operation_id == operation_id,
                Operation.status == OperationStatus.CREATED,
            )
            .values(
                status=OperationStatus.PROCESSING,
                submit_intent=True,
            )
        )
        return cast(bool, result.rowcount == 1)

    async def set_provider_payment_id_if_empty(
        self,
        operation_id: str,
        provider_payment_id: str,
    ) -> bool:
        """Устанавливает providerPaymentId только если он ещё пуст; True если значение записано"""
        operation = await self.get(operation_id)
        if operation is None or operation.provider_payment_id is not None:
            return False
        operation.provider_payment_id = provider_payment_id
        await self._session.flush()
        return True

    async def list_processing(self) -> list[Operation]:
        """Возвращает незавершённые операции в статусе PROCESSING (для recovery)"""
        result = await self._session.scalars(
            select(Operation).where(Operation.status == OperationStatus.PROCESSING).order_by(Operation.created_at)
        )
        return list(result.all())

    async def set_status(self, operation: Operation, status: OperationStatus) -> None:
        """Обновляет статус операции в текущей сессии"""
        operation.status = status
        await self._session.flush()
