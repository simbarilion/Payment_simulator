"""Инициализация схемы постоянного хранилища"""

import logging

from sqlalchemy import Connection

from app.db.session import engine
from app.models import Base  # импорт пакета регистрирует ORM-модели в metadata

logger = logging.getLogger(__name__)


def _create_all(connection: Connection) -> None:
    """Синхронно создаёт таблицы"""
    Base.metadata.create_all(bind=connection)


async def init_db() -> None:
    """Создаёт недостающие таблицы SQLite через metadata.create_all"""
    async with engine.begin() as conn:
        await conn.run_sync(_create_all)
    logger.info("Database schema ensured via create_all")
