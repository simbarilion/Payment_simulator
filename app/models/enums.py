"""Перечисления статусов платёжных операций"""

from enum import StrEnum


class OperationStatus(StrEnum):
    """Допустимые статусы операции по контракту ТЗ"""

    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
