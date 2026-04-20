# Лабораторная работа 5: Кеширование и Rate Limiting

## Вариант 24 — Система управления недвижимостью

Подробное описание стратегий — в `performance_design.md`.

## Что реализовано

### Кеширование (Redis, Cache-Aside)

| Endpoint | Ключ | TTL | Инвалидация |
|----------|------|-----|-------------|
| `GET /api/v1/properties?city=` | `properties:city:{city}` | 60 сек | При создании/смене статуса объекта в этом городе |
| `GET /api/v1/properties?min_price=&max_price=` | `properties:price:{min}:{max}` | 60 сек | При любом изменении объекта |
| `GET /api/v1/properties/{id}` | `properties:id:{id}` | 120 сек | При смене статуса |
| `GET /api/v1/users/me` | `users:me:{user_id}` | 30 сек | — |

### Rate Limiting

| Endpoint | Алгоритм | Лимит |
|----------|----------|-------|
| `POST /api/v1/auth/token` | Fixed Window Counter | 10 req/60s на IP |
| `GET /api/v1/properties` | Sliding Window Counter | 100 req/60s на IP |

При превышении — `429 Too Many Requests` с заголовками:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1717200060
Retry-After: 42
```

## Запуск

```bash
docker-compose up --build
```

- http://localhost:8000/docs — Auth Service
- http://localhost:8001/docs — Property Service

## Тесты

```bash
pip install -r requirements.txt
pytest tests/ -v
```
