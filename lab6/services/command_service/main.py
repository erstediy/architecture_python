from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timedelta
from enum import Enum
import jwt
import bcrypt
import os
import json
import asyncpg
from aiokafka import AIOKafkaProducer
from services.events import (
    Event, property_created, property_status_changed,
    viewing_scheduled, user_created,
)

SECRET_KEY = os.getenv("SECRET_KEY", "changeme-32-char-secret-key-here!")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
DB_DSN = os.getenv("DB_DSN", "postgresql://postgres:postgres@postgres:5432/real_estate")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")

TOPIC_PROPERTIES = "real-estate.properties"
TOPIC_VIEWINGS = "real-estate.viewings"
TOPIC_USERS = "real-estate.users"

app = FastAPI(title="Command Service", version="1.0.0")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

pool: Optional[asyncpg.Pool] = None
producer: Optional[AIOKafkaProducer] = None


class Role(str, Enum):
    admin = "admin"
    buyer = "buyer"
    agent = "agent"


class PropertyStatus(str, Enum):
    active = "active"
    sold = "sold"
    rented = "rented"
    inactive = "inactive"


class PropertyType(str, Enum):
    apartment = "apartment"
    house = "house"
    commercial = "commercial"
    land = "land"


class UserCreate(BaseModel):
    login: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., max_length=50)
    last_name: str = Field(..., max_length=50)
    role: Role = Role.buyer


class UserPublic(BaseModel):
    id: int
    login: str
    first_name: str
    last_name: str
    role: Role


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PropertyCreate(BaseModel):
    title: str = Field(..., max_length=200)
    type: PropertyType
    city: str = Field(..., max_length=100)
    address: str = Field(..., max_length=300)
    price: float = Field(..., gt=0)
    area: float = Field(..., gt=0)
    rooms: Optional[int] = Field(None, ge=0)
    description: Optional[str] = Field(None, max_length=2000)


class PropertyPublic(PropertyCreate):
    id: int
    owner_id: int
    status: PropertyStatus
    created_at: datetime


class PropertyStatusUpdate(BaseModel):
    status: PropertyStatus


class ViewingCreate(BaseModel):
    property_id: int
    scheduled_at: datetime


class ViewingPublic(BaseModel):
    id: int
    property_id: int
    buyer_id: int
    scheduled_at: datetime
    created_at: datetime


@app.on_event("startup")
async def startup():
    global pool, producer
    pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=10)
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode(),
        acks="all",
        enable_idempotence=True,
    )
    await producer.start()


@app.on_event("shutdown")
async def shutdown():
    await producer.stop()
    await pool.close()


async def _publish(topic: str, event: Event):
    await producer.send_and_wait(topic, event.model_dump(mode="json"))


@app.get("/health")
async def health():
    return {"status": "ok"}


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _make_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _row_to_user(row) -> UserPublic:
    return UserPublic(id=row["id"], login=row["login"],
                      first_name=row["first_name"], last_name=row["last_name"], role=row["role"])


def _row_to_property(row) -> PropertyPublic:
    return PropertyPublic(
        id=row["id"], owner_id=row["owner_id"], title=row["title"], type=row["type"],
        city=row["city"], address=row["address"], price=float(row["price"]),
        area=float(row["area"]), rooms=row["rooms"], description=row["description"],
        status=row["status"], created_at=row["created_at"],
    )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserPublic:
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except Exception:
        raise exc
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, login, first_name, last_name, role FROM users WHERE id = $1", user_id)
    if not row:
        raise exc
    return _row_to_user(row)


@app.post("/api/v1/auth/token", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, password_hash FROM users WHERE login = $1", form.username)
    if not row or not _verify(form.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect login or password")
    return Token(access_token=_make_token(row["id"]))


@app.post("/api/v1/users", response_model=UserPublic, status_code=201)
async def create_user(body: UserCreate):
    async with pool.acquire() as conn:
        if await conn.fetchrow("SELECT id FROM users WHERE login = $1", body.login):
            raise HTTPException(status_code=400, detail="Login already taken")
        row = await conn.fetchrow(
            "INSERT INTO users (login, password_hash, first_name, last_name, role) VALUES ($1,$2,$3,$4,$5) RETURNING *",
            body.login, _hash(body.password), body.first_name, body.last_name, body.role.value,
        )
    await _publish(TOPIC_USERS, user_created(row))
    return _row_to_user(row)


@app.post("/api/v1/properties", response_model=PropertyPublic, status_code=201)
async def create_property(body: PropertyCreate, user: UserPublic = Depends(get_current_user)):
    if user.role not in ("agent", "admin"):
        raise HTTPException(status_code=403, detail="Only agents and admins can add properties")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO properties (owner_id, title, type, city, address, price, area, rooms, description)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *""",
            user.id, body.title, body.type.value, body.city, body.address,
            body.price, body.area, body.rooms, body.description,
        )
    await _publish(TOPIC_PROPERTIES, property_created(row))
    return _row_to_property(row)


@app.patch("/api/v1/properties/{property_id}/status", response_model=PropertyPublic)
async def update_property_status(
    property_id: int, body: PropertyStatusUpdate, user: UserPublic = Depends(get_current_user)
):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM properties WHERE id = $1", property_id)
        if not row:
            raise HTTPException(status_code=404, detail="Property not found")
        if row["owner_id"] != user.id and user.role != "admin":
            raise HTTPException(status_code=403, detail="Not authorized")
        old_status = row["status"]
        row = await conn.fetchrow(
            "UPDATE properties SET status = $1 WHERE id = $2 RETURNING *",
            body.status.value, property_id,
        )
    await _publish(TOPIC_PROPERTIES, property_status_changed(row, old_status))
    return _row_to_property(row)


@app.post("/api/v1/viewings", response_model=ViewingPublic, status_code=201)
async def create_viewing(body: ViewingCreate, user: UserPublic = Depends(get_current_user)):
    if user.role not in ("buyer", "admin"):
        raise HTTPException(status_code=403, detail="Only buyers can schedule viewings")
    async with pool.acquire() as conn:
        if not await conn.fetchrow("SELECT id FROM properties WHERE id = $1", body.property_id):
            raise HTTPException(status_code=404, detail="Property not found")
        row = await conn.fetchrow(
            "INSERT INTO viewings (property_id, buyer_id, scheduled_at) VALUES ($1,$2,$3) RETURNING *",
            body.property_id, user.id, body.scheduled_at,
        )
    await _publish(TOPIC_VIEWINGS, viewing_scheduled(row))
    return ViewingPublic(id=row["id"], property_id=row["property_id"], buyer_id=row["buyer_id"],
                         scheduled_at=row["scheduled_at"], created_at=row["created_at"])
