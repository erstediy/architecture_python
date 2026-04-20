# Event-Driven Architecture — Система управления недвижимостью

## 1. Анализ событий

### Команды → События

| Команда | Событие | Producer |
|---------|---------|----------|
| CreateProperty | `property.created` | Command Service |
| UpdatePropertyStatus | `property.status_changed` | Command Service |
| ScheduleViewing | `viewing.scheduled` | Command Service |
| CreateUser | `user.created` | Command Service |

### Потребители событий

| Событие | Consumers |
|---------|-----------|
| `property.created` | Query Service (обновление read-модели) |
| `property.status_changed` | Query Service, Notification Service |
| `viewing.scheduled` | Query Service, Notification Service |
| `user.created` | Query Service |

---

## 2. Архитектура

```
Client
  │
  ▼
Command Service  ──── Kafka ────▶  Query Service (read DB)
  │  (write DB)                ▶  Notification Service
  │
  ▼
PostgreSQL (write)          PostgreSQL (read replica / same DB, separate schema)
```

### Топики Kafka

| Топик | Partitions | Retention |
|-------|-----------|-----------|
| `real-estate.properties` | 3 | 7 days |
| `real-estate.viewings` | 3 | 7 days |
| `real-estate.users` | 1 | 7 days |

Routing по event type через заголовок `event_type`.

### Гарантии доставки

- **Producer**: `acks=all`, `enable.idempotence=true` → exactly-once на запись в Kafka
- **Consumer**: ручной commit offset после успешной обработки → at-least-once семантика
- Идемпотентность consumer обеспечивается через `ON CONFLICT DO NOTHING` / upsert в read-модели

---

## 3. CQRS

### Write Model (Command Service)
- Принимает REST-команды
- Валидирует и записывает в PostgreSQL (write DB)
- Публикует событие в Kafka

### Read Model (Query Service)
- Слушает Kafka, проецирует события в read-таблицы
- Отвечает на GET-запросы из read DB
- Read DB синхронизируется асинхронно — eventual consistency

### Синхронизация
```
Command Service
  └─ INSERT INTO properties (write) → publish property.created
                                           │
                                    Kafka  │
                                           ▼
                                    Query Service
                                      └─ UPSERT INTO properties_read
```
