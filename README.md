# Wallet API

Внутренний микросервис для управления балансами пользователей.  
Позволяет создавать кошельки, пополнять их и переводить средства между ними.

---

## Быстрый старт

```bash
# 1. Склонируйте репозиторий
git clone <repo-url>
cd wallet-api

# 2. Запуск (БД + применение миграций + API)
docker-compose up -d

# API доступен на: http://localhost:8000
# Swagger UI:      http://localhost:8000/docs
```

Всё происходит автоматически: `entrypoint.sh` дожидается PostgreSQL, применяет `alembic upgrade head` и стартует uvicorn.

---

## API

| Метод | URL | Описание |
|---|---|---|
| `POST` | `/api/v1/wallets` | Создать кошелёк |
| `GET` | `/api/v1/wallets/{id}` | Баланс + история операций |
| `POST` | `/api/v1/wallets/{id}/deposit` | Пополнить кошелёк |
| `POST` | `/api/v1/wallets/transfer` | Перевод между кошельками |
| `GET` | `/health` | Liveness probe |

### Примеры

```bash
# Создать кошелёк
curl -X POST http://localhost:8000/api/v1/wallets
# {"wallet_id": "...", "balance": "0"}

# Пополнить
curl -X POST http://localhost:8000/api/v1/wallets/<id>/deposit \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"amount": "100.00"}'

# Перевод
curl -X POST http://localhost:8000/api/v1/wallets/transfer \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"from_wallet_id": "...", "to_wallet_id": "...", "amount": "50.00"}'

# Баланс + история
curl http://localhost:8000/api/v1/wallets/<id>?limit=20
```

---

## Запуск тестов

```bash
# Внутри Docker (рекомендуется — использует уже поднятую БД)
docker-compose run --rm api pytest -v

# Или локально (нужен запущенный PostgreSQL)
pip install -e ".[test]"
DATABASE_URL=postgresql+asyncpg://wallet_user:wallet_pass@localhost:5432/wallet_db \
  pytest -v
```

---

## Архитектурные решения

### 1. Точность: `NUMERIC(20, 8)` + `Decimal`

Деньги нельзя хранить в `float` — [стандартная проблема](https://docs.python.org/3/tutorial/floatingpoint.html) с представлением десятичных чисел в двоичной арифметике.  
Решение: `NUMERIC(20, 8)` в PostgreSQL гарантирует точное хранение; Python `Decimal` — точную арифметику без потерь при сложении/вычитании.

### 2. Идемпотентность: `Idempotency-Key` заголовок

Клиент (например, мобильное приложение) генерирует UUID перед отправкой запроса и передаёт его в заголовке `Idempotency-Key`.

**Алгоритм:**
1. Запрос пришёл → ищем ключ в таблице `idempotency_keys`.
2. Найден → возвращаем закешированный ответ (статус + тело), не выполняя операцию повторно.
3. Не найден → выполняем операцию, сохраняем ответ в `idempotency_keys`.

Дополнительно: уникальный индекс `transactions.idempotency_key` — DB-level защита: даже если два одинаковых запроса пройдут проверку одновременно (race на уровне приложения), второй `INSERT` упадёт с ConstraintError, а не создаст дубль.

### 3. Race conditions: `SELECT ... FOR UPDATE`

При пополнении и переводе используем пессимистичную блокировку строки кошелька:

```sql
SELECT * FROM wallets WHERE id = $1 FOR UPDATE;
```

Это гарантирует: пока транзакция T1 читает и изменяет баланс, T2 блокируется и ждёт. После коммита T1 — T2 видит уже обновлённый баланс и не может "перезаписать" изменения T1. Баланс никогда не уйдёт в минус.

### 4. Deadlock prevention: ordered locking

При переводе A → B блокируем кошельки **в порядке UUID по возрастанию**, независимо от направления перевода.

Пример:
- Запрос 1: перевод `wallet_AA` → `wallet_BB` → блокирует AA, потом BB.
- Запрос 2: перевод `wallet_BB` → `wallet_AA` → тоже сначала блокирует AA (UUID меньше), потом BB.

Оба запроса конкурируют за одну и ту же первую блокировку — один ждёт, дедлока нет.

### 5. Async стек

| Компонент | Выбор | Причина |
|---|---|---|
| Framework | FastAPI | Нативная поддержка async, Pydantic v2, автодокументация |
| ORM | SQLAlchemy 2.x async | Поддержка asyncpg, `with_for_update()`, типизированные модели |
| Driver | asyncpg | Самый быстрый PostgreSQL-драйвер для Python async |
| Migrations | Alembic | Стандарт для SQLAlchemy, поддержка downgrade |
| Validation | Pydantic v2 | Строгая валидация Decimal, UUID; быстрая сериализация |

### 6. Транзакционная атомарность

Каждая операция изменения баланса выполняется внутри явной транзакции (`async with session.begin()`). При любой ошибке транзакция автоматически откатывается — деньги не теряются и не дублируются.

---

## Структура проекта

```
wallet-api/
├── app/
│   ├── main.py               # FastAPI app
│   ├── config.py             # Settings (env vars)
│   ├── database.py           # Async engine + Base
│   ├── exceptions.py         # HTTP exceptions
│   ├── models/               # SQLAlchemy ORM models
│   ├── schemas/              # Pydantic schemas
│   ├── api/v1/wallets.py     # Endpoints
│   └── services/
│       └── wallet_service.py # Business logic (locking, transfers)
├── migrations/               # Alembic migrations
├── tests/
│   ├── conftest.py           # Fixtures, test DB setup
│   ├── test_wallets.py       # Integration tests
│   └── test_concurrency.py   # Race condition & deadlock tests
├── docker-compose.yml
├── Dockerfile
└── entrypoint.sh
```