"""Тесты эндпоинта GET /health"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_200_when_sqlite_available() -> None:
    """GET /health возвращает 200 и status=ok при доступной БД"""
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
