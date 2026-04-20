\c real_estate

-- 1. Создание пользователя
INSERT INTO users (login, password_hash, first_name, last_name, role)
VALUES ('newuser', crypt('Password1', gen_salt('bf')), 'Имя', 'Фамилия', 'buyer')
RETURNING id, login, first_name, last_name, role;

-- 2. Поиск пользователя по логину
SELECT id, login, first_name, last_name, role
FROM users
WHERE login = 'agent1';

-- 3. Поиск пользователя по маске имени или фамилии
SELECT id, login, first_name, last_name, role
FROM users
WHERE first_name ILIKE '%иван%'
   OR last_name  ILIKE '%иван%';

-- 4. Добавление объекта недвижимости
INSERT INTO properties (owner_id, title, type, city, address, price, area, rooms, description)
VALUES (2, 'Новый объект', 'apartment', 'Москва', 'ул. Примерная, 1', 6000000, 55.0, 2, 'Описание')
RETURNING *;

-- 5. Поиск объектов по городу
SELECT id, title, type, city, address, price, area, rooms, status
FROM properties
WHERE city = 'Москва'
  AND status = 'active';

-- 6. Поиск объектов по цене (диапазон)
SELECT id, title, city, price, area, rooms, status
FROM properties
WHERE price BETWEEN 5000000 AND 10000000
  AND status = 'active'
ORDER BY price;

-- 7. Получение объектов конкретного пользователя
SELECT id, title, type, city, price, status, created_at
FROM properties
WHERE owner_id = 2
ORDER BY created_at DESC;

-- 8. Изменение статуса объекта
UPDATE properties
SET status = 'sold'
WHERE id = 1
  AND owner_id = 2
RETURNING id, title, status;

-- 9. Запись на просмотр
INSERT INTO viewings (property_id, buyer_id, scheduled_at)
VALUES (2, 4, '2025-07-01 10:00:00+03')
RETURNING *;

-- 10. Получение записей на просмотр объекта
SELECT v.id, v.scheduled_at, v.created_at,
       u.id AS buyer_id, u.login AS buyer_login,
       u.first_name, u.last_name
FROM viewings v
JOIN users u ON u.id = v.buyer_id
WHERE v.property_id = 1
ORDER BY v.scheduled_at;
