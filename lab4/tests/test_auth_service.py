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
    data = resp.json()
    assert data["login"] == "testuser"
    assert data["role"] == "buyer"
    assert "id" in data


def test_create_user_duplicate_login(auth_client):
    _create_user(auth_client)
    resp = _create_user(auth_client)
    assert resp.status_code == 400


def test_create_user_invalid_login(auth_client):
    resp = _create_user(auth_client, login="a")
    assert resp.status_code == 422


def test_create_user_short_password(auth_client):
    resp = _create_user(auth_client, password="123")
    assert resp.status_code == 422


def test_login_success(auth_client):
    _create_user(auth_client)
    resp = auth_client.post("/api/v1/auth/token", data={"username": "testuser", "password": "Password1"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(auth_client):
    _create_user(auth_client)
    resp = auth_client.post("/api/v1/auth/token", data={"username": "testuser", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_unknown_user(auth_client):
    resp = auth_client.post("/api/v1/auth/token", data={"username": "ghost", "password": "Password1"})
    assert resp.status_code == 401


def test_search_by_login(auth_client):
    _create_user(auth_client)
    token = _get_token(auth_client)
    resp = auth_client.get("/api/v1/users?login=testuser", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()[0]["login"] == "testuser"


def test_search_by_login_not_found(auth_client):
    _create_user(auth_client)
    token = _get_token(auth_client)
    resp = auth_client.get("/api/v1/users?login=nobody", headers=_auth(token))
    assert resp.status_code == 404


def test_search_by_name_mask(auth_client):
    _create_user(auth_client, login="userivan", first_name="Ivan", last_name="Petrov")
    _create_user(auth_client, login="userpetr", password="Password2", first_name="Petr", last_name="Ivanov")
    token = _get_token(auth_client, login="userivan")
    resp = auth_client.get("/api/v1/users?name=ivan", headers=_auth(token))
    assert resp.status_code == 200
    logins = {u["login"] for u in resp.json()}
    assert "userivan" in logins
    assert "userpetr" in logins


def test_search_no_params(auth_client):
    _create_user(auth_client)
    token = _get_token(auth_client)
    resp = auth_client.get("/api/v1/users", headers=_auth(token))
    assert resp.status_code == 400


def test_me_endpoint(auth_client):
    _create_user(auth_client)
    token = _get_token(auth_client)
    resp = auth_client.get("/api/v1/users/me", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["login"] == "testuser"


def test_me_unauthorized(auth_client):
    resp = auth_client.get("/api/v1/users/me")
    assert resp.status_code == 401
