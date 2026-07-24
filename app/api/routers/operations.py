"""Роутер создания и чтения платёжных операций"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_session
from app.schemas.operations import CreateOperationRequest, OperationResponse
from app.services.operation_service import OperationService

router = APIRouter(prefix="/operations", tags=["operations"])


@router.post(
    "",
    response_model=OperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создание операции",
    description="Создаёт платёжную операцию в статусе CREATED",
    responses={
        201: {"description": "Операция создана"},
        409: {"description": "Операция с таким operationId уже существует"},
    },
)
async def create_operation(
    payload: CreateOperationRequest,
    session: AsyncSession = Depends(get_session),
) -> OperationResponse:
    """Создаёт новую операцию или возвращает конфликт при дубликате operationId"""
    return await OperationService(session).create(payload)


@router.get(
    "/{operation_id}",
    response_model=OperationResponse,
    summary="Получение операции",
    description="Возвращает текущее состояние платёжной операции",
    responses={
        200: {"description": "Текущее состояние операции"},
        404: {"description": "Операция не найдена"},
    },
)
async def get_operation(
    operation_id: str,
    session: AsyncSession = Depends(get_session),
) -> OperationResponse:
    """Возвращает операцию по id или 404, если она не существует"""
    return await OperationService(session).get(operation_id)
