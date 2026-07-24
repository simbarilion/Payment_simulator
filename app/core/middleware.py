"""HTTP-middleware приложения"""

from __future__ import annotations

import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:

        request_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

        request.state.request_id = request_id

        response = await call_next(request)

        response.headers["X-Correlation-ID"] = request_id

        return response
