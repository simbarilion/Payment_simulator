"""Эндпоинты проверки состояния сервиса"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_session
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Проверка работоспособности",
    description="Liveness-проверка: сервис запущен и отвечает.",
    responses={200: {"description": "Сервис доступен"}},
)
async def health(
    session: AsyncSession = Depends(get_session),
) -> HealthResponse:
    """Возвращает статус работоспособности сервиса"""
    try:
        await session.execute(text("SELECT 1"))
        return HealthResponse(status="ok")
    except Exception as ex:
        raise HTTPException(status_code=503, detail="Database unavailable") from ex
