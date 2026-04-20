from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import httpx
import os
import json
import asyncio
import asyncpg
from aiokafka import AIOKafkaConsumer

COMMAND_SERVICE_URL = os.getenv("COMMAND_SERVICE_URL", "http://command-service:8000")
DB_DSN = os.getenv("DB_DSN", "postgresql://postgres:postgres@postgres:5432/real_estate_read")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
KAFKA_GROUP = "query-service"

app = FastAPI(title="Query Service", version="1.0.0")
security = HTTPBearer()

pool: Optional[asyncpg.Pool] = None
consumer_task: Optional[asyncio.Task] = None


class PropertyStatus(str, Enum):
    active = "active"
    sold = "sold"
    rented = "rented"
    inactive = "inactive"


class PropertyPublic(BaseModel):
    id: int
    owner_id: int
    title: str
    type: str
    city: str
    address: str
    price: float
    area: float
    rooms: Optional[int]
    status: PropertyStatus
    created_at: datetime


class ViewingPublic(BaseModel):
    id: int
    property_id: int
    buyer_id: int
    scheduled_at: datetime


class UserPublic(BaseModel):
    id: int
    login: str
    first_name: str
    last_name: str
    role: str


READ_SCHEMA = """
CREATE TABLE IF NOT EXISTS properties_read (
    id          INTEGER PRIMARY KEY,
    owner_id    INTEGER NOT NULL,
    title       VARCHAR(200) NOT NULL,
    type        VARCHAR(20) NOT NULL,
    city        VARCHAR(100) NOT NULL,
    address     VARCHAR(300) NOT NULL,
    price       NUMERIC(14,2) NOT NULL,
    area        NUMERIC(10,2) NOT NULL,
    rooms       SMALLINT,
    status      VARCHAR(10) NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS viewings_read (
    id          INTEGER PRIMARY KEY,
    property_id INTEGER NOT NULL,
    buyer_id    INTEGER NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_read_city   ON properties_read(city);
CREATE INDEX IF NOT EXISTS idx_read_price  ON properties_read(price);
CREATE INDEX IF NOT EXISTS idx_read_status ON properties_read(status);
"""


async def _process_event(event: dict):
    etype = event.get("event_type")
    p = event.get("payload", {})
    async with pool.acquire() as conn:
        if etype == "property.created":
            await conn.execute("""
                INSERT INTO properties_read (id, owner_id, title, type, city, address, price, area, rooms, status, created_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (id) DO NOTHING
            """, p["id"], p["owner_id"], p["title"], p["type"], p["city"], p["address"],
                p["price"], p["area"], p.get("rooms"), p["status"],
                datetime.fromisoformat(p["created_at"]))

        elif etype == "property.status_changed":
            await conn.execute(
                "UPDATE properties_read SET status = $1 WHERE id = $2",
                p["new_status"], p["id"])

        elif etype == "viewing.scheduled":
            await conn.execute("""
                INSERT INTO viewings_read (id, property_id, buyer_id, scheduled_at)
                VALUES ($1,$2,$3,$4) ON CONFLICT (id) DO NOTHING
            """, p["id"], p["property_id"], p["buyer_id"],
                datetime.fromisoformat(p["scheduled_at"]))


async def _consume():
    consumer = AIOKafkaConsumer(
        "real-estate.properties", "real-estate.viewings", "real-estate.users",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=KAFKA_GROUP,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda v: json.loads(v.decode()),
    )
    await consumer.start()
    try:
        async for msg in consumer:
            try:
                await _process_event(msg.value)
                await consumer.commit()
            except Exception:
                pass
    finally:
        await consumer.stop()


@app.on_event("startup")
async def startup():
    global pool, consumer_task
    pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=10)
    async with pool.acquire() as conn:
        await conn.execute(READ_SCHEMA)
    consumer_task = asyncio.create_task(_consume())


@app.on_event("shutdown")
async def shutdown():
    if consumer_task:
        consumer_task.cancel()
    await pool.close()


@app.get("/health")
async def health():
    return {"status": "ok"}


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserPublic:
    token = credentials.credentials
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{COMMAND_SERVICE_URL}/api/v1/users/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Command service unavailable")
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return UserPublic(**resp.json())


def _row_to_property(row) -> PropertyPublic:
    return PropertyPublic(
        id=row["id"], owner_id=row["owner_id"], title=row["title"], type=row["type"],
        city=row["city"], address=row["address"], price=float(row["price"]),
        area=float(row["area"]), rooms=row["rooms"], status=row["status"],
        created_at=row["created_at"],
    )


@app.get("/api/v1/properties", response_model=List[PropertyPublic])
async def search_properties(
    city: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    user: UserPublic = Depends(get_current_user),
):
    if city is None and min_price is None and max_price is None:
        raise HTTPException(status_code=400, detail="Provide 'city', 'min_price' or 'max_price'")

    conditions = ["status = 'active'"]
    params: list = []
    i = 1
    if city:
        conditions.append(f"city = ${i}"); params.append(city); i += 1
    if min_price is not None:
        conditions.append(f"price >= ${i}"); params.append(min_price); i += 1
    if max_price is not None:
        conditions.append(f"price <= ${i}"); params.append(max_price); i += 1

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM properties_read WHERE {' AND '.join(conditions)} ORDER BY created_at DESC",
            *params,
        )
    return [_row_to_property(r) for r in rows]


@app.get("/api/v1/properties/user/{user_id}", response_model=List[PropertyPublic])
async def get_user_properties(user_id: int, user: UserPublic = Depends(get_current_user)):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM properties_read WHERE owner_id = $1 ORDER BY created_at DESC", user_id)
    return [_row_to_property(r) for r in rows]


@app.get("/api/v1/properties/{property_id}", response_model=PropertyPublic)
async def get_property(property_id: int, user: UserPublic = Depends(get_current_user)):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM properties_read WHERE id = $1", property_id)
    if not row:
        raise HTTPException(status_code=404, detail="Property not found")
    return _row_to_property(row)


@app.get("/api/v1/viewings/property/{property_id}", response_model=List[ViewingPublic])
async def get_property_viewings(property_id: int, user: UserPublic = Depends(get_current_user)):
    async with pool.acquire() as conn:
        prop = await conn.fetchrow("SELECT owner_id FROM properties_read WHERE id = $1", property_id)
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
        if prop["owner_id"] != user.id and user.role != "admin":
            raise HTTPException(status_code=403, detail="Not authorized")
        rows = await conn.fetch(
            "SELECT * FROM viewings_read WHERE property_id = $1 ORDER BY scheduled_at", property_id)
    return [ViewingPublic(id=r["id"], property_id=r["property_id"], buyer_id=r["buyer_id"],
                          scheduled_at=r["scheduled_at"]) for r in rows]
