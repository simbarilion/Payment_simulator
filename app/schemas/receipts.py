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
    )

    provider_payment_id: str = Field(..., alias="providerPaymentId", min_length=1)
    operation_id: str = Field(..., alias="operationId", min_length=1)
    result: Literal["COMPLETED", "REJECTED"]
    message: str = ""
    occurred_at: datetime = Field(..., alias="occurredAt")
