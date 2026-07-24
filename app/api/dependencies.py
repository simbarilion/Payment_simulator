"""Общие зависимости FastAPI"""

from app.core.config import Settings, get_settings


def settings_dep() -> Settings:
    """Возвращает настройки приложения для внедрения через Depends"""
    return get_settings()
