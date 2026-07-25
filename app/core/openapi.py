"""Метаданные OpenAPI / Swagger для candidate-service"""

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Проверка работоспособности сервиса и доступности SQLite.",
    },
    {
        "name": "operations",
        "description": (
            "Жизненный цикл платёжной операции: создание, submit провайдеру, чтение состояния и истории переходов."
        ),
    },
    {
        "name": "receipts",
        "description": (
            "Callback-квитанции от provider-simulator. Только они переводят операцию в COMPLETED или REJECTED."
        ),
    },
]

API_DESCRIPTION = """
Сервис проводит платёжную операцию через внешнего `provider-simulator` и сохраняет
корректное состояние при повторах, конкурентных запросах, потере HTTP-ответа и перезапусках.

**Основные сценарии**
- `POST /operations` — создать операцию (`CREATED`); `operationId` задаёт клиент
- `POST /operations/{operationId}/submit` — сохранить намерение отправки и вызвать провайдера
- `POST /receipts` — принять callback-квитанцию (финальный статус)
- `GET /operations/{operationId}` — текущее состояние
- `GET /operations/{operationId}/events` — история переходов
- `GET /health` — готовность сервиса и БД

**Важные правила**
- Финальный статус — **только** из `/receipts`; ответ провайдера `ACCEPTED` не завершает платёж
- Повторный / параллельный `submit` не создаёт второе намерение и второй платёж
- К провайдеру уходят заголовки `Idempotency-Key` и `X-Correlation-ID` (= `operationId`)
- После рестарта `PROCESSING`-операции продолжаются через recovery

**Ошибки приложения** (`AppError`): JSON вида
`{"error": "<code>", "message": "...", "details": null}`.
"""
