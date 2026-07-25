"""Тесты чтения операции GET /operations/{id}"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_operation_returns_200(client_test_db: AsyncClient) -> None:
    """GET /operations/{id} возвращает текущее состояние созданной операции"""
    await client_test_db.post(
        "/operations",
        json={
            "operationId": "operation-get",
            "amount": "1000.00",
            "currency": "RUB",
            "description": "Оплата заказа",
        },
    )

    response = await client_test_db.get("/operations/operation-get")

    assert response.status_code == 200
    assert response.json() == {
        "operationId": "operation-get",
        "amount": "1000.00",
        "currency": "RUB",
        "description": "Оплата заказа",
        "status": "CREATED",
        "providerPaymentId": None,
    }


@pytest.mark.asyncio
async def test_get_operation_returns_404_when_missing(client_test_db: AsyncClient) -> None:
    """GET /operations/{id} для неизвестной операции возвращает 404"""
    response = await client_test_db.get("/operations/missing-id")

    assert response.status_code == 404
    assert response.json()["error"] == "operation_not_found"
