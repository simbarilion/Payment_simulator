"""Настройки приложения из переменных окружения и файла .env"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Корневая директория репозитория
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из переменных окружения"""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Payment_simulator"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8080)

    # Logs
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_file: str = "app.log"
    request_log_file: str = "requests.log"

    # SQLite: в Docker Compose каталог монтируется как /data
    data_dir: str = Field(
        default="data",
        description="Каталог постоянного хранилища SQLite",
    )
    sqlite_filename: str = Field(
        default="payments.db",
        description="Имя файла базы SQLite внутри data_dir",
    )

    provider_url: str = Field(
        default="http://localhost:8081",
        description="Базовый URL внешнего provider-simulator",
    )

    @property
    def sqlite_path(self) -> Path:
        """Абсолютный путь к файлу базы SQLite"""
        path = Path(self.data_dir)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        return (path / self.sqlite_filename).resolve()

    @property
    def database_url(self) -> str:
        """Асинхронный URL для SQLAlchemy + aiosqlite"""
        return f"sqlite+aiosqlite:///{self.sqlite_path.as_posix()}"


@lru_cache
def get_settings() -> Settings:
    """Возвращает закэшированный экземпляр настроек"""
    return Settings()


def clear_settings_cache() -> None:
    """Сбрасывает кэш настроек"""
    get_settings.cache_clear()
