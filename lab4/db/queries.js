// CRUD-запросы и агрегации для системы управления недвижимостью
// Запуск: mongosh real_estate < queries.js

db = db.getSiblingDB("real_estate");

print("\n=== CREATE ===");

// Создать пользователя
db.users.insertOne({
  login: "newagent",
  password_hash: "$2b$12$newhash",
  first_name: "Новый",
  last_name: "Агент",
  role: "agent",
  created_at: new Date(),
});
print("Пользователь создан");

// Создать объект недвижимости
const agentId = db.users.findOne({ login: "agent1" })._id;
db.properties.insertOne({
  owner_id: agentId,
  title: "Новая квартира",
  type: "apartment",
  city: "Москва",
  address: "ул. Тестовая, 1",
  price: 7000000,
  area: 50.0,
  rooms: 2,
  status: "active",
  tags: ["новостройка"],
  viewings: [],
  created_at: new Date(),
});
print("Объект создан");

// Добавить просмотр к объекту ($push)
const prop = db.properties.findOne({ city: "Краснодар", status: "active" });
const buyer = db.users.findOne({ login: "buyer3" });
db.properties.updateOne(
  { _id: prop._id },
  {
    $push: {
      viewings: {
        buyer_id: buyer._id,
        buyer_login: buyer.login,
        scheduled_at: new Date("2025-07-01T10:00:00"),
        created_at: new Date(),
      },
    },
  }
);
print("Просмотр добавлен");

print("\n=== READ ===");

// Поиск по городу ($eq)
printjson(db.properties.find({ city: { $eq: "Москва" }, status: "active" }, { title: 1, price: 1, city: 1 }).toArray());

// Поиск по диапазону цены ($gt, $lt)
printjson(db.properties.find({ price: { $gt: 5000000, $lt: 15000000 } }, { title: 1, price: 1 }).toArray());

// Поиск по типу из списка ($in)
printjson(db.properties.find({ type: { $in: ["apartment", "house"] } }, { title: 1, type: 1, city: 1 }).toArray());

// Поиск по городу И статусу ($and)
printjson(db.properties.find({
  $and: [{ city: "Санкт-Петербург" }, { status: { $ne: "sold" } }],
}, { title: 1, city: 1, status: 1 }).toArray());

// Поиск по городу ИЛИ дешёвые объекты ($or)
printjson(db.properties.find({
  $or: [{ city: "Краснодар" }, { price: { $lt: 5000000 } }],
}, { title: 1, city: 1, price: 1 }).toArray());

// Поиск по тегу (поиск в массиве)
printjson(db.properties.find({ tags: "ремонт" }, { title: 1, tags: 1 }).toArray());

// Поиск пользователя по логину
printjson(db.users.findOne({ login: "agent1" }, { password_hash: 0 }));

print("\n=== UPDATE ===");

// Обновить статус объекта
db.properties.updateOne(
  { title: "Новая квартира" },
  { $set: { status: "sold" } }
);
print("Статус обновлён");

// Добавить тег ($addToSet — без дубликатов)
db.properties.updateOne(
  { title: "Уютная двушка у метро" },
  { $addToSet: { tags: "топ-предложение" } }
);
print("Тег добавлен");

// Удалить тег ($pull)
db.properties.updateOne(
  { title: "Уютная двушка у метро" },
  { $pull: { tags: "топ-предложение" } }
);
print("Тег удалён");

// Обновить цену всех активных объектов в Краснодаре (скидка 5%)
db.properties.updateMany(
  { city: "Краснодар", status: "active" },
  [{ $set: { price: { $multiply: ["$price", 0.95] } } }]
);
print("Цены обновлены");

print("\n=== DELETE ===");

// Удалить конкретный просмотр из объекта ($pull по buyer_login)
db.properties.updateOne(
  { title: "Уютная двушка у метро" },
  { $pull: { viewings: { buyer_login: "buyer2" } } }
);
print("Просмотр удалён");

// Удалить объект
db.properties.deleteOne({ title: "Новая квартира" });
print("Объект удалён");

// Удалить неактивные объекты
db.properties.deleteMany({ status: "inactive" });
print("Неактивные объекты удалены");

print("\n=== AGGREGATION ===");

// Статистика по городам: количество объектов, средняя цена, мин/макс цена
const result = db.properties.aggregate([
  { $match: { status: "active" } },
  {
    $group: {
      _id: "$city",
      count: { $sum: 1 },
      avg_price: { $avg: "$price" },
      min_price: { $min: "$price" },
      max_price: { $max: "$price" },
      total_viewings: { $sum: { $size: "$viewings" } },
    },
  },
  {
    $project: {
      city: "$_id",
      _id: 0,
      count: 1,
      avg_price: { $round: ["$avg_price", 0] },
      min_price: 1,
      max_price: 1,
      total_viewings: 1,
    },
  },
  { $sort: { avg_price: -1 } },
]).toArray();
printjson(result);
