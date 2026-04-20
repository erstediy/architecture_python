from fastapi import FastAPI, HTTPException, Depends, status, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timedelta
from enum import Enum
import jwt
import bcrypt
import os
import json
import time
import asyncpg
import redis.asyncio as aioredis

SECRET_KEY = os.getenv("SECRET_KEY", "changeme-32-char-secret-key-here!")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
DB_DSN = os.getenv("DB_DSN", "postgresql://postgres:postgres@postgres:5432/real_estate")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

RATE_LIMIT_LOGIN_MAX = 10
RATE_LIMIT_LOGIN_WINDOW = 60

USER_CACHE_TTL = 30

app = FastAPI(title="Auth Service", version="1.0.0")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

pool: Optional[asyncpg.Pool] = None
redis: Optional[aioredis.Redis] = None


class Role(str, Enum):
    admin = "admin"
    buyer = "buyer"
    agent = "agent"


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


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _make_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _row_to_public(row) -> UserPublic:
    return UserPublic(id=row["id"], login=row["login"],
                      first_name=row["first_name"], last_name=row["last_name"], role=row["role"])


async def _rate_limit_fixed_window(key: str, limit: int, window: int, response: Response):
    now = int(time.time())
    bucket = now // window
    redis_key = f"rl:{key}:{bucket}"

    count = await redis.incr(redis_key)
    if count == 1:
        await redis.expire(redis_key, window)

    reset_at = (bucket + 1) * window
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
                "Retry-After": str(reset_at - now),
            },
        )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserPublic:
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except Exception:
        raise exc

    cache_key = f"users:me:{user_id}"
    cached = await redis.get(cache_key)
    if cached:
        return UserPublic(**json.loads(cached))

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, login, first_name, last_name, role FROM users WHERE id = $1", user_id)
    if not row:
        raise exc

    user = _row_to_public(row)
    await redis.setex(cache_key, USER_CACHE_TTL, user.model_dump_json())
    return user


@app.post("/api/v1/auth/token", response_model=Token)
async def login(request: Request, response: Response, form: OAuth2PasswordRequestForm = Depends()):
    client_ip = request.client.host
    await _rate_limit_fixed_window(f"login:{client_ip}", RATE_LIMIT_LOGIN_MAX, RATE_LIMIT_LOGIN_WINDOW, response)

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, password_hash FROM users WHERE login = $1", form.username)
    if not row or not _verify(form.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect login or password")
    return Token(access_token=_make_token(row["id"]))


@app.post("/api/v1/users", response_model=UserPublic, status_code=201)
async def create_user(body: UserCreate):
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM users WHERE login = $1", body.login)
        if existing:
            raise HTTPException(status_code=400, detail="Login already taken")
        row = await conn.fetchrow(
            "INSERT INTO users (login, password_hash, first_name, last_name, role) VALUES ($1,$2,$3,$4,$5) RETURNING id, login, first_name, last_name, role",
            body.login, _hash(body.password), body.first_name, body.last_name, body.role.value,
        )
    return _row_to_public(row)


@app.get("/api/v1/users", response_model=List[UserPublic])
async def search_users(
    login: Optional[str] = None,
    name: Optional[str] = None,
    _: UserPublic = Depends(get_current_user),
):
    async with pool.acquire() as conn:
        if login is not None:
            row = await conn.fetchrow(
                "SELECT id, login, first_name, last_name, role FROM users WHERE login = $1", login)
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            return [_row_to_public(row)]
        if name is not None:
            rows = await conn.fetch(
                "SELECT id, login, first_name, last_name, role FROM users WHERE first_name ILIKE $1 OR last_name ILIKE $1",
                f"%{name}%",
            )
            return [_row_to_public(r) for r in rows]
    raise HTTPException(status_code=400, detail="Provide 'login' or 'name' query parameter")


@app.get("/api/v1/users/me", response_model=UserPublic)
async def me(current: UserPublic = Depends(get_current_user)):
    return current
