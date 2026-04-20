// Тестовые данные для системы управления недвижимостью
// Запуск: mongosh real_estate < data.js

db = db.getSiblingDB("real_estate");

db.users.drop();
db.properties.drop();

// ── Users ──────────────────────────────────────────────────────────────────

const admin  = ObjectId();
const agent1 = ObjectId();
const agent2 = ObjectId();
const agent3 = ObjectId();
const agent4 = ObjectId();
const buyer1 = ObjectId();
const buyer2 = ObjectId();
const buyer3 = ObjectId();
const buyer4 = ObjectId();
const buyer5 = ObjectId();

db.users.insertMany([
  { _id: admin,  login: "admin",   password_hash: "$2b$12$hash0", first_name: "Сергей",    last_name: "Админов",   role: "admin",  created_at: new Date("2024-01-01") },
  { _id: agent1, login: "agent1",  password_hash: "$2b$12$hash1", first_name: "Иван",      last_name: "Петров",    role: "agent",  created_at: new Date("2024-01-02") },
  { _id: agent2, login: "agent2",  password_hash: "$2b$12$hash2", first_name: "Мария",     last_name: "Сидорова",  role: "agent",  created_at: new Date("2024-01-03") },
  { _id: agent3, login: "agent3",  password_hash: "$2b$12$hash3", first_name: "Алексей",   last_name: "Козлов",    role: "agent",  created_at: new Date("2024-01-04") },
  { _id: agent4, login: "agent4",  password_hash: "$2b$12$hash4", first_name: "Наталья",   last_name: "Новикова",  role: "agent",  created_at: new Date("2024-01-05") },
  { _id: buyer1, login: "buyer1",  password_hash: "$2b$12$hash5", first_name: "Олег",      last_name: "Морозов",   role: "buyer",  created_at: new Date("2024-01-06") },
  { _id: buyer2, login: "buyer2",  password_hash: "$2b$12$hash6", first_name: "Анна",      last_name: "Волкова",   role: "buyer",  created_at: new Date("2024-01-07") },
  { _id: buyer3, login: "buyer3",  password_hash: "$2b$12$hash7", first_name: "Дмитрий",   last_name: "Зайцев",    role: "buyer",  created_at: new Date("2024-01-08") },
  { _id: buyer4, login: "buyer4",  password_hash: "$2b$12$hash8", first_name: "Екатерина", last_name: "Павлова",   role: "buyer",  created_at: new Date("2024-01-09") },
  { _id: buyer5, login: "buyer5",  password_hash: "$2b$12$hash9", first_name: "Михаил",    last_name: "Семёнов",   role: "buyer",  created_at: new Date("2024-01-10") },
]);

// ── Properties ─────────────────────────────────────────────────────────────

