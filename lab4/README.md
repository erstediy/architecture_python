# Лабораторная работа 4: MongoDB — документная модель, CRUD, валидация схем

## Вариант 24 — Система управления недвижимостью

## Структура

| Файл | Описание |
|------|----------|
| `db/schema_design.md` | Документная модель, обоснование embedded vs references |
| `db/data.js` | Тестовые данные (10 пользователей, 10 объектов) |
| `db/queries.js` | CRUD-запросы + агрегация |
| `db/validation.js` | Валидация схем через `$jsonSchema` |

## Документная модель

Две коллекции:
- **`users`** — пользователи (admin, agent, buyer)
- **`properties`** — объекты недвижимости; просмотры (`viewings`) хранятся как embedded array внутри объекта

## Запуск

```bash
docker-compose up --build
```

MongoDB поднимается с автоматической загрузкой тестовых данных из `db/data.js`.

Swagger UI:
- http://localhost:8000/docs — Auth Service
- http://localhost:8001/docs — Property Service

### Загрузка данных и запросов вручную

```bash
mongosh real_estate < db/data.js
mongosh real_estate < db/validation.js
mongosh real_estate < db/queries.js
```

## Тесты

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
