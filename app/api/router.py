"""Агрегирующий API-роутер приложения"""

from fastapi import APIRouter

from app.api.routers import health, operations, receipts

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(operations.router)
api_router.include_router(receipts.router)
