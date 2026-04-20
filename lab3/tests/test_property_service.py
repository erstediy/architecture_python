import pytest
import property_service.main as prop_m
from property_service.main import app, get_current_user

PROP_PAYLOAD = {
    "title": "Уютная квартира",
    "type": "apartment",
    "city": "Москва",
    "address": "ул. Ленина, 1",
    "price": 5000000.0,
    "area": 52.5,
    "rooms": 2,
}

AUTH_HEADER = {"Authorization": "Bearer faketoken"}



def override(user: dict):
    async def _dep():
        from property_service.main import UserPublic
        return UserPublic(**user)
    app.dependency_overrides[get_current_user] = _dep


AGENT = {"id": 999, "login": "agent1", "first_name": "A", "last_name": "B", "role": "agent"}
BUYER = {"id": 998, "login": "buyer1", "first_name": "C", "last_name": "D", "role": "buyer"}


def test_create_property_as_agent(prop_client_with_override):
    override(AGENT)
    resp = prop_client_with_override.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    assert resp.status_code == 201
    assert resp.json()["city"] == "Москва"
    assert resp.json()["status"] == "active"


def test_create_property_as_buyer_forbidden(prop_client_with_override):
    override(BUYER)
    resp = prop_client_with_override.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    assert resp.status_code == 403


def test_search_by_city(prop_client_with_override):
    override(AGENT)
    prop_client_with_override.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    prop_client_with_override.post("/api/v1/properties", json={**PROP_PAYLOAD, "city": "Питер"}, headers=AUTH_HEADER)
    override(BUYER)
    resp = prop_client_with_override.get("/api/v1/properties?city=Москва", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["city"] == "Москва"


def test_search_by_price(prop_client_with_override):
    override(AGENT)
    prop_client_with_override.post("/api/v1/properties", json={**PROP_PAYLOAD, "price": 3000000}, headers=AUTH_HEADER)
    prop_client_with_override.post("/api/v1/properties", json={**PROP_PAYLOAD, "price": 8000000}, headers=AUTH_HEADER)
    override(BUYER)
    resp = prop_client_with_override.get("/api/v1/properties?max_price=5000000", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert all(p["price"] <= 5000000 for p in resp.json())


def test_search_no_params(prop_client_with_override):
    override(BUYER)
    resp = prop_client_with_override.get("/api/v1/properties", headers=AUTH_HEADER)
    assert resp.status_code == 400


def test_update_property_status(prop_client_with_override):
    override(AGENT)
    r = prop_client_with_override.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    pid = r.json()["id"]
    resp = prop_client_with_override.patch(f"/api/v1/properties/{pid}/status", json={"status": "sold"}, headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert resp.json()["status"] == "sold"


def test_update_status_not_owner(prop_client_with_override):
    override(AGENT)
    r = prop_client_with_override.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    pid = r.json()["id"]
    override(BUYER)
    resp = prop_client_with_override.patch(f"/api/v1/properties/{pid}/status", json={"status": "sold"}, headers=AUTH_HEADER)
    assert resp.status_code == 403


def test_update_status_not_found(prop_client_with_override):
    override(AGENT)
    resp = prop_client_with_override.patch("/api/v1/properties/99999/status", json={"status": "sold"}, headers=AUTH_HEADER)
    assert resp.status_code == 404


def test_create_viewing(prop_client_with_override):
    override(AGENT)
    r = prop_client_with_override.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    pid = r.json()["id"]
    override(BUYER)
    resp = prop_client_with_override.post("/api/v1/viewings", json={"property_id": pid, "scheduled_at": "2025-06-01T10:00:00"}, headers=AUTH_HEADER)
    assert resp.status_code == 201
    assert resp.json()["buyer_id"] == BUYER["id"]


def test_create_viewing_agent_forbidden(prop_client_with_override):
    override(AGENT)
    r = prop_client_with_override.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    pid = r.json()["id"]
    resp = prop_client_with_override.post("/api/v1/viewings", json={"property_id": pid, "scheduled_at": "2025-06-01T10:00:00"}, headers=AUTH_HEADER)
    assert resp.status_code == 403


def test_create_viewing_not_found(prop_client_with_override):
    override(BUYER)
    resp = prop_client_with_override.post("/api/v1/viewings", json={"property_id": 99999, "scheduled_at": "2025-06-01T10:00:00"}, headers=AUTH_HEADER)
    assert resp.status_code == 404


def test_get_viewings_as_owner(prop_client_with_override):
    override(AGENT)
    r = prop_client_with_override.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    pid = r.json()["id"]
    override(BUYER)
    prop_client_with_override.post("/api/v1/viewings", json={"property_id": pid, "scheduled_at": "2025-06-01T10:00:00"}, headers=AUTH_HEADER)
    override(AGENT)
    resp = prop_client_with_override.get(f"/api/v1/viewings/property/{pid}", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_viewings_forbidden(prop_client_with_override):
    override(AGENT)
    r = prop_client_with_override.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    pid = r.json()["id"]
    override(BUYER)
    resp = prop_client_with_override.get(f"/api/v1/viewings/property/{pid}", headers=AUTH_HEADER)
    assert resp.status_code == 403
