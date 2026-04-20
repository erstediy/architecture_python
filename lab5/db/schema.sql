CREATE EXTENSION IF NOT EXISTS pgcrypto;

\c real_estate

CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    login       VARCHAR(50)  UNIQUE NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    first_name  VARCHAR(50)  NOT NULL,
    last_name   VARCHAR(50)  NOT NULL,
    role        VARCHAR(10)  NOT NULL CHECK (role IN ('admin', 'buyer', 'agent')),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS properties (
    id          SERIAL PRIMARY KEY,
    owner_id    INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(200) NOT NULL,
    type        VARCHAR(20)  NOT NULL CHECK (type IN ('apartment', 'house', 'commercial', 'land')),
    city        VARCHAR(100) NOT NULL,
    address     VARCHAR(300) NOT NULL,
    price       NUMERIC(14,2) NOT NULL CHECK (price > 0),
    area        NUMERIC(10,2) NOT NULL CHECK (area > 0),
    rooms       SMALLINT     CHECK (rooms >= 0),
    description TEXT,
    status      VARCHAR(10)  NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'sold', 'rented', 'inactive')),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS viewings (
    id          SERIAL PRIMARY KEY,
    property_id INTEGER      NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    buyer_id    INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scheduled_at TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- индексы для FK
CREATE INDEX IF NOT EXISTS idx_properties_owner_id   ON properties(owner_id);
CREATE INDEX IF NOT EXISTS idx_viewings_property_id  ON viewings(property_id);
CREATE INDEX IF NOT EXISTS idx_viewings_buyer_id     ON viewings(buyer_id);

-- индексы для WHERE в частых запросах
CREATE INDEX IF NOT EXISTS idx_properties_city       ON properties(city);
CREATE INDEX IF NOT EXISTS idx_properties_price      ON properties(price);
CREATE INDEX IF NOT EXISTS idx_properties_status     ON properties(status);
CREATE INDEX IF NOT EXISTS idx_users_login           ON users(login);

-- составной индекс для поиска по городу + цене
CREATE INDEX IF NOT EXISTS idx_properties_city_price ON properties(city, price);
