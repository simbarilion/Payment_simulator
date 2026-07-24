"""HTTP-middleware приложения"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Пробрасывает или генерирует X-Correlation-ID для запроса и ответа"""

    def __init__(self, app: ASGIApp) -> None:
        """Инициализирует middleware с ASGI-приложением"""
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Устанавливает correlation id в state запроса и заголовок ответа"""
        request_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

        request.state.request_id = request_id

        response = await call_next(request)

        response.headers["X-Correlation-ID"] = request_id

        return response
