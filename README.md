# Payment Simulator

Сервис проводит платёжную операцию через внешний `provider-simulator` и сохраняет корректное состояние при повторах, конкурентных запросах, потерянных HTTP-ответах и перезапусках.

Финальный статус операции (`COMPLETED` / `REJECTED`) определяется **только** callback-квитанцией на `POST /receipts`. Ответ `202 Accepted` от провайдера сохраняет `providerPaymentId` и не завершает платёж.

## Требования

- Docker и Docker Compose
- Для локального запуска без Docker: Python 3.14 и Poetry

## Запуск приложения (Docker Compose)

1. Клонировать репозиторий и перейти в корень проекта:

```bash
git clone https://github.com/simbarilion/Payment_simulator.git
cd Payment_simulator
```

2. Собрать образы и поднять оба сервиса:

```bash
docker compose -f docker-compose.yaml up --build
```

3. Дождаться готовности приложения, в другом терминале вызвать healthcheck:

```bash
curl -s http://localhost:8080/health
```

Ожидается `{"status":"ok"}`.

Сервисы после старта:

| Сервис | URL |
|--------|-----|
| candidate-service | http://localhost:8080 |
| provider-simulator | http://localhost:8081 |
| OpenAPI (candidate) | http://localhost:8080/docs |

### Постоянное хранение данных

Сервис использует SQLite в качестве постоянного хранилища.

В `docker-compose.yaml` каталог `/data` внутри контейнера смонтирован в именованный Docker volume `candidate-data`. Файл базы данных `payments.db` (имя задаётся переменной `SQLITE_FILENAME`) создаётся внутри этого каталога.

Благодаря использованию Docker volume данные сохраняются между перезапусками и пересозданием контейнера. 

В базе данных хранятся операции, история переходов состояний (`OperationEvent`) и связь операции с платежом провайдера (`providerPaymentId`).

Данные сохраняются, пока не будет удалён Docker volume `candidate-data`. Полный сброс БД: 

`docker compose -f docker-compose.yaml down -v` (флаг `-v` удаляет volume `candidate-data`).

Остановка контейнеров без удаления данных:

```bash
docker compose -f docker-compose.yaml down
```

## Сквозной сценарий

Ниже приведён минимальный сценарий ручной проверки сервиса после запуска. 

Он демонстрирует полный жизненный цикл операции: создание, отправку провайдеру, обработку callback-квитанции и просмотр истории событий.

### `operationId`

Сервис не генерирует `operationId`: его передаёт клиент в соответствии с контрактом задания.

В реальных платёжных системах идентификатор обычно создаётся внешней системой (например, сервисом заказов) и используется как ключ идемпотентности.

В примерах ниже используется `operation-demo-1`. При повторном запуске сценария без очистки БД используйте новый идентификатор.

### 1. Создать операцию

```bash
curl -s -X POST http://localhost:8080/operations \
  -H "Content-Type: application/json" \
  -d "{\"operationId\":\"operation-demo-1\",\"amount\":\"1000.00\",\"currency\":\"RUB\",\"description\":\"Оплата заказа\"}"
```

Ожидается **201**, `"status":"CREATED"`, `"providerPaymentId":null`.

Повтор с тем же `operationId` -> **409**.

### 2. Надёжно запланировать отправку

```bash
curl -s -i -X POST http://localhost:8080/operations/operation-demo-1/submit
```

Первый вызов -> **202**, `"status":"PROCESSING"`.  
Повторный -> **200** и то же состояние (второе намерение и второй платёж у провайдера не создаются).

Сервис вызывает:

`POST {PROVIDER_URL}/payments`  
с заголовками `Idempotency-Key` и `X-Correlation-ID` = `operationId`.

### 3. Дождаться callback-квитанции

Симулятор сам шлёт `POST http://candidate-service:8080/receipts` с `result: COMPLETED` или `REJECTED` (в пределах 1–2 секунд).

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

