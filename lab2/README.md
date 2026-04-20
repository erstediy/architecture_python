# Лабораторная работа 2: REST API сервис

## Вариант 24 — Система управления недвижимостью

## Сервисы

| Сервис | Порт | Описание |
|--------|------|----------|
| Auth Service | 8000 | Пользователи, аутентификация, JWT |
| Property Service | 8001 | Объекты недвижимости, просмотры |

## Запуск

```bash
docker-compose up --build
```

Swagger UI:
- http://localhost:8000/docs
- http://localhost:8001/docs

## API

### Пользователи (Auth Service, :8000)

```bash
# Создание пользователя
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"login":"agent1","password":"Password1","first_name":"Иван","last_name":"Петров","role":"agent"}'

# Получение токена
curl -X POST http://localhost:8000/api/v1/auth/token \
  -d "username=agent1&password=Password1"

# Поиск по логину
curl "http://localhost:8000/api/v1/users?login=agent1" \
  -H "Authorization: Bearer <TOKEN>"

# Поиск по маске имени
curl "http://localhost:8000/api/v1/users?name=иван" \
  -H "Authorization: Bearer <TOKEN>"
```

### Объекты недвижимости (Property Service, :8001)

```bash
# Добавление объекта (только agent/admin)
curl -X POST http://localhost:8001/api/v1/properties \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Квартира в центре","type":"apartment","city":"Москва","address":"ул. Тверская, 1","price":9500000,"area":65,"rooms":3}'

# Поиск по городу
curl "http://localhost:8001/api/v1/properties?city=Москва" \
  -H "Authorization: Bearer <TOKEN>"

# Поиск по цене
curl "http://localhost:8001/api/v1/properties?min_price=5000000&max_price=10000000" \
  -H "Authorization: Bearer <TOKEN>"

# Объекты пользователя
curl http://localhost:8001/api/v1/properties/user/1 \
  -H "Authorization: Bearer <TOKEN>"

# Изменение статуса
curl -X PATCH http://localhost:8001/api/v1/properties/1/status \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"status":"sold"}'
```

### Просмотры (Property Service, :8001)

```bash
# Запись на просмотр (только buyer/admin)
curl -X POST http://localhost:8001/api/v1/viewings \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"property_id":1,"scheduled_at":"2025-06-15T11:00:00"}'

# Просмотры объекта (только owner/admin)
curl http://localhost:8001/api/v1/viewings/property/1 \
  -H "Authorization: Bearer <TOKEN>"
```

## Тесты

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Аутентификация

JWT Bearer токен. Роли: `admin`, `agent`, `buyer`.

- Создание объектов: `agent`, `admin`
- Запись на просмотр: `buyer`, `admin`
- Просмотр записей: владелец объекта или `admin`
