"""Схемы ответов health-эндпоинта"""

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Ответ проверки состояния сервиса"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "ok",
                }
            ]
        }
    )
    status: str = Field(..., description="Статус сервиса", examples=["ok"])
