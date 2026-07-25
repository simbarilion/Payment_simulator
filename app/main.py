"""Точка входа FastAPI-приложения платёжного сервиса"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestIdMiddleware
from app.core.openapi import API_DESCRIPTION, OPENAPI_TAGS
from app.db.init_db import init_db
from app.db.session import AsyncSessionLocal, engine
from app.services.provider_service import ProviderClient
from app.services.recovery_service import start_recovery_task

logger = logging.getLogger(__name__)
settings = get_settings()
setup_logging(settings)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Управляет жизненным циклом: схема, провайдер, recovery и корректная остановка"""
    await init_db()

    http = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))
    provider_client = ProviderClient(
        base_url=settings.provider_url,
        http=http,
        max_attempts=settings.provider_max_attempts,
        retry_base_delay_seconds=settings.provider_retry_base_delay_seconds,
    )
    app.state.http_client = http
    app.state.provider_client = provider_client

    recovery_task = start_recovery_task(AsyncSessionLocal, provider_client)
    app.state.recovery_task = recovery_task

    logger.info(
        "Application started | data_dir=%s | sqlite=%s | provider_url=%s",
        settings.data_dir,
        settings.sqlite_path,
        settings.provider_url,
    )
    try:
        yield
    finally:
        if not recovery_task.done():
            recovery_task.cancel()
        try:
            await recovery_task
        except asyncio.CancelledError:
            logger.info("Recovery task cancelled on shutdown")
        except Exception:
            logger.exception("Recovery task failed")

        await http.aclose()
        await engine.dispose()
        logger.info("Application stopped")


app = FastAPI(
    title="Payment Simulator API",
    description=API_DESCRIPTION,
    version="1.0.0",
    openapi_tags=OPENAPI_TAGS,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "Popova Nadezhda",
        "email": "nadezhdapopova13@yandex.ru",
    },
    lifespan=lifespan,
)

app.add_middleware(RequestIdMiddleware)

register_exception_handlers(app)

app.include_router(api_router)
