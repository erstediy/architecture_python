from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum
import httpx
import os

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")

app = FastAPI(title="Property Service", version="1.0.0")
security = HTTPBearer()

properties_db: Dict[int, dict] = {}
viewings_db: Dict[int, dict] = {}
_prop_id_seq = 0
_view_id_seq = 0


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


def _next_prop_id() -> int:
    global _prop_id_seq
    _prop_id_seq += 1
    return _prop_id_seq


def _next_view_id() -> int:
    global _view_id_seq
    _view_id_seq += 1
    return _view_id_seq


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        resp = httpx.get(
            f"{AUTH_SERVICE_URL}/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Auth service unavailable")
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return resp.json()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/properties", response_model=PropertyPublic, status_code=201)
async def create_property(body: PropertyCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in ("agent", "admin"):
        raise HTTPException(status_code=403, detail="Only agents and admins can add properties")
    pid = _next_prop_id()
    now = datetime.utcnow()
    properties_db[pid] = {
        **body.model_dump(),
        "id": pid,
        "owner_id": user["id"],
        "status": PropertyStatus.active,
        "created_at": now,
    }
    return properties_db[pid]


@app.get("/api/v1/properties", response_model=List[PropertyPublic])
async def search_properties(
    city: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    user: dict = Depends(get_current_user),
):
    if city is None and min_price is None and max_price is None:
        raise HTTPException(status_code=400, detail="Provide 'city', 'min_price' or 'max_price'")

    result = list(properties_db.values())

    if city is not None:
        result = [p for p in result if p["city"].lower() == city.lower()]
    if min_price is not None:
        result = [p for p in result if p["price"] >= min_price]
    if max_price is not None:
        result = [p for p in result if p["price"] <= max_price]

    return result


@app.get("/api/v1/properties/user/{user_id}", response_model=List[PropertyPublic])
async def get_user_properties(user_id: int, user: dict = Depends(get_current_user)):
    return [p for p in properties_db.values() if p["owner_id"] == user_id]


@app.get("/api/v1/properties/{property_id}", response_model=PropertyPublic)
async def get_property(property_id: int, user: dict = Depends(get_current_user)):
    p = properties_db.get(property_id)
    if not p:
        raise HTTPException(status_code=404, detail="Property not found")
    return p


@app.patch("/api/v1/properties/{property_id}/status", response_model=PropertyPublic)
async def update_property_status(
    property_id: int,
    body: PropertyStatusUpdate,
    user: dict = Depends(get_current_user),
):
    p = properties_db.get(property_id)
    if not p:
        raise HTTPException(status_code=404, detail="Property not found")
    if p["owner_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    p["status"] = body.status
    return p


@app.post("/api/v1/viewings", response_model=ViewingPublic, status_code=201)
async def create_viewing(body: ViewingCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in ("buyer", "admin"):
        raise HTTPException(status_code=403, detail="Only buyers can schedule viewings")
    if body.property_id not in properties_db:
        raise HTTPException(status_code=404, detail="Property not found")
    vid = _next_view_id()
    viewings_db[vid] = {
        "id": vid,
        "property_id": body.property_id,
        "buyer_id": user["id"],
        "scheduled_at": body.scheduled_at,
        "created_at": datetime.utcnow(),
    }
    return viewings_db[vid]


@app.get("/api/v1/viewings/property/{property_id}", response_model=List[ViewingPublic])
async def get_property_viewings(property_id: int, user: dict = Depends(get_current_user)):
    if property_id not in properties_db:
        raise HTTPException(status_code=404, detail="Property not found")
    p = properties_db[property_id]
    if p["owner_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    return [v for v in viewings_db.values() if v["property_id"] == property_id]
