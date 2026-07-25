"""Схемы запросов и ответов для платёжных операций"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import OperationStatus

_AMOUNT_RE = re.compile(r"^(?:0|[1-9]\d*)(?:\.\d{1,2})?$")


class CreateOperationRequest(BaseModel):
    """Тело запроса на создание операции"""

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "operationId": "operation-demo-1",
                    "amount": "1000.00",
                    "currency": "RUB",
                    "description": "Оплата заказа",
                }
            ]
        },
    )

    operation_id: str = Field(
        ...,
        alias="operationId",
        min_length=1,
        description="Идентификатор операции от клиента (ключ идемпотентности)",
        examples=["operation-demo-1"],
    )
    amount: str = Field(
        ...,
        description="Сумма: положительная десятичная строка, не более 2 знаков после точки",
        examples=["1000.00"],
    )
    currency: Literal["RUB"] = Field(
        default="RUB",
        description="Валюта операции (в контракте задания — только RUB)",
        examples=["RUB"],
    )
    description: str | None = Field(
        default=None,
        description="Произвольное описание платежа",
        examples=["Оплата заказа"],
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: str) -> str:
        """Проверяет, что amount — положительная десятичная строка с не более чем двумя знаками"""
        if not _AMOUNT_RE.fullmatch(value):
            raise ValueError("amount must be a positive decimal string with at most 2 fraction digits")
        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("amount must be a valid decimal") from exc
        if amount <= 0:
            raise ValueError("amount must be greater than zero")
        return value


class OperationResponse(BaseModel):
    """Текущее состояние операции в ответе API"""

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "operationId": "operation-demo-1",
                    "amount": "1000.00",
                    "currency": "RUB",
                    "description": "Оплата заказа",
                    "status": "CREATED",
                    "providerPaymentId": None,
                },
                {
                    "operationId": "operation-demo-1",
                    "amount": "1000.00",
                    "currency": "RUB",
                    "description": "Оплата заказа",
                    "status": "PROCESSING",
                    "providerPaymentId": "aa5b7856-e9f2-4fd5-955b-38b1f28d9c57",
                },
                {
                    "operationId": "operation-demo-1",
                    "amount": "1000.00",
                    "currency": "RUB",
                    "description": "Оплата заказа",
                    "status": "COMPLETED",
                    "providerPaymentId": "aa5b7856-e9f2-4fd5-955b-38b1f28d9c57",
                },
            ]
        },
    )

    operation_id: str = Field(
        ...,
        alias="operationId",
        description="Идентификатор операции",
        examples=["operation-demo-1"],
    )
    amount: str = Field(..., description="Сумма операции", examples=["1000.00"])
    currency: str = Field(..., description="Валюта", examples=["RUB"])
    description: str | None = Field(
        default=None,
        description="Описание",
        examples=["Оплата заказа"],
    )
    status: OperationStatus = Field(
        ...,
        description="Текущий статус операции",
        examples=["CREATED"],
    )
    provider_payment_id: str | None = Field(
        default=None,
        alias="providerPaymentId",
        description="Идентификатор платежа у провайдера (после accept или ранней квитанции)",
        examples=["aa5b7856-e9f2-4fd5-955b-38b1f28d9c57"],
    )


class OperationEventResponse(BaseModel):
    """Событие перехода статуса операции в истории"""

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "eventId": 1,
                    "type": "CREATED",
                    "fromStatus": None,
                    "toStatus": "CREATED",
                    "message": "Operation created",
                    "occurredAt": "2026-07-25T16:10:50.875619",
                },
                {
                    "eventId": 2,
                    "type": "PROCESSING",
                    "fromStatus": "CREATED",
                    "toStatus": "PROCESSING",
                    "message": "Submit intent saved",
                    "occurredAt": "2026-07-25T16:10:50.898539",
                },
                {
                    "eventId": 3,
                    "type": "COMPLETED",
                    "fromStatus": "PROCESSING",
                    "toStatus": "COMPLETED",
                    "message": "Payment completed",
                    "occurredAt": "2026-07-25T16:10:51.420344",
                },
                {
                    "eventId": 4,
                    "type": "RECEIPT_IGNORED",
                    "fromStatus": "COMPLETED",
                    "toStatus": "COMPLETED",
                    "message": "Conflicting receipt ignored",
                    "occurredAt": "2026-07-25T16:11:00.000000",
                },
            ]
        },
    )

    event_id: int = Field(
        ...,
        alias="eventId",
        description="Монотонный номер события в пределах операции",
        examples=[1],
    )
    type: str = Field(
        ...,
        description="Тип события (статус или RECEIPT_IGNORED)",
        examples=["PROCESSING"],
    )
    from_status: str | None = Field(
        default=None,
        alias="fromStatus",
        description="Статус до перехода",
        examples=["CREATED"],
    )
    to_status: str | None = Field(
        default=None,
        alias="toStatus",
        description="Статус после перехода",
        examples=["PROCESSING"],
    )
    message: str = Field(
        ...,
        description="Пояснение к событию",
        examples=["Submit intent saved"],
    )
    occurred_at: datetime = Field(
        ...,
        alias="occurredAt",
        description="Время фиксации события",
        examples=["2026-07-25T16:10:50.898539"],
    )
