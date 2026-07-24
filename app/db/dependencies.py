"""Зависимости слоя базы данных"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Проброс асинхронной сессии БД для FastAPI Depends"""
    async for session in get_db_session():
        yield session
