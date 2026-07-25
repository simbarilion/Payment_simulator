"""Тесты истории операций GET /operations/{id}/events"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_events_after_create(
    client: AsyncClient,
    create_operation: Callable[..., Awaitable[None]],
) -> None:
    """После create история содержит одно событие CREATED с eventId=1"""
    await create_operation("operation-events")

    response = await client.get("/operations/operation-events/events")

    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["eventId"] == 1
    assert events[0]["type"] == "CREATED"
    assert events[0]["fromStatus"] is None
    assert events[0]["toStatus"] == "CREATED"
    assert events[0]["message"] == "Operation created"
    assert "occurredAt" in events[0]


@pytest.mark.asyncio
async def test_list_events_after_create_and_submit(
    client: AsyncClient,
    create_operation: Callable[..., Awaitable[None]],
) -> None:
    """После create и submit eventId монотонно растёт: CREATED затем PROCESSING"""
    await create_operation("operation-events-submit", amount="10.00", description=None)
    await client.post("/operations/operation-events-submit/submit")

    response = await client.get("/operations/operation-events-submit/events")

    assert response.status_code == 200
    events = response.json()
    assert [e["eventId"] for e in events] == [1, 2]
    assert [e["type"] for e in events] == ["CREATED", "PROCESSING"]
    assert events[1]["fromStatus"] == "CREATED"
    assert events[1]["toStatus"] == "PROCESSING"


@pytest.mark.asyncio
async def test_list_events_missing_operation_returns_404(client: AsyncClient) -> None:
    """История несуществующей операции возвращает 404"""
    response = await client.get("/operations/missing/events")
    assert response.status_code == 404
    assert response.json()["error"] == "operation_not_found"
