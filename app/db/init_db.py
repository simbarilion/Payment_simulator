"""Инициализация схемы постоянного хранилища"""

import logging

from app.db.session import engine
from app.models import Base  # импорт пакета регистрирует ORM-модели в metadata

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Создаёт недостающие таблицы SQLite через metadata.create_all"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema ensured via create_all")
