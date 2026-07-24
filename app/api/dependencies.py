"""Общие зависимости FastAPI"""

from typing import cast

from fastapi import Request

from app.core.config import Settings, get_settings
from app.services.provider_service import ProviderClient


def settings_dep() -> Settings:
    """Возвращает настройки приложения для внедрения через Depends"""
    return get_settings()


def provider_client_dep(request: Request) -> ProviderClient:
    """Возвращает HTTP-клиент провайдера из состояния приложения"""
    return cast(ProviderClient, request.app.state.provider_client)