db.properties.insertMany([
  {
    owner_id: agent1, title: "Уютная двушка у метро", type: "apartment",
    city: "Москва", address: "ул. Ленина, 10", price: 8500000, area: 54.0, rooms: 2,
    description: "Свежий ремонт, рядом метро Сокол",
    status: "active", tags: ["ремонт", "метро", "тихий двор"],
    viewings: [
      { buyer_id: buyer1, buyer_login: "buyer1", scheduled_at: new Date("2025-06-01T10:00:00"), created_at: new Date("2025-05-20") },
      { buyer_id: buyer2, buyer_login: "buyer2", scheduled_at: new Date("2025-06-03T14:00:00"), created_at: new Date("2025-05-21") },
    ],
    created_at: new Date("2024-02-01"),
  },
  {
    owner_id: agent1, title: "Просторная трёшка в центре", type: "apartment",
    city: "Москва", address: "Тверская ул., 5", price: 15000000, area: 89.5, rooms: 3,
    description: "Панорамный вид, паркинг",
    status: "active", tags: ["центр", "паркинг", "панорама"],
    viewings: [
      { buyer_id: buyer3, buyer_login: "buyer3", scheduled_at: new Date("2025-06-05T11:00:00"), created_at: new Date("2025-05-22") },
    ],
    created_at: new Date("2024-02-10"),
  },
  {
    owner_id: agent2, title: "Студия на Невском", type: "apartment",
    city: "Санкт-Петербург", address: "Невский пр., 88", price: 4200000, area: 28.0, rooms: 1,
    description: "Идеально для инвестиций",
    status: "active", tags: ["инвестиции", "центр"],
    viewings: [],
    created_at: new Date("2024-02-15"),
  },
  {
    owner_id: agent2, title: "Коттедж с участком", type: "house",
    city: "Москва", address: "пос. Рублёво, д. 7", price: 32000000, area: 220.0, rooms: 5,
    description: "Охраняемый посёлок, 15 соток",
    status: "active", tags: ["коттедж", "участок", "охрана"],
    viewings: [
      { buyer_id: buyer4, buyer_login: "buyer4", scheduled_at: new Date("2025-06-10T10:00:00"), created_at: new Date("2025-05-25") },
    ],
    created_at: new Date("2024-03-01"),
  },
  {
    owner_id: agent3, title: "Офис в бизнес-центре", type: "commercial",
    city: "Москва", address: "Пресненская наб., 12", price: 25000000, area: 150.0, rooms: 0,
    description: "Класс А, вид на Москва-Сити",
    status: "active", tags: ["офис", "класс-А", "Москва-Сити"],
    viewings: [],
    created_at: new Date("2024-03-10"),
  },
  {
    owner_id: agent3, title: "Однушка у парка", type: "apartment",
    city: "Санкт-Петербург", address: "Московский пр., 200", price: 5800000, area: 38.5, rooms: 1,
    description: "Рядом Парк Победы",
    status: "sold", tags: ["парк", "тихий район"],
    viewings: [
      { buyer_id: buyer5, buyer_login: "buyer5", scheduled_at: new Date("2025-04-01T12:00:00"), created_at: new Date("2025-03-20") },
    ],
    created_at: new Date("2024-03-15"),
  },
  {
    owner_id: agent4, title: "Земельный участок под ИЖС", type: "land",
    city: "Краснодар", address: "ст. Елизаветинская, уч. 45", price: 1200000, area: 600.0, rooms: 0,
    description: "20 соток, все коммуникации",
    status: "active", tags: ["ИЖС", "коммуникации"],
    viewings: [],
    created_at: new Date("2024-04-01"),
  },
  {
    owner_id: agent4, title: "Двушка с ремонтом", type: "apartment",
    city: "Краснодар", address: "ул. Красная, 55", price: 6300000, area: 61.0, rooms: 2,
    description: "Дизайнерский ремонт, мебель",
    status: "active", tags: ["ремонт", "мебель"],
    viewings: [
      { buyer_id: buyer1, buyer_login: "buyer1", scheduled_at: new Date("2025-06-15T09:00:00"), created_at: new Date("2025-06-01") },
    ],
    created_at: new Date("2024-04-10"),
  },
  {
    owner_id: agent1, title: "Таунхаус в Подмосковье", type: "house",
    city: "Москва", address: "г. Красногорск, ул. Садовая, 3", price: 12000000, area: 130.0, rooms: 4,
    description: "Закрытый посёлок, собственный дворик",
    status: "rented", tags: ["таунхаус", "посёлок"],
    viewings: [],
    created_at: new Date("2024-04-20"),
  },
  {
    owner_id: agent2, title: "Склад на промзоне", type: "commercial",
    city: "Санкт-Петербург", address: "Обводный кан., 134", price: 9000000, area: 500.0, rooms: 0,
    description: "Высокие потолки, ж/д ветка",
    status: "inactive", tags: ["склад", "промзона", "ж/д"],
    viewings: [],
    created_at: new Date("2024-05-01"),
  },
]);

print("Данные загружены: " + db.users.countDocuments() + " пользователей, " + db.properties.countDocuments() + " объектов");
