from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from enum import Enum
import jwt
import bcrypt
import re
import os

SECRET_KEY = os.getenv("SECRET_KEY", "changeme-32-char-secret-key-here!")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI(title="Auth Service", version="1.0.0")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

users_db: Dict[int, dict] = {}
_user_id_seq = 0


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


def _next_id() -> int:
    global _user_id_seq
    _user_id_seq += 1
    return _user_id_seq


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _make_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except Exception:
        raise exc
    user = users_db.get(user_id)
    if not user:
        raise exc
    return user


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/auth/token", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = next((u for u in users_db.values() if u["login"] == form.username), None)
    if not user or not _verify(form.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect login or password")
    return Token(access_token=_make_token(user["id"]))


@app.post("/api/v1/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate):
    if any(u["login"] == body.login for u in users_db.values()):
        raise HTTPException(status_code=400, detail="Login already taken")
    uid = _next_id()
    users_db[uid] = {
        "id": uid,
        "login": body.login,
        "password_hash": _hash(body.password),
        "first_name": body.first_name,
        "last_name": body.last_name,
        "role": body.role,
    }
    return _to_public(users_db[uid])


@app.get("/api/v1/users", response_model=List[UserPublic])
def search_users(
    login: Optional[str] = None,
    name: Optional[str] = None,
    _: dict = Depends(get_current_user),
):
    if login is not None:
        user = next((u for u in users_db.values() if u["login"] == login), None)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return [_to_public(user)]

    if name is not None:
        pattern = re.compile(re.escape(name), re.IGNORECASE)
        result = [
            _to_public(u) for u in users_db.values()
            if pattern.search(u["first_name"]) or pattern.search(u["last_name"])
        ]
        return result

    raise HTTPException(status_code=400, detail="Provide 'login' or 'name' query parameter")


@app.get("/api/v1/users/me", response_model=UserPublic)
def me(current: dict = Depends(get_current_user)):
    return _to_public(current)


def _to_public(u: dict) -> UserPublic:
    return UserPublic(id=u["id"], login=u["login"], first_name=u["first_name"], last_name=u["last_name"], role=u["role"])
