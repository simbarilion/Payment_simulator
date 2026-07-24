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

    # Database
    db_name: str
    db_user: str
    db_password: str
    db_host: str
    db_port: int = 5432

    provider_url: str

    @property
    def database_url(self) -> str:
        """Асинхронный URL для SQLAlchemy + asyncpg"""
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


@lru_cache  # чтобы настройки не создавались при каждом импорте
def get_settings() -> Settings:
    """Возвращает закэшированный экземпляр настроек"""
    return Settings()


def clear_settings_cache() -> None:
    """Сбрасывает кэш настроек"""
    get_settings.cache_clear()
