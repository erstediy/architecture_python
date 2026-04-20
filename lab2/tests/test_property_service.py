import pytest
from fastapi.testclient import TestClient
import property_service.main as m
from property_service.main import app, get_current_user

client = TestClient(app)

AGENT = {"id": 1, "login": "agent1", "first_name": "A", "last_name": "B", "role": "agent"}
BUYER = {"id": 2, "login": "buyer1", "first_name": "C", "last_name": "D", "role": "buyer"}
ADMIN = {"id": 3, "login": "admin1", "first_name": "E", "last_name": "F", "role": "admin"}

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


@pytest.fixture(autouse=True)
def clear_db():
    m.properties_db.clear()
    m.viewings_db.clear()
    m._prop_id_seq = 0
    m._view_id_seq = 0
    app.dependency_overrides.clear()
    yield
    m.properties_db.clear()
    m.viewings_db.clear()
    m._prop_id_seq = 0
    m._view_id_seq = 0
    app.dependency_overrides.clear()


def override(user):
    async def _override():
        return user
    app.dependency_overrides[get_current_user] = _override


def test_create_property_as_agent():
    override(AGENT)
    resp = client.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    assert resp.status_code == 201
    data = resp.json()
    assert data["city"] == "Москва"
    assert data["owner_id"] == AGENT["id"]
    assert data["status"] == "active"


def test_create_property_as_buyer_forbidden():
    override(BUYER)
    resp = client.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    assert resp.status_code == 403


def test_search_by_city():
    override(AGENT)
    client.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    client.post("/api/v1/properties", json={**PROP_PAYLOAD, "city": "Питер"}, headers=AUTH_HEADER)
    override(BUYER)
    resp = client.get("/api/v1/properties?city=Москва", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["city"] == "Москва"


def test_search_by_price():
    override(AGENT)
    client.post("/api/v1/properties", json={**PROP_PAYLOAD, "price": 3000000}, headers=AUTH_HEADER)
    client.post("/api/v1/properties", json={**PROP_PAYLOAD, "price": 8000000}, headers=AUTH_HEADER)
    override(BUYER)
    resp = client.get("/api/v1/properties?max_price=5000000", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert all(p["price"] <= 5000000 for p in resp.json())


def test_search_no_params():
    override(BUYER)
    resp = client.get("/api/v1/properties", headers=AUTH_HEADER)
    assert resp.status_code == 400


def test_get_user_properties():
    override(AGENT)
    client.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    override(BUYER)
    resp = client.get(f"/api/v1/properties/user/{AGENT['id']}", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_update_property_status():
    override(AGENT)
    r = client.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    pid = r.json()["id"]
    resp = client.patch(f"/api/v1/properties/{pid}/status", json={"status": "sold"}, headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert resp.json()["status"] == "sold"


def test_update_status_not_owner():
    override(AGENT)
    r = client.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    pid = r.json()["id"]
    override(BUYER)
    resp = client.patch(f"/api/v1/properties/{pid}/status", json={"status": "sold"}, headers=AUTH_HEADER)
    assert resp.status_code == 403


def test_update_status_not_found():
    override(AGENT)
    resp = client.patch("/api/v1/properties/999/status", json={"status": "sold"}, headers=AUTH_HEADER)
    assert resp.status_code == 404


def test_create_viewing():
    override(AGENT)
    r = client.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    pid = r.json()["id"]
    override(BUYER)
    resp = client.post("/api/v1/viewings", json={"property_id": pid, "scheduled_at": "2025-06-01T10:00:00"}, headers=AUTH_HEADER)
    assert resp.status_code == 201
    assert resp.json()["buyer_id"] == BUYER["id"]


def test_create_viewing_agent_forbidden():
    override(AGENT)
    r = client.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    pid = r.json()["id"]
    resp = client.post("/api/v1/viewings", json={"property_id": pid, "scheduled_at": "2025-06-01T10:00:00"}, headers=AUTH_HEADER)
    assert resp.status_code == 403


def test_create_viewing_property_not_found():
    override(BUYER)
    resp = client.post("/api/v1/viewings", json={"property_id": 999, "scheduled_at": "2025-06-01T10:00:00"}, headers=AUTH_HEADER)
    assert resp.status_code == 404


def test_get_property_viewings_as_owner():
    override(AGENT)
    r = client.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    pid = r.json()["id"]
    override(BUYER)
    client.post("/api/v1/viewings", json={"property_id": pid, "scheduled_at": "2025-06-01T10:00:00"}, headers=AUTH_HEADER)
    override(AGENT)
    resp = client.get(f"/api/v1/viewings/property/{pid}", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_property_viewings_forbidden():
    override(AGENT)
    r = client.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    pid = r.json()["id"]
    override(BUYER)
    resp = client.get(f"/api/v1/viewings/property/{pid}", headers=AUTH_HEADER)
    assert resp.status_code == 403
