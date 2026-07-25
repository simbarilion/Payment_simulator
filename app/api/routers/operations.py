"""Роутер создания, чтения и отправки платёжных операций"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import provider_client_dep
from app.db.dependencies import get_session
from app.schemas.errors import ErrorResponse
from app.schemas.operations import CreateOperationRequest, OperationEventResponse, OperationResponse
from app.services.operation_service import OperationService, build_operation_service
from app.services.provider_service import ProviderClient

router = APIRouter(prefix="/operations", tags=["operations"])


@router.post(
    "",
    response_model=OperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создание операции",
    description=(
        "Создаёт платёжную операцию в статусе `CREATED`. "
        "`operationId` задаёт клиент и далее используется как Idempotency-Key у провайдера."
    ),
    responses={
        201: {"description": "Операция создана", "model": OperationResponse},
        409: {
            "description": "Операция с таким operationId уже существует",
            "model": ErrorResponse,
        },
        422: {"description": "Ошибка валидации тела запроса"},
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
    description="Возвращает текущее состояние платёжной операции по `operationId`.",
    responses={
        200: {"description": "Текущее состояние операции", "model": OperationResponse},
        404: {"description": "Операция не найдена", "model": ErrorResponse},
    },
)
async def get_operation(
    operation_id: str,
    session: AsyncSession = Depends(get_session),
) -> OperationResponse:
    """Возвращает операцию по id или 404, если она не существует"""
    return await OperationService(session).get(operation_id)


@router.get(
    "/{operation_id}/events",
    response_model=list[OperationEventResponse],
    summary="История переходов операции",
    description=(
        "Возвращает события операции в порядке фиксации "
        "(`CREATED` → `PROCESSING` → `COMPLETED`|`REJECTED`, при конфликте — `RECEIPT_IGNORED`)."
    ),
    responses={
        200: {"description": "История переходов"},
        404: {"description": "Операция не найдена", "model": ErrorResponse},
    },
)
async def list_operation_events(
    operation_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[OperationEventResponse]:
    """Возвращает историю событий операции или 404, если операции нет"""
    return await OperationService(session).list_events(operation_id)


@router.post(
    "/{operation_id}/submit",
    response_model=OperationResponse,
    summary="Отправка операции провайдеру",
    description=(
        "Атомарно сохраняет намерение отправки (`CREATED` → `PROCESSING`), затем вызывает "
        "`POST {PROVIDER_URL}/payments` с `Idempotency-Key` и `X-Correlation-ID`. "
        "Первый вызов — **202**, повторный — **200** без второго платежа. "
        "Финальный статус приходит только через `/receipts`."
    ),
    responses={
        202: {
            "description": "Намерение отправки создано, операция в PROCESSING",
            "model": OperationResponse,
        },
        200: {
            "description": "Повторный submit: возвращено текущее состояние",
            "model": OperationResponse,
        },
        404: {"description": "Операция не найдена", "model": ErrorResponse},
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
