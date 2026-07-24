"""ORM-модель платёжной операции"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import OperationStatus

if TYPE_CHECKING:
    from app.models.operation_event import OperationEvent


class Operation(Base):
    """Платёжная операция и намерение отправки провайдеру"""

    __tablename__ = "operations"

    operation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    amount: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="RUB")
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[OperationStatus] = mapped_column(
        String(32),
        nullable=False,
        default=OperationStatus.CREATED,
    )
    provider_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    submit_intent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    events: Mapped[list[OperationEvent]] = relationship(
        "OperationEvent",
        back_populates="operation",
        order_by="OperationEvent.event_id",
        cascade="all, delete-orphan",
    )
