from fastapi import FastAPI, HTTPException, Depends, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import httpx
import os
import json
import time
import asyncpg
import redis.asyncio as aioredis

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
DB_DSN = os.getenv("DB_DSN", "postgresql://postgres:postgres@postgres:5432/real_estate")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

SEARCH_CACHE_TTL = 60
PROPERTY_CACHE_TTL = 120
RATE_LIMIT_SEARCH_MAX = 100
RATE_LIMIT_SEARCH_WINDOW = 60

app = FastAPI(title="Property Service", version="1.0.0")
security = HTTPBearer()

pool: Optional[asyncpg.Pool] = None
redis: Optional[aioredis.Redis] = None


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


class UserPublic(BaseModel):
    id: int
    login: str
    first_name: str
    last_name: str
    role: str


@app.on_event("startup")
async def startup():
    global pool, redis
    pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=10)
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)


@app.on_event("shutdown")
async def shutdown():
    await pool.close()
    await redis.aclose()


@app.get("/health")
async def health():
    return {"status": "ok"}


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserPublic:
    token = credentials.credentials
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{AUTH_SERVICE_URL}/api/v1/users/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Auth service unavailable")
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return UserPublic(**resp.json())


async def _rate_limit_sliding_window(key: str, limit: int, window: int, response: Response):
    now = time.time()
    redis_key = f"rl:sw:{key}"

    pipe = redis.pipeline()
    pipe.zremrangebyscore(redis_key, 0, now - window)
    pipe.zadd(redis_key, {str(now): now})
    pipe.zcard(redis_key)
    pipe.expire(redis_key, window)
    results = await pipe.execute()
    count = results[2]

    reset_at = int(now) + window
    remaining = max(0, limit - count)

    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_at)

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_at),
                "Retry-After": str(window),
            },
        )


def _row_to_property(row) -> PropertyPublic:
    return PropertyPublic(
        id=row["id"], owner_id=row["owner_id"], title=row["title"], type=row["type"],
        city=row["city"], address=row["address"], price=float(row["price"]),
        area=float(row["area"]), rooms=row["rooms"], description=row["description"],
        status=row["status"], created_at=row["created_at"],
    )


async def _invalidate_search_cache(city: Optional[str] = None):
    if city:
        await redis.delete(f"properties:city:{city.lower()}")
    keys = await redis.keys("properties:price:*")
    if keys:
        await redis.delete(*keys)


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
    await _invalidate_search_cache(city=body.city)
    return _row_to_property(row)


@app.get("/api/v1/properties", response_model=List[PropertyPublic])
async def search_properties(
    request: Request,
    response: Response,
    city: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    user: UserPublic = Depends(get_current_user),
):
    if city is None and min_price is None and max_price is None:
        raise HTTPException(status_code=400, detail="Provide 'city', 'min_price' or 'max_price'")

    client_ip = request.client.host
    await _rate_limit_sliding_window(
        f"search:{client_ip}", RATE_LIMIT_SEARCH_MAX, RATE_LIMIT_SEARCH_WINDOW, response
    )

    if city is not None and min_price is None and max_price is None:
        cache_key = f"properties:city:{city.lower()}"
    elif city is None:
        cache_key = f"properties:price:{min_price}:{max_price}"
    else:
        cache_key = None

    if cache_key:
        cached = await redis.get(cache_key)
        if cached:
            return [PropertyPublic(**p) for p in json.loads(cached)]

    conditions = ["status = 'active'"]
    params: list = []
    i = 1
    if city is not None:
        conditions.append(f"city = ${i}"); params.append(city); i += 1
    if min_price is not None:
        conditions.append(f"price >= ${i}"); params.append(min_price); i += 1
    if max_price is not None:
        conditions.append(f"price <= ${i}"); params.append(max_price); i += 1

    query = f"SELECT * FROM properties WHERE {' AND '.join(conditions)} ORDER BY created_at DESC"
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    result = [_row_to_property(r) for r in rows]

    if cache_key:
        payload = json.dumps([p.model_dump(mode="json") for p in result], default=str)
        await redis.setex(cache_key, SEARCH_CACHE_TTL, payload)

    return result


@app.get("/api/v1/properties/user/{user_id}", response_model=List[PropertyPublic])
async def get_user_properties(user_id: int, user: UserPublic = Depends(get_current_user)):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM properties WHERE owner_id = $1 ORDER BY created_at DESC", user_id)
    return [_row_to_property(r) for r in rows]


@app.get("/api/v1/properties/{property_id}", response_model=PropertyPublic)
async def get_property(property_id: int, user: UserPublic = Depends(get_current_user)):
    cache_key = f"properties:id:{property_id}"
    cached = await redis.get(cache_key)
    if cached:
        return PropertyPublic(**json.loads(cached))

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM properties WHERE id = $1", property_id)
    if not row:
        raise HTTPException(status_code=404, detail="Property not found")

    prop = _row_to_property(row)
    await redis.setex(cache_key, PROPERTY_CACHE_TTL, prop.model_dump_json())
    return prop


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
        row = await conn.fetchrow(
            "UPDATE properties SET status = $1 WHERE id = $2 RETURNING *",
            body.status.value, property_id,
        )

    await redis.delete(f"properties:id:{property_id}")
    await _invalidate_search_cache(city=row["city"])
    return _row_to_property(row)


@app.post("/api/v1/viewings", response_model=ViewingPublic, status_code=201)
async def create_viewing(body: ViewingCreate, user: UserPublic = Depends(get_current_user)):
    if user.role not in ("buyer", "admin"):
        raise HTTPException(status_code=403, detail="Only buyers can schedule viewings")
    async with pool.acquire() as conn:
        exists = await conn.fetchrow("SELECT id FROM properties WHERE id = $1", body.property_id)
        if not exists:
            raise HTTPException(status_code=404, detail="Property not found")
        row = await conn.fetchrow(
            "INSERT INTO viewings (property_id, buyer_id, scheduled_at) VALUES ($1,$2,$3) RETURNING *",
            body.property_id, user.id, body.scheduled_at,
        )
    return ViewingPublic(id=row["id"], property_id=row["property_id"], buyer_id=row["buyer_id"],
                         scheduled_at=row["scheduled_at"], created_at=row["created_at"])


@app.get("/api/v1/viewings/property/{property_id}", response_model=List[ViewingPublic])
async def get_property_viewings(property_id: int, user: UserPublic = Depends(get_current_user)):
    async with pool.acquire() as conn:
        prop = await conn.fetchrow("SELECT owner_id FROM properties WHERE id = $1", property_id)
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
        if prop["owner_id"] != user.id and user.role != "admin":
            raise HTTPException(status_code=403, detail="Not authorized")
        rows = await conn.fetch(
            "SELECT * FROM viewings WHERE property_id = $1 ORDER BY scheduled_at", property_id)
    return [ViewingPublic(id=r["id"], property_id=r["property_id"], buyer_id=r["buyer_id"],
                          scheduled_at=r["scheduled_at"], created_at=r["created_at"]) for r in rows]
