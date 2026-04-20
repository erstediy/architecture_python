from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timedelta
from enum import Enum
import jwt
import bcrypt
import os
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

SECRET_KEY = os.getenv("SECRET_KEY", "changeme-32-char-secret-key-here!")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017")
DB_NAME = os.getenv("DB_NAME", "real_estate")

app = FastAPI(title="Auth Service", version="1.0.0")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

client: Optional[AsyncIOMotorClient] = None
db = None


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
    id: str
    login: str
    first_name: str
    last_name: str
    role: Role


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


@app.on_event("startup")
async def startup():
    global client, db
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    await db.users.create_index("login", unique=True)


@app.on_event("shutdown")
async def shutdown():
    client.close()


@app.get("/health")
async def health():
    return {"status": "ok"}


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _make_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _doc_to_public(doc) -> UserPublic:
    return UserPublic(id=str(doc["_id"]), login=doc["login"],
                      first_name=doc["first_name"], last_name=doc["last_name"], role=doc["role"])


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserPublic:
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload["sub"]
    except Exception:
        raise exc
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise exc
    return _doc_to_public(doc)


@app.post("/api/v1/auth/token", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    doc = await db.users.find_one({"login": form.username})
    if not doc or not _verify(form.password, doc["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect login or password")
    return Token(access_token=_make_token(str(doc["_id"])))


@app.post("/api/v1/users", response_model=UserPublic, status_code=201)
async def create_user(body: UserCreate):
    if await db.users.find_one({"login": body.login}):
        raise HTTPException(status_code=400, detail="Login already taken")
    doc = {
        "login": body.login,
        "password_hash": _hash(body.password),
        "first_name": body.first_name,
        "last_name": body.last_name,
        "role": body.role.value,
        "created_at": datetime.utcnow(),
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_public(doc)


@app.get("/api/v1/users", response_model=List[UserPublic])
async def search_users(
    login: Optional[str] = None,
    name: Optional[str] = None,
    _: UserPublic = Depends(get_current_user),
):
    if login is not None:
        doc = await db.users.find_one({"login": login})
        if not doc:
            raise HTTPException(status_code=404, detail="User not found")
        return [_doc_to_public(doc)]

    if name is not None:
        cursor = db.users.find({
            "$or": [
                {"first_name": {"$regex": name, "$options": "i"}},
                {"last_name": {"$regex": name, "$options": "i"}},
            ]
        })
        return [_doc_to_public(d) async for d in cursor]

    raise HTTPException(status_code=400, detail="Provide 'login' or 'name' query parameter")


@app.get("/api/v1/users/me", response_model=UserPublic)
async def me(current: UserPublic = Depends(get_current_user)):
    return current
