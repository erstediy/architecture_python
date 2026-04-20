from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime
from uuid import uuid4


class Event(BaseModel):
    event_type: str
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    payload: Any


def property_created(row) -> Event:
    return Event(event_type="property.created", payload={
        "id": row["id"], "owner_id": row["owner_id"], "title": row["title"],
        "type": row["type"], "city": row["city"], "address": row["address"],
        "price": float(row["price"]), "area": float(row["area"]),
        "rooms": row["rooms"], "status": row["status"],
        "created_at": row["created_at"].isoformat(),
    })


def property_status_changed(row, old_status: str) -> Event:
    return Event(event_type="property.status_changed", payload={
        "id": row["id"], "owner_id": row["owner_id"],
        "old_status": old_status, "new_status": row["status"],
    })


def viewing_scheduled(row) -> Event:
    return Event(event_type="viewing.scheduled", payload={
        "id": row["id"], "property_id": row["property_id"],
        "buyer_id": row["buyer_id"],
        "scheduled_at": row["scheduled_at"].isoformat(),
    })


def user_created(row) -> Event:
    return Event(event_type="user.created", payload={
        "id": row["id"], "login": row["login"],
        "first_name": row["first_name"], "last_name": row["last_name"],
        "role": row["role"],
    })
