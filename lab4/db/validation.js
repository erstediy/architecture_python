// Валидация схем через $jsonSchema
// Запуск: mongosh real_estate < validation.js

db = db.getSiblingDB("real_estate");

// ── Валидация коллекции users ──────────────────────────────────────────────

db.runCommand({
  collMod: "users",
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["login", "password_hash", "first_name", "last_name", "role", "created_at"],
      properties: {
        login: {
          bsonType: "string",
          minLength: 3,
          maxLength: 50,
          pattern: "^[a-zA-Z0-9_]+$",
          description: "Логин: 3–50 символов, только буквы/цифры/underscore",
        },
        password_hash: {
          bsonType: "string",
          minLength: 1,
          description: "Хэш пароля обязателен",
        },
        first_name: {
          bsonType: "string",
          minLength: 1,
          maxLength: 50,
        },
        last_name: {
          bsonType: "string",
          minLength: 1,
          maxLength: 50,
        },
        role: {
          bsonType: "string",
          enum: ["admin", "agent", "buyer"],
          description: "Роль: admin, agent или buyer",
        },
        created_at: {
          bsonType: "date",
        },
      },
    },
  },
  validationLevel: "strict",
  validationAction: "error",
});
print("Валидация для users установлена");

// ── Валидация коллекции properties ────────────────────────────────────────

db.runCommand({
  collMod: "properties",
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["owner_id", "title", "type", "city", "address", "price", "area", "status", "created_at"],
      properties: {
        owner_id: {
          bsonType: "objectId",
        },
        title: {
          bsonType: "string",
          minLength: 1,
          maxLength: 200,
        },
        type: {
          bsonType: "string",
          enum: ["apartment", "house", "commercial", "land"],
        },
        city: {
          bsonType: "string",
          minLength: 1,
          maxLength: 100,
        },
        address: {
          bsonType: "string",
          minLength: 1,
          maxLength: 300,
        },
        price: {
          bsonType: "number",
          minimum: 1,
          description: "Цена должна быть больше 0",
        },
        area: {
          bsonType: "number",
          minimum: 0.1,
          description: "Площадь должна быть больше 0",
        },
        rooms: {
          bsonType: ["int", "null"],
          minimum: 0,
        },
        status: {
          bsonType: "string",
          enum: ["active", "sold", "rented", "inactive"],
        },
        tags: {
          bsonType: "array",
          items: { bsonType: "string" },
        },
        viewings: {
          bsonType: "array",
          items: {
            bsonType: "object",
            required: ["buyer_id", "buyer_login", "scheduled_at"],
            properties: {
              buyer_id: { bsonType: "objectId" },
              buyer_login: { bsonType: "string" },
              scheduled_at: { bsonType: "date" },
              created_at: { bsonType: "date" },
            },
          },
        },
        created_at: {
          bsonType: "date",
        },
      },
    },
  },
  validationLevel: "strict",
  validationAction: "error",
});
print("Валидация для properties установлена");

// ── Тест невалидных данных ─────────────────────────────────────────────────

print("\n--- Тест 1: короткий логин (должна быть ошибка) ---");
try {
  db.users.insertOne({
    login: "ab",
    password_hash: "$2b$12$x",
    first_name: "Тест",
    last_name: "Тест",
    role: "buyer",
    created_at: new Date(),
  });
  print("ПРОВАЛ: ошибки не было");
} catch (e) {
  print("OK: " + e.message);
}

print("\n--- Тест 2: недопустимая роль (должна быть ошибка) ---");
try {
  db.users.insertOne({
    login: "testuser",
    password_hash: "$2b$12$x",
    first_name: "Тест",
    last_name: "Тест",
    role: "superuser",
    created_at: new Date(),
  });
  print("ПРОВАЛ: ошибки не было");
} catch (e) {
  print("OK: " + e.message);
}

print("\n--- Тест 3: отрицательная цена (должна быть ошибка) ---");
try {
  db.properties.insertOne({
    owner_id: new ObjectId(),
    title: "Тест",
    type: "apartment",
    city: "Москва",
    address: "ул. Тест, 1",
    price: -100,
    area: 50.0,
    status: "active",
    viewings: [],
    created_at: new Date(),
  });
  print("ПРОВАЛ: ошибки не было");
} catch (e) {
  print("OK: " + e.message);
}

print("\n--- Тест 4: невалидный тип объекта (должна быть ошибка) ---");
try {
  db.properties.insertOne({
    owner_id: new ObjectId(),
    title: "Тест",
    type: "garage",
    city: "Москва",
    address: "ул. Тест, 1",
    price: 1000000,
    area: 50.0,
    status: "active",
    viewings: [],
    created_at: new Date(),
  });
  print("ПРОВАЛ: ошибки не было");
} catch (e) {
  print("OK: " + e.message);
}

print("\n--- Тест 5: валидный документ (должен пройти) ---");
try {
  const r = db.users.insertOne({
    login: "validuser",
    password_hash: "$2b$12$x",
    first_name: "Валид",
    last_name: "Пользователь",
    role: "buyer",
    created_at: new Date(),
  });
  db.users.deleteOne({ _id: r.insertedId });
  print("OK: валидный документ принят");
} catch (e) {
  print("ПРОВАЛ: " + e.message);
}
