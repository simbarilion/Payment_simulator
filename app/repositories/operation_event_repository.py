"""Репозиторий событий истории операций"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OperationEvent


class OperationEventRepository:
    """SQL/ORM-доступ к таблице operation_events без commit"""

    def __init__(self, session: AsyncSession) -> None:
        """Сохраняет сессию для запросов"""
        self._session = session

    def add(self, event: OperationEvent) -> None:
        """Добавляет событие в текущую сессию"""
        self._session.add(event)

    async def list_by_operation(self, operation_id: str) -> list[OperationEvent]:
        """Возвращает события операции в порядке возрастания event_id"""
        result = await self._session.scalars(
            select(OperationEvent).where(OperationEvent.operation_id == operation_id).order_by(OperationEvent.event_id)
        )
        return list(result.all())

    async def next_event_id(self, operation_id: str) -> int:
        """Возвращает следующий монотонный event_id в пределах операции"""
        current_max = await self._session.scalar(
            select(func.max(OperationEvent.event_id)).where(OperationEvent.operation_id == operation_id)
        )
        return int(current_max or 0) + 1
