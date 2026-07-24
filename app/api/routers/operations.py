"""Роутер создания, чтения и отправки платёжных операций"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import provider_client_dep
from app.db.dependencies import get_session
from app.schemas.operations import CreateOperationRequest, OperationResponse
from app.services.operation_service import OperationService, build_operation_service
from app.services.provider_service import ProviderClient

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


@router.post(
    "/{operation_id}/submit",
    response_model=OperationResponse,
    summary="Отправка операции провайдеру",
    description="Атомарно сохраняет намерение отправки и вызывает провайдера после фиксации",
    responses={
        202: {"description": "Намерение отправки создано, операция в PROCESSING"},
        200: {"description": "Повторный submit: возвращено текущее состояние"},
        404: {"description": "Операция не найдена"},
    },
)
async def submit_operation(
    operation_id: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
    provider: ProviderClient = Depends(provider_client_dep),
) -> OperationResponse:
    """Планирует отправку: 202 при первом submit, 200 при повторе"""
    body, status_code = await build_operation_service(session, provider).submit(operation_id)
    response.status_code = status_code
    return body
