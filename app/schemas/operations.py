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
    )

    operation_id: str = Field(..., alias="operationId", min_length=1)
    amount: str
    currency: Literal["RUB"] = "RUB"
    description: str | None = None

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
    )

    operation_id: str = Field(..., alias="operationId")
    amount: str
    currency: str
    description: str | None = None
    status: OperationStatus
    provider_payment_id: str | None = Field(None, alias="providerPaymentId")


class OperationEventResponse(BaseModel):
    """Событие перехода статуса операции в истории"""

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
        from_attributes=True,
    )

    event_id: int = Field(..., alias="eventId")
    type: str
    from_status: str | None = Field(None, alias="fromStatus")
    to_status: str | None = Field(None, alias="toStatus")
    message: str
    occurred_at: datetime = Field(..., alias="occurredAt")