- Все попытки отправки одной операции используют один и тот же `Idempotency-Key` (= `operationId`) и неизменное тело запроса.
- Параллельные / повторные `submit` не создают второе намерение: ровно один переход `CREATED` → `PROCESSING`.
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

## Локальный запуск приложения

В этом режиме `candidate-service` запускается локально через Uvicorn, а `provider-simulator` — в Docker Compose.

1. Клонировать репозиторий и перейти в корневую директорию проекта:

```bash
git clone https://github.com/simbarilion/Payment_simulator.git
cd Payment_simulator
```

2. Запустить `provider-simulator`. Порт `8081` должен быть свободен.

```bash
docker compose -f docker-compose.yaml up provider-simulator
```

3. Создать файл окружения:

```bash
cp .env.example .env
```

По умолчанию используются следующие значения:

- `PROVIDER_URL=http://localhost:8081` — адрес `provider-simulator`;
- `DATA_DIR=data` — каталог для хранения файла SQLite;
- `SQLITE_FILENAME=payments.db` — имя файла базы данных.

4. Установить зависимости и запустить приложение:

```bash
poetry install
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8080
```

5. Проверить доступность сервиса:

```bash
curl -s http://localhost:8080/health
```

6. Запуск тестов (опционально):

```bash
poetry install --with test
poetry run pytest
```

**Примечание**

При локальном запуске callback-квитанции от `provider-simulator` могут быть недоступны, 
поскольку в Docker Compose используется адрес `http://candidate-service:8080/receipts`, который разрешается только внутри Docker-сети.

Для проверки полного сценария (создание операции -> submit -> callback -> финальный статус) 
рекомендуется запускать оба сервиса через Docker Compose.


## Переменные окружения

При локальном запуске настройки загружаются из файла `.env`.

Для запуска через Docker Compose переменные окружения определены непосредственно в `docker-compose.yaml`.

Ниже приведены параметры, используемые сервисом.

| Переменная | Значение в Compose | Назначение                                              |
|------------|--------------------|---------------------------------------------------------|
| `PROVIDER_URL` | `http://provider-simulator:8081` | Адрес внешнего provider-simulator внутри Docker-сети    |
| `DATA_DIR` | `/data` | Каталог постоянного хранения данных                     |
| `SQLITE_FILENAME` | `payments.db` | Имя файла базы данных SQLite                            |
| `APP_HOST` / `APP_PORT` | `0.0.0.0` / `8080` | Хост, на котором слушает FastAPI, порт приложения       |
| `PROVIDER_MAX_ATTEMPTS` | `3` | Максимальное число повторов вызова провайдера           |
| `PROVIDER_RETRY_BASE_DELAY_SECONDS` | `0.2` | Начальная задержка между повторными попытками (backoff) |

В качестве постоянного хранилища используется SQLite. Файл базы данных располагается в Docker volume `candidate-data`, 
благодаря чему данные сохраняются после перезапуска или пересоздания контейнера.

### provider-simulator

| Переменная | Значение | Назначение |
|------------|----------|--------|
| `CALLBACK_URL` | `http://candidate-service:8080/receipts` | Адрес callback-эндпоинта, на который симулятор отправляет результат обработки платежа |

После успешного принятия платежа симулятор выполняет HTTP-запрос на `CALLBACK_URL`, передавая финальный результат (`COMPLETED` или `REJECTED`).
Именно эта квитанция завершает жизненный цикл операции.

## Структура проекта

