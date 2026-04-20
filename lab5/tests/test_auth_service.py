from fastapi.testclient import TestClient
import auth_service.main as m
from auth_service.main import app


def _create_user(c, login="testuser", password="Password1", first_name="Ivan", last_name="Petrov", role="buyer"):
    return c.post("/api/v1/users", json={
        "login": login, "password": password,
        "first_name": first_name, "last_name": last_name, "role": role,
    })


def _get_token(c, login="testuser", password="Password1"):
    resp = c.post("/api/v1/auth/token", data={"username": login, "password": password})
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_user(auth_client):
    resp = _create_user(auth_client)
    assert resp.status_code == 201
    assert resp.json()["login"] == "testuser"


def test_login_success(auth_client):
    _create_user(auth_client)
    resp = auth_client.post("/api/v1/auth/token", data={"username": "testuser", "password": "Password1"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_rate_limit(auth_client):
    _create_user(auth_client)
    for _ in range(10):
        auth_client.post("/api/v1/auth/token", data={"username": "testuser", "password": "wrongpass"})
    resp = auth_client.post("/api/v1/auth/token", data={"username": "testuser", "password": "wrongpass"})
    assert resp.status_code == 429
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Reset" in resp.headers


def test_login_rate_limit_headers(auth_client):
    _create_user(auth_client)
    resp = auth_client.post("/api/v1/auth/token", data={"username": "testuser", "password": "Password1"})
    assert resp.status_code == 200
    assert resp.headers["X-RateLimit-Limit"] == "10"
    assert int(resp.headers["X-RateLimit-Remaining"]) <= 10


def test_me_cached(auth_client):
    _create_user(auth_client)
    token = _get_token(auth_client)
    resp1 = auth_client.get("/api/v1/users/me", headers=_auth(token))
    resp2 = auth_client.get("/api/v1/users/me", headers=_auth(token))
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()


def test_search_by_login(auth_client):
    _create_user(auth_client)
    token = _get_token(auth_client)
    resp = auth_client.get("/api/v1/users?login=testuser", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()[0]["login"] == "testuser"


def test_me_unauthorized(auth_client):
    resp = auth_client.get("/api/v1/users/me")
    assert resp.status_code == 401
