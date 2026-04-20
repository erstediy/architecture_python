# Документная модель MongoDB — Вариант 24: Система управления недвижимостью

## Коллекции

### `users`
Пользователи системы. Хранятся отдельно — на них ссылаются properties и viewings.

```json
{
  "_id": ObjectId,
  "login": "string",
  "password_hash": "string",
  "first_name": "string",
  "last_name": "string",
  "role": "admin|agent|buyer",
  "created_at": Date
}
```

### `properties`
Объекты недвижимости. Владелец хранится как **reference** (`owner_id: ObjectId`) — агент может иметь много объектов, дублировать данные пользователя в каждый объект нецелесообразно.

Просмотры хранятся как **embedded array** внутри объекта — просмотр не имеет смысла без объекта, выборки всегда идут в контексте конкретного объекта, и количество просмотров на объект ограничено.

```json
{
  "_id": ObjectId,
  "owner_id": ObjectId,
  "title": "string",
  "type": "apartment|house|commercial|land",
  "city": "string",
  "address": "string",
  "price": Number,
  "area": Number,
  "rooms": Number,
  "description": "string",
  "status": "active|sold|rented|inactive",
  "tags": ["string"],
  "viewings": [
    {
      "buyer_id": ObjectId,
      "buyer_login": "string",
      "scheduled_at": Date,
      "created_at": Date
    }
  ],
  "created_at": Date
}
```

## Embedded vs References

| Решение | Обоснование |
|---------|-------------|
| `owner_id` — reference | Пользователь существует независимо от объекта, имеет свои данные и операции |
| `viewings` — embedded | Просмотры всегда читаются вместе с объектом; отдельная коллекция дала бы лишний JOIN-эквивалент (lookup) при каждом запросе объекта |
| `buyer_login` в viewing — денормализация | Позволяет показать список просмотров без дополнительного lookup по users |
| `tags` — embedded array | Простой список строк, не требует отдельной сущности |
