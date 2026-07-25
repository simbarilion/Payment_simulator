"""Роутер приёма callback-квитанций от провайдера"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_session
from app.schemas.errors import ErrorResponse
from app.schemas.receipts import ReceiptRequest
from app.services.receipt_service import ReceiptService

router = APIRouter(tags=["receipts"])


@router.post(
    "/receipts",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Приём callback-квитанции",
    description=(
        "Принимает квитанцию провайдера и в одной транзакции обновляет операцию. "
        "Повтор с тем же `result` — без второго перехода; поздняя противоположная — "
        "`RECEIPT_IGNORED`; несовпадающий `providerPaymentId` — **409**."
    ),
    responses={
        204: {"description": "Квитанция принята (в том числе повторная или проигнорированная)"},
        404: {"description": "Операция не найдена", "model": ErrorResponse},
        409: {
            "description": "Несовпадающий providerPaymentId",
            "model": ErrorResponse,
        },
        422: {"description": "Ошибка валидации тела квитанции"},
    },
)
async def accept_receipt(
    payload: ReceiptRequest,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Обрабатывает квитанцию и возвращает 204 без тела"""
    await ReceiptService(session).process(payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
