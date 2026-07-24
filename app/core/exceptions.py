"""Исключения уровня приложения"""

from typing import Any

from starlette.status import HTTP_409_CONFLICT


class AppError(Exception):
    """Базовая ошибка приложения, отображаемая в HTTP-ответ"""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        code: str = "app_error",
        details: Any = None,
    ) -> None:
        """Инициализирует ошибку с сообщением, статусом, кодом и деталями"""
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details


class OperationAlreadyExists(AppError):
    """Ошибка повторного создания операции с тем же operationId (HTTP 409)"""

    def __init__(self, operation_id: str) -> None:
        """Формирует конфликт для уже существующей операции"""
        super().__init__(
            message=f"Operation '{operation_id}' already exists",
            status_code=HTTP_409_CONFLICT,
            code="operation_already_exists",
        )
