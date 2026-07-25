"""Общие схемы ответов API (ошибки и служебные)"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Единый формат доменной ошибки приложения (AppError)"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "error": "operation_already_exists",
                    "message": "Operation 'operation-demo-1' already exists",
                    "details": None,
                },
                {
                    "error": "operation_not_found",
                    "message": "Operation 'operation-demo-1' not found",
                    "details": None,
                },
                {
                    "error": "provider_payment_id_conflict",
                    "message": "providerPaymentId does not match operation 'operation-demo-1'",
                    "details": None,
                },
            ]
        }
    )

    error: str = Field(
        ...,
        description="Машинный код ошибки",
        examples=["operation_already_exists"],
    )
    message: str = Field(
        ...,
        description="Человекочитаемое описание",
        examples=["Operation 'operation-demo-1' already exists"],
    )
    details: Any = Field(
        default=None,
        description="Дополнительные данные об ошибке (если есть)",
    )
