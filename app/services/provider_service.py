"""HTTP-клиент вызовов внешнего provider-simulator"""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True, slots=True)
class ProviderPaymentAccepted:
    """Успешный транспортный ответ провайдера (не финальный статус операции)"""

    provider_payment_id: str
    status: str


class ProviderClient:
    """Асинхронный клиент POST {PROVIDER_URL}/payments с идемпотентными заголовками"""

    def __init__(self, base_url: str, http: httpx.AsyncClient) -> None:
        """Сохраняет базовый URL провайдера и переиспользуемый httpx-клиент"""
        self._base_url = base_url.rstrip("/")
        self._http = http

    async def create_payment(
        self,
        *,
        operation_id: str,
        amount: str,
        currency: str,
    ) -> ProviderPaymentAccepted:
        """Создаёт платёж у провайдера с неизменным телом и Idempotency-Key=operationId"""
        response = await self._http.post(
            f"{self._base_url}/payments",
            headers={
                "Idempotency-Key": operation_id,
                "X-Correlation-ID": operation_id,
                "Content-Type": "application/json",
            },
            json={
                "operationId": operation_id,
                "amount": amount,
                "currency": currency,
            },
        )
        response.raise_for_status()
        payload = response.json()
        return ProviderPaymentAccepted(
            provider_payment_id=payload["providerPaymentId"],
            status=payload["status"],
        )
