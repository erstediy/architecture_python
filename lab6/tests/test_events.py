import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from services.events import (
    Event, property_created, property_status_changed,
    viewing_scheduled, user_created,
)


def _mock_row(data: dict):
    row = MagicMock()
    row.__getitem__ = lambda self, k: data[k]
    row.get = lambda k, d=None: data.get(k, d)
    return row


def test_property_created_event():
    row = _mock_row({
        "id": 1, "owner_id": 42, "title": "Test", "type": "apartment",
        "city": "Москва", "address": "ул. Ленина, 1", "price": 5000000.0,
        "area": 50.0, "rooms": 2, "status": "active",
        "created_at": datetime(2025, 1, 1),
    })
    event = property_created(row)
    assert event.event_type == "property.created"
    assert event.payload["city"] == "Москва"
    assert event.payload["price"] == 5000000.0
    assert "event_id" in event.model_dump()


def test_property_status_changed_event():
    row = _mock_row({"id": 1, "owner_id": 42, "status": "sold"})
    event = property_status_changed(row, "active")
    assert event.event_type == "property.status_changed"
    assert event.payload["old_status"] == "active"
    assert event.payload["new_status"] == "sold"


def test_viewing_scheduled_event():
    row = _mock_row({
        "id": 10, "property_id": 1, "buyer_id": 99,
        "scheduled_at": datetime(2025, 6, 15, 10, 0),
    })
    event = viewing_scheduled(row)
    assert event.event_type == "viewing.scheduled"
    assert event.payload["buyer_id"] == 99


def test_user_created_event():
    row = _mock_row({
        "id": 5, "login": "agent1", "first_name": "Иван",
        "last_name": "Петров", "role": "agent",
    })
    event = user_created(row)
    assert event.event_type == "user.created"
    assert event.payload["login"] == "agent1"
    assert event.payload["role"] == "agent"


def test_event_has_unique_ids():
    row = _mock_row({"id": 5, "login": "u", "first_name": "A", "last_name": "B", "role": "buyer"})
    e1 = user_created(row)
    e2 = user_created(row)
    assert e1.event_id != e2.event_id


def test_event_serializable():
    row = _mock_row({
        "id": 1, "owner_id": 42, "title": "T", "type": "apartment",
        "city": "М", "address": "А", "price": 1.0, "area": 1.0,
        "rooms": None, "status": "active", "created_at": datetime(2025, 1, 1),
    })
    event = property_created(row)
    data = event.model_dump(mode="json")
    assert data["event_type"] == "property.created"
    assert isinstance(data["occurred_at"], str)
