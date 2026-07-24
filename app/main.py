"""Точка входа FastAPI-приложения"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestIdMiddleware
from app.db.session import engine

logger = logging.getLogger(__name__)
settings = get_settings()
setup_logging(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application started")
    yield
    await engine.dispose()  # закрывает пулл соединений с PostgreSQL при завершении работы приложения


app = FastAPI(
    title="Payment Service API",
    description="",
    version="1.0.0",
    openapi_tags=[],
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
