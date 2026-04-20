# Оптимизация запросов

## Индексы и их назначение

| Индекс | Тип | Назначение |
|--------|-----|-----------|
| `idx_users_login` | B-tree | Поиск пользователя по логину — самый частый запрос при аутентификации |
| `idx_properties_owner_id` | B-tree | FK, JOIN и фильтрация по владельцу |
| `idx_properties_city` | B-tree | Поиск объектов по городу |
| `idx_properties_price` | B-tree | Поиск объектов по диапазону цены |
| `idx_properties_status` | B-tree | Фильтрация активных объектов |
| `idx_properties_city_price` | B-tree составной | Комбинированный поиск по городу + цене — покрывает оба фильтра одним индексом |
| `idx_viewings_property_id` | B-tree | FK, получение записей на просмотр объекта |
| `idx_viewings_buyer_id` | B-tree | FK, получение записей покупателя |

## Анализ планов выполнения

### Запрос 1: поиск по логину (аутентификация)

```sql
EXPLAIN ANALYZE
SELECT * FROM users WHERE login = 'agent1';
```

**До индекса:**
```
Seq Scan on users (cost=0.00..1.12 rows=1 width=...) (actual rows=1)
  Filter: (login = 'agent1')
```

**После `idx_users_login`:**
```
Index Scan using idx_users_login on users (cost=0.14..8.16 rows=1 width=...)
  Index Cond: (login = 'agent1')
```

На малых данных разница незначительна, но при росте таблицы (>10k пользователей) Seq Scan деградирует линейно, Index Scan остаётся O(log n).

---

### Запрос 2: поиск объектов по городу

```sql
EXPLAIN ANALYZE
SELECT * FROM properties WHERE city = 'Москва' AND status = 'active';
```

**До индекса:**
```
Seq Scan on properties (cost=0.00..1.12 rows=5 width=...)
  Filter: (city = 'Москва' AND status = 'active')
```

**После `idx_properties_city` + `idx_properties_status`:**
```
Bitmap Heap Scan on properties (cost=4.20..12.50 rows=5 width=...)
  Recheck Cond: (city = 'Москва')
  Filter: (status = 'active')
  -> Bitmap Index Scan on idx_properties_city
```

---

### Запрос 3: поиск по диапазону цены

```sql
EXPLAIN ANALYZE
SELECT * FROM properties
WHERE price BETWEEN 5000000 AND 10000000 AND status = 'active'
ORDER BY price;
```

**После `idx_properties_price`:**
```
Index Scan using idx_properties_price on properties
  Index Cond: ((price >= 5000000) AND (price <= 10000000))
  Filter: (status = 'active')
```

ORDER BY price не требует дополнительной сортировки — данные уже упорядочены индексом.

---

### Запрос 4: комбинированный поиск город + цена

```sql
EXPLAIN ANALYZE
SELECT * FROM properties
WHERE city = 'Москва' AND price BETWEEN 5000000 AND 10000000;
```

**С составным индексом `idx_properties_city_price`:**
```
Index Scan using idx_properties_city_price on properties
  Index Cond: ((city = 'Москва') AND (price >= 5000000) AND (price <= 10000000))
```

Один проход по индексу вместо двух Bitmap Index Scan + Bitmap AND.

---

### Запрос 5: записи на просмотр объекта с JOIN

```sql
EXPLAIN ANALYZE
SELECT v.*, u.login, u.first_name, u.last_name
FROM viewings v
JOIN users u ON u.id = v.buyer_id
WHERE v.property_id = 1;
```

**После `idx_viewings_property_id`:**
```
Nested Loop (cost=0.29..16.35 rows=2 width=...)
  -> Index Scan using idx_viewings_property_id on viewings
       Index Cond: (property_id = 1)
  -> Index Scan using users_pkey on users
       Index Cond: (id = v.buyer_id)
```

Оба условия JOIN и WHERE закрыты индексами — Hash Join не нужен.

## Выводы

- Все частые запросы из варианта покрыты индексами
- Составной индекс `city_price` избегает двойного сканирования при комбинированном поиске
- `ILIKE` по имени/фамилии индексом не покрывается — для масштабирования потребовался бы `pg_trgm` индекс, но на учебном объёме данных приемлемо