```text
Payment_simulator/
├── app/
│   ├── api/                 # HTTP-слой: роутеры, Depends, сборка api_router
│   │   └── routers/         # health, operations, receipts
│   ├── core/                # конфиг, исключения, handlers, логи, middleware
│   ├── db/                  # async engine, сессии, init_db
│   ├── models/              # ORM: Operation, OperationEvent, статусы
│   ├── repositories/        # чтение/запись SQLite через SQLAlchemy
│   ├── schemas/             # Pydantic-схемы запросов и ответов API
│   ├── services/            # бизнес-логика: operations, receipts, provider, recovery
│   ├── workers/             # фоновый dispatch вызова провайдера после submit
│   └── main.py              # FastAPI, lifespan, httpx, старт RecoveryService
├── tests/                   # pytest (API, client, receipts, recovery)
├── data/                    # runtime: локальный SQLite (не исходный код, в .gitignore)
├── logs/                    # runtime: логи при запуске (появляются сами, в .gitignore)
├── docker-compose.yaml      # candidate-service + provider-simulator
├── Dockerfile
├── .env.example
├── Makefile
├── pyproject.toml
└── README.md
```

### Ответственность слоёв

- **api / routers** — принимают HTTP-запросы, валидируют вход через схемы, вызывают сервисы; без бизнес-правил и SQL.
- **schemas** — контракт API (Pydantic): create/submit/get, receipts, health.
- **services** — жизненный цикл операции, приём квитанций, идемпотентный `submit`, HTTP-клиент провайдера (`ProviderClient`), `RecoveryService` для незавершённых `PROCESSING`.
- **repositories** — доступ к SQLite: операции, события, атомарный переход статусов `CREATED` в `PROCESSING`.
- **models / db** — ORM-модели и инфраструктура сессий; схема создаётся при старте (`create_all`).
- **workers** — после сохранения намерения `submit` асинхронно вызывает провайдера и сохраняет `providerPaymentId` (не recovery).
- **core** — настройки окружения, доменные ошибки, exception handlers, request-id middleware, логирование.

## Архитектура проекта

```text
Клиент
   │
   ▼
candidate-service
   │
   ├──► SQLite
   │
   ▼
ProviderClient
   │
   ▼
provider-simulator
   │
callback
   │
   ▼
/receipts ──► SQLite
```

Краткий поток:

1. Клиент создаёт операцию (`CREATED`) и вызывает `submit`.
2. Сервис атомарно фиксирует намерение (`PROCESSING`) в SQLite и только потом вызывает провайдера.
3. Провайдер отвечает `ACCEPTED` + `providerPaymentId` (промежуточный этап) и позже шлёт квитанцию на `/receipts`.
4. Только квитанция переводит операцию в `COMPLETED` или `REJECTED`.
5. При старте `RecoveryService` (в `app/services/`) находит незавершённые `PROCESSING` и повторяет вызов с тем же `Idempotency-Key`.

## Архитектурные решения

- **SQLite вместо PostgreSQL** — соответствует условиям ТЗ, проще docker-compose, данные переживают рестарт контейнера.
- **Клиентский `operationId`** — в соответствии с контрактом ТЗ; он же ключ идемпотентности у провайдера.
- **Сначала сохранение в базе, затем HTTP-вызов** — операция переводится в `PROCESSING` до обращения к провайдеру. Благодаря этому после сбоя или перезапуска отправка может быть безопасно продолжена.
- **Разделение транспортного и бизнес-результата** — успешный HTTP-ответ провайдера подтверждает только получение запроса. Операция считается завершённой только после получения callback-квитанции.
- **Защита от повторных отправок** — только один запрос может перевести операцию из `CREATED` в `PROCESSING`. Повторные и конкурентные `submit` используют уже сохранённое состояние.
- **Автоматическое восстановление после перезапуска** — при запуске приложения повторно обрабатываются операции, оставшиеся в состоянии `PROCESSING`.

## Возможные улучшения

- переход на PostgreSQL и миграции Alembic для эксплуатации под высокой нагрузкой;
- добавление метрик и трассировки запросов по `X-Correlation-ID`;
- расширение автоматических тестов сценариями высокой конкуренции и длительных сетевых сбоев.

## Автор

Выполнено в рамках тестового задания.

Надежда Попова  
Python Developer  

Email: nadezhdapopova13@yandex.ru  

Репозиторий: https://github.com/simbarilion/Payment_simulator
