from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import httpx
import os
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017")
DB_NAME = os.getenv("DB_NAME", "real_estate")

app = FastAPI(title="Property Service", version="1.0.0")
security = HTTPBearer()

client: Optional[AsyncIOMotorClient] = None
db = None


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
    tags: List[str] = Field(default_factory=list)


class PropertyPublic(PropertyCreate):
    id: str
    owner_id: str
    status: PropertyStatus
    created_at: datetime


class PropertyStatusUpdate(BaseModel):
    status: PropertyStatus


class ViewingCreate(BaseModel):
    property_id: str
    scheduled_at: datetime


class ViewingPublic(BaseModel):
    property_id: str
    buyer_id: str
    buyer_login: str
    scheduled_at: datetime
    created_at: datetime


class UserPublic(BaseModel):
    id: str
    login: str
    first_name: str
    last_name: str
    role: str


@app.on_event("startup")
async def startup():
    global client, db
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    await db.properties.create_index("owner_id")
    await db.properties.create_index("city")
    await db.properties.create_index("price")
    await db.properties.create_index([("city", 1), ("price", 1)])


@app.on_event("shutdown")
async def shutdown():
    client.close()


@app.get("/health")
async def health():
    return {"status": "ok"}


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserPublic:
    token = credentials.credentials
    try:
        async with httpx.AsyncClient() as c:
            resp = await c.get(f"{AUTH_SERVICE_URL}/api/v1/users/me",
                               headers={"Authorization": f"Bearer {token}"}, timeout=5)
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Auth service unavailable")
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return UserPublic(**resp.json())


def _doc_to_property(doc) -> PropertyPublic:
    return PropertyPublic(
        id=str(doc["_id"]), owner_id=str(doc["owner_id"]),
        title=doc["title"], type=doc["type"], city=doc["city"],
        address=doc["address"], price=float(doc["price"]), area=float(doc["area"]),
        rooms=doc.get("rooms"), description=doc.get("description"),
        tags=doc.get("tags", []), status=doc["status"], created_at=doc["created_at"],
    )


@app.post("/api/v1/properties", response_model=PropertyPublic, status_code=201)
async def create_property(body: PropertyCreate, user: UserPublic = Depends(get_current_user)):
    if user.role not in ("agent", "admin"):
        raise HTTPException(status_code=403, detail="Only agents and admins can add properties")
    doc = {
        "owner_id": ObjectId(user.id),
        "title": body.title, "type": body.type.value,
        "city": body.city, "address": body.address,
        "price": body.price, "area": body.area,
        "rooms": body.rooms, "description": body.description,
        "tags": body.tags, "status": "active",
        "viewings": [], "created_at": datetime.utcnow(),
    }
    result = await db.properties.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_property(doc)


@app.get("/api/v1/properties", response_model=List[PropertyPublic])
async def search_properties(
    city: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    user: UserPublic = Depends(get_current_user),
):
    if city is None and min_price is None and max_price is None:
        raise HTTPException(status_code=400, detail="Provide 'city', 'min_price' or 'max_price'")

    query: dict = {"status": "active"}
    if city:
        query["city"] = city
    price_filter = {}
    if min_price is not None:
        price_filter["$gte"] = min_price
    if max_price is not None:
        price_filter["$lte"] = max_price
    if price_filter:
        query["price"] = price_filter

    cursor = db.properties.find(query).sort("created_at", -1)
    return [_doc_to_property(d) async for d in cursor]


@app.get("/api/v1/properties/user/{user_id}", response_model=List[PropertyPublic])
async def get_user_properties(user_id: str, user: UserPublic = Depends(get_current_user)):
    cursor = db.properties.find({"owner_id": ObjectId(user_id)}).sort("created_at", -1)
    return [_doc_to_property(d) async for d in cursor]


@app.get("/api/v1/properties/{property_id}", response_model=PropertyPublic)
async def get_property(property_id: str, user: UserPublic = Depends(get_current_user)):
    doc = await db.properties.find_one({"_id": ObjectId(property_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Property not found")
    return _doc_to_property(doc)


@app.patch("/api/v1/properties/{property_id}/status", response_model=PropertyPublic)
async def update_property_status(
    property_id: str, body: PropertyStatusUpdate, user: UserPublic = Depends(get_current_user)
):
    doc = await db.properties.find_one({"_id": ObjectId(property_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Property not found")
    if str(doc["owner_id"]) != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    await db.properties.update_one({"_id": ObjectId(property_id)}, {"$set": {"status": body.status.value}})
    doc["status"] = body.status.value
    return _doc_to_property(doc)


@app.post("/api/v1/viewings", response_model=ViewingPublic, status_code=201)
async def create_viewing(body: ViewingCreate, user: UserPublic = Depends(get_current_user)):
    if user.role not in ("buyer", "admin"):
        raise HTTPException(status_code=403, detail="Only buyers can schedule viewings")
    doc = await db.properties.find_one({"_id": ObjectId(body.property_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Property not found")
    viewing = {
        "buyer_id": ObjectId(user.id),
        "buyer_login": user.login,
        "scheduled_at": body.scheduled_at,
        "created_at": datetime.utcnow(),
    }
    await db.properties.update_one({"_id": ObjectId(body.property_id)}, {"$push": {"viewings": viewing}})
    return ViewingPublic(
        property_id=body.property_id, buyer_id=user.id, buyer_login=user.login,
        scheduled_at=body.scheduled_at, created_at=viewing["created_at"],
    )


@app.get("/api/v1/viewings/property/{property_id}", response_model=List[ViewingPublic])
async def get_property_viewings(property_id: str, user: UserPublic = Depends(get_current_user)):
    doc = await db.properties.find_one({"_id": ObjectId(property_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Property not found")
    if str(doc["owner_id"]) != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    return [
        ViewingPublic(
            property_id=property_id, buyer_id=str(v["buyer_id"]),
            buyer_login=v["buyer_login"], scheduled_at=v["scheduled_at"],
            created_at=v["created_at"],
        )
        for v in doc.get("viewings", [])
    ]
