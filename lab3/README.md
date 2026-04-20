# Лабораторная работа 3: PostgreSQL — схема БД, индексы, оптимизация

## Вариант 24 — Система управления недвижимостью

## Схема БД

| Таблица | Описание |
|---------|----------|
| `users` | Пользователи системы (admin, agent, buyer) |
| `properties` | Объекты недвижимости |
| `viewings` | Записи на просмотр объектов |

## Запуск

```bash
docker-compose up --build
```

PostgreSQL поднимается с автоматическим применением `db/schema.sql` и `db/data.sql`.

Swagger UI:
- http://localhost:8000/docs — Auth Service
- http://localhost:8001/docs — Property Service

## Тесты

Тесты используют `testcontainers-python` — PostgreSQL поднимается автоматически в Docker-контейнере, никакой локальной БД не нужно. Требуется только запущенный Docker.

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Примеры запросов

```bash
# Создать пользователя
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"login":"agent1","password":"Password1","first_name":"Иван","last_name":"Петров","role":"agent"}'

# Получить токен
curl -X POST http://localhost:8000/api/v1/auth/token \
  -d "username=agent1&password=Password1"

# Поиск объектов по городу
curl "http://localhost:8001/api/v1/properties?city=Москва" \
  -H "Authorization: Bearer <TOKEN>"

# Поиск по цене
curl "http://localhost:8001/api/v1/properties?min_price=5000000&max_price=10000000" \
  -H "Authorization: Bearer <TOKEN>"
```

## Индексы

Подробное описание индексов и планов выполнения — в `db/optimization.md`.
