# Event Catalog — Система управления недвижимостью

---

## `property.created`

**Топик:** `real-estate.properties`

**Producer:** Command Service

**Consumers:** Query Service, Notification Service

**Гарантии:** at-least-once (idempotent upsert на стороне consumer)

**Payload:**
```json
{
  "event_type": "property.created",
  "event_id": "uuid",
  "occurred_at": "2025-06-01T10:00:00Z",
  "payload": {
    "id": 1,
    "owner_id": 42,
    "title": "Уютная квартира",
    "type": "apartment",
    "city": "Москва",
    "address": "ул. Ленина, 10",
    "price": 8500000.0,
    "area": 54.0,
    "rooms": 2,
    "status": "active",
    "created_at": "2025-06-01T10:00:00Z"
  }
}
```

---

## `property.status_changed`

**Топик:** `real-estate.properties`

**Producer:** Command Service

**Consumers:** Query Service, Notification Service

**Гарантии:** at-least-once

**Payload:**
```json
{
  "event_type": "property.status_changed",
  "event_id": "uuid",
  "occurred_at": "2025-06-01T11:00:00Z",
  "payload": {
    "id": 1,
    "owner_id": 42,
    "old_status": "active",
    "new_status": "sold"
  }
}
```

---

## `viewing.scheduled`

**Топик:** `real-estate.viewings`

**Producer:** Command Service

**Consumers:** Query Service, Notification Service

**Гарантии:** at-least-once

**Payload:**
```json
{
  "event_type": "viewing.scheduled",
  "event_id": "uuid",
  "occurred_at": "2025-06-01T12:00:00Z",
  "payload": {
    "id": 10,
    "property_id": 1,
    "buyer_id": 99,
    "scheduled_at": "2025-06-15T10:00:00Z"
  }
}
```

---

## `user.created`

**Топик:** `real-estate.users`

**Producer:** Command Service

**Consumers:** Query Service

**Гарантии:** at-least-once

**Payload:**
```json
{
  "event_type": "user.created",
  "event_id": "uuid",
  "occurred_at": "2025-06-01T09:00:00Z",
  "payload": {
    "id": 42,
    "login": "agent1",
    "first_name": "Иван",
    "last_name": "Петров",
    "role": "agent"
  }
}
```
