# Payment Simulator

Сервис проводит платёжную операцию через внешний `provider-simulator` и сохраняет корректное состояние при повторах, конкурентных запросах, потерянных HTTP-ответах и перезапусках.

Финальный статус операции (`COMPLETED` / `REJECTED`) определяется **только** callback-квитанцией на `POST /receipts`. Ответ `202 Accepted` от провайдера лишь сохраняет `providerPaymentId` и не завершает платёж.

## Требования

- Docker и Docker Compose
- Для локального запуска без Docker: Python 3.14 и Poetry

## Запуск приложения (Docker Compose)

Из корня репозитория:

```bash
docker compose up --build
```

Сервисы:

| Сервис | URL |
|--------|-----|
| candidate-service | http://localhost:8080 |
| provider-simulator | http://localhost:8081 |
| OpenAPI (candidate) | http://localhost:8080/docs |

Данные SQLite хранятся в volume `candidate-data` → `/data/payments.db` и переживают recreate контейнера (пока volume не удалён).

Остановка:

```bash
docker compose down
```

Удаление volume (сброс данных):

```bash
docker compose down -v
```

## Проверка готовности

```bash
curl -s http://localhost:8080/health
```

Ожидается `{"status":"ok"}`.

## Сквозной сценарий

Подставьте уникальный `operationId` при каждом прогоне.

### 1. Создать операцию

```bash
curl -s -X POST http://localhost:8080/operations \
  -H "Content-Type: application/json" \
  -d "{\"operationId\":\"operation-demo-1\",\"amount\":\"1000.00\",\"currency\":\"RUB\",\"description\":\"Оплата заказа\"}"
```

Ожидается **201**, `"status":"CREATED"`, `"providerPaymentId":null`.

Повтор с тем же `operationId` вызывает исключение со статусом **409**.

### 2. Надёжно запланировать отправку

```bash
curl -s -i -X POST http://localhost:8080/operations/operation-demo-1/submit
```

Первый вызов возвращает **202**, `"status":"PROCESSING"`.  
Повторный вызов возвращает **200** и то же состояние (второе намерение и второй платёж у провайдера не создаются).

Сервис вызывает:

`POST {PROVIDER_URL}/payments`  
с заголовками `Idempotency-Key` и `X-Correlation-ID` = `operationId`.

### 3. Дождаться callback-квитанции

Симулятор сам шлёт `POST http://candidate-service:8080/receipts` с `result: COMPLETED` или `REJECTED`.

Проверить состояние:

```bash
curl -s http://localhost:8080/operations/operation-demo-1
```

После квитанции статус станет `COMPLETED` или `REJECTED`, появится `providerPaymentId`.

### 4. История переходов

```bash
curl -s http://localhost:8080/operations/operation-demo-1/events
```

Ожидается монотонный `eventId`: `CREATED` -> `PROCESSING` -> `COMPLETED`|`REJECTED`.

## Идемпотентность и один платёж на операцию

- Все повторы одной операции используют **один и тот же** `Idempotency-Key` (равен `operationId`) и неизменное тело платежа.
- Параллельные / повторные `submit` не создают второе намерение: ровно один переход от `CREATED` к `PROCESSING`.
- После сетевой ошибки или потери ответа операция остаётся `PROCESSING`; recovery при старте снова вызывает провайдера с тем же ключом.
- Провайдер при том же ключе возвращает тот же `providerPaymentId` и не создаёт новый платёж.
- Автопроверка сверяет внутренний аудит провайдера: на одну операцию — не более одного платежа.

## Обязательный API

| Метод | Маршрут | Успех |
|-------|---------|-------|
| GET | `/health` | 200 |
| POST | `/operations` | 201 |
| POST | `/operations/{id}/submit` | 202 или 200 |
| POST | `/receipts` | 204 |
| GET | `/operations/{id}` | 200 |
| GET | `/operations/{id}/events` | 200 |

## Локальный запуск (без Docker)

```bash
cp .env.example .env
poetry install
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Нужен доступный `PROVIDER_URL` (по умолчанию `http://localhost:8081`). Симулятор удобнее поднимать через Compose.

Тесты:

```bash
poetry install --with test
poetry run pytest
```

## Переменные окружения

Создай `.env` по примеру `.env.example`. 

В docker-compose.yaml для candidate задаются как минимум:

- `PROVIDER_URL=http://provider-simulator:8081`
- `DATA_DIR=/data`

У симулятора: `CALLBACK_URL=http://candidate-service:8080/receipts`.
