"""Тесты чтения операции GET /operations/{id}"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_operation_returns_200(client: AsyncClient) -> None:
    """GET /operations/{id} возвращает текущее состояние созданной операции"""
    await client.post(
        "/operations",
        json={
            "operationId": "operation-get",
            "amount": "1000.00",
            "currency": "RUB",
            "description": "Оплата заказа",
        },
    )

    response = await client.get("/operations/operation-get")

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
async def test_get_operation_returns_404_when_missing(client: AsyncClient) -> None:
    """GET /operations/{id} для неизвестной операции возвращает 404"""
    response = await client.get("/operations/missing-id")

    assert response.status_code == 404
    assert response.json()["error"] == "operation_not_found"
