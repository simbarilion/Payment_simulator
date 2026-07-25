"""Схемы callback-квитанций провайдера"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReceiptRequest(BaseModel):
    """Тело callback-квитанции от provider-simulator"""

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "providerPaymentId": "aa5b7856-e9f2-4fd5-955b-38b1f28d9c57",
                    "operationId": "operation-demo-1",
                    "result": "COMPLETED",
                    "message": "Payment completed",
                    "occurredAt": "2026-07-25T16:10:51.420344Z",
                },
                {
                    "providerPaymentId": "aa5b7856-e9f2-4fd5-955b-38b1f28d9c57",
                    "operationId": "operation-demo-1",
                    "result": "REJECTED",
                    "message": "Payment rejected by provider",
                    "occurredAt": "2026-07-25T16:10:51.420344Z",
                },
            ]
        },
    )

    provider_payment_id: str = Field(
        ...,
        alias="providerPaymentId",
        min_length=1,
        description="Идентификатор платежа у провайдера",
        examples=["aa5b7856-e9f2-4fd5-955b-38b1f28d9c57"],
    )
    operation_id: str = Field(
        ...,
        alias="operationId",
        min_length=1,
        description="Идентификатор операции candidate-service",
        examples=["operation-demo-1"],
    )
    result: Literal["COMPLETED", "REJECTED"] = Field(
        ...,
        description="Финальный результат платежа",
        examples=["COMPLETED"],
    )
    message: str = Field(
        default="",
        description="Текстовое пояснение от провайдера",
        examples=["Payment completed"],
    )
    occurred_at: datetime = Field(
        ...,
        alias="occurredAt",
        description="Момент формирования квитанции (ISO 8601)",
        examples=["2026-07-25T16:10:51.420344Z"],
    )
