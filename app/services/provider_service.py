"""HTTP-клиент вызовов внешнего provider-simulator"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProviderPaymentAccepted:
    """Успешный промежуточный транспортный ответ провайдера"""

    provider_payment_id: str
    status: str


class ProviderClient:
    """Асинхронный клиент POST {PROVIDER_URL}/payments с идемпотентными заголовками"""

    def __init__(
        self,
        base_url: str,
        http: httpx.AsyncClient,
        max_attempts: int = 3,
        retry_base_delay_seconds: float = 0.2,
    ) -> None:
        """Сохраняет базовый URL провайдера, httpx-клиент и параметры повторов"""
        self._base_url = base_url.rstrip("/")
        self._http = http
        self._max_attempts = max_attempts
        self._retry_base_delay_seconds = retry_base_delay_seconds

    async def create_payment(
        self,
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

    async def create_payment_with_retries(
        self,
        operation_id: str,
        amount: str,
        currency: str,
    ) -> ProviderPaymentAccepted:
        """Повторяет create_payment при 503 и сетевых ошибках с ограниченным backoff"""
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                result = await self.create_payment(
                    operation_id=operation_id,
                    amount=amount,
                    currency=currency,
                )
                logger.info(
                    "Provider accepted payment | operationId=%s | providerPaymentId=%s | attempt=%s",
                    operation_id,
                    result.provider_payment_id,
                    attempt,
                )
                return result
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code != 503 or attempt >= self._max_attempts:
                    raise
                logger.warning(
                    "Provider returned 503, retrying | operationId=%s | attempt=%s",
                    operation_id,
                    attempt,
                )
            except httpx.TransportError as exc:
                last_error = exc
                if attempt >= self._max_attempts:
                    raise
                logger.warning(
                    "Provider transport error, retrying | operationId=%s | attempt=%s | error=%s",
                    operation_id,
                    attempt,
                    exc,
                )

            delay = self._retry_base_delay_seconds * (2 ** (attempt - 1))
            delay += random.uniform(0, delay * 0.1) if delay > 0 else 0
            await asyncio.sleep(delay)

        assert last_error is not None
        raise last_error
