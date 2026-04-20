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

AGENT = {"id": 999, "login": "agent1", "first_name": "A", "last_name": "B", "role": "agent"}
BUYER = {"id": 998, "login": "buyer1", "first_name": "C", "last_name": "D", "role": "buyer"}


def override(user: dict):
    async def _dep():
        from property_service.main import UserPublic
        return UserPublic(**user)
    app.dependency_overrides[get_current_user] = _dep


def test_create_property(prop_client_with_override):
    override(AGENT)
    resp = prop_client_with_override.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    assert resp.status_code == 201
    assert resp.json()["city"] == "Москва"


def test_search_cached(prop_client_with_override):
    override(AGENT)
    prop_client_with_override.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    override(BUYER)
    resp1 = prop_client_with_override.get("/api/v1/properties?city=Москва", headers=AUTH_HEADER)
    resp2 = prop_client_with_override.get("/api/v1/properties?city=Москва", headers=AUTH_HEADER)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()


def test_cache_invalidated_on_create(prop_client_with_override):
    override(AGENT)
    prop_client_with_override.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    override(BUYER)
    resp1 = prop_client_with_override.get("/api/v1/properties?city=Москва", headers=AUTH_HEADER)
    assert len(resp1.json()) == 1

    override(AGENT)
    prop_client_with_override.post("/api/v1/properties", json={**PROP_PAYLOAD, "title": "Вторая"}, headers=AUTH_HEADER)

    override(BUYER)
    resp2 = prop_client_with_override.get("/api/v1/properties?city=Москва", headers=AUTH_HEADER)
    assert len(resp2.json()) == 2


def test_cache_invalidated_on_status_change(prop_client_with_override):
    override(AGENT)
    r = prop_client_with_override.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    pid = r.json()["id"]

    override(BUYER)
    resp1 = prop_client_with_override.get("/api/v1/properties?city=Москва", headers=AUTH_HEADER)
    assert len(resp1.json()) == 1

    override(AGENT)
    prop_client_with_override.patch(f"/api/v1/properties/{pid}/status", json={"status": "sold"}, headers=AUTH_HEADER)

    override(BUYER)
    resp2 = prop_client_with_override.get("/api/v1/properties?city=Москва", headers=AUTH_HEADER)
    assert len(resp2.json()) == 0


def test_search_rate_limit(prop_client_with_override):
    override(BUYER)
    prop_m.RATE_LIMIT_SEARCH_MAX = 3
    for _ in range(3):
        prop_client_with_override.get("/api/v1/properties?city=Тест", headers=AUTH_HEADER)
    resp = prop_client_with_override.get("/api/v1/properties?city=Тест", headers=AUTH_HEADER)
    assert resp.status_code == 429
    assert "X-RateLimit-Limit" in resp.headers
    prop_m.RATE_LIMIT_SEARCH_MAX = 100


def test_search_rate_limit_headers(prop_client_with_override):
    override(BUYER)
    resp = prop_client_with_override.get("/api/v1/properties?city=Москва", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Reset" in resp.headers


def test_property_cached(prop_client_with_override):
    override(AGENT)
    r = prop_client_with_override.post("/api/v1/properties", json=PROP_PAYLOAD, headers=AUTH_HEADER)
    pid = r.json()["id"]
    override(BUYER)
    resp1 = prop_client_with_override.get(f"/api/v1/properties/{pid}", headers=AUTH_HEADER)
    resp2 = prop_client_with_override.get(f"/api/v1/properties/{pid}", headers=AUTH_HEADER)
    assert resp1.status_code == 200
    assert resp1.json() == resp2.json()


def test_search_no_params(prop_client_with_override):
    override(BUYER)
    resp = prop_client_with_override.get("/api/v1/properties", headers=AUTH_HEADER)
    assert resp.status_code == 400
