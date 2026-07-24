"""Тесты каркаса HTTP-клиента провайдера"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.provider_service import ProviderClient, ProviderPaymentAccepted


def _mock_http(response: MagicMock) -> AsyncMock:
    """Создаёт AsyncClient-заглушку с заданным ответом post"""
    http = AsyncMock()
    http.post = AsyncMock(return_value=response)
    return http


@pytest.mark.asyncio
async def test_create_payment_sends_idempotency_and_correlation_headers() -> None:
    """POST /payments уходит с Idempotency-Key и X-Correlation-ID равными operationId"""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "providerPaymentId": "aa5b7856-e9f2-4fd5-955b-38b1f28d9c57",
        "status": "ACCEPTED",
    }
    http = _mock_http(response)
    client = ProviderClient(base_url="http://provider:8081", http=http)

    result = await client.create_payment(
        operation_id="operation-123",
        amount="1000.00",
        currency="RUB",
    )

    http.post.assert_awaited_once_with(
        "http://provider:8081/payments",
        headers={
            "Idempotency-Key": "operation-123",
            "X-Correlation-ID": "operation-123",
            "Content-Type": "application/json",
        },
        json={
            "operationId": "operation-123",
            "amount": "1000.00",
            "currency": "RUB",
        },
    )
    assert result == ProviderPaymentAccepted(
        provider_payment_id="aa5b7856-e9f2-4fd5-955b-38b1f28d9c57",
        status="ACCEPTED",
    )


@pytest.mark.asyncio
async def test_create_payment_raises_on_http_error() -> None:
    """При ответе 503 клиент пробрасывает HTTPStatusError"""
    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Service Unavailable",
        request=MagicMock(),
        response=MagicMock(status_code=503),
    )
    http = _mock_http(response)
    client = ProviderClient(base_url="http://provider", http=http)

    with pytest.raises(httpx.HTTPStatusError):
        await client.create_payment(
            operation_id="operation-123",
            amount="1000.00",
            currency="RUB",
        )
