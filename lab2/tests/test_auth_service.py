import pytest
from fastapi.testclient import TestClient
import auth_service.main as m
from auth_service.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_db():
    m.users_db.clear()
    m._user_id_seq = 0
    yield
    m.users_db.clear()
    m._user_id_seq = 0


def _create_user(login="testuser", password="Password1", first_name="Ivan", last_name="Petrov", role="buyer"):
    return client.post("/api/v1/users", json={
        "login": login, "password": password,
        "first_name": first_name, "last_name": last_name, "role": role,
    })


def _get_token(login="testuser", password="Password1"):
    resp = client.post("/api/v1/auth/token", data={"username": login, "password": password})
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_user():
    resp = _create_user()
    assert resp.status_code == 201
    data = resp.json()
    assert data["login"] == "testuser"
    assert data["role"] == "buyer"
    assert "id" in data


def test_create_user_duplicate_login():
    _create_user()
    resp = _create_user()
    assert resp.status_code == 400


def test_create_user_invalid_login():
    resp = _create_user(login="a")
    assert resp.status_code == 422


def test_create_user_short_password():
    resp = _create_user(password="123")
    assert resp.status_code == 422


def test_login_success():
    _create_user()
    resp = client.post("/api/v1/auth/token", data={"username": "testuser", "password": "Password1"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password():
    _create_user()
    resp = client.post("/api/v1/auth/token", data={"username": "testuser", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_unknown_user():
    resp = client.post("/api/v1/auth/token", data={"username": "ghost", "password": "Password1"})
    assert resp.status_code == 401


def test_search_by_login():
    _create_user()
    token = _get_token()
    resp = client.get("/api/v1/users?login=testuser", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()[0]["login"] == "testuser"


def test_search_by_login_not_found():
    _create_user()
    token = _get_token()
    resp = client.get("/api/v1/users?login=nobody", headers=_auth(token))
    assert resp.status_code == 404


def test_search_by_name_mask():
    _create_user(login="userivan", password="Password1", first_name="Ivan", last_name="Petrov")
    _create_user(login="userpetr", password="Password2", first_name="Petr", last_name="Ivanov")
    token = _get_token(login="userivan", password="Password1")
    resp = client.get("/api/v1/users?name=ivan", headers=_auth(token))
    assert resp.status_code == 200
    logins = {u["login"] for u in resp.json()}
    assert "userivan" in logins
    assert "userpetr" in logins


def test_search_no_params():
    _create_user()
    token = _get_token()
    resp = client.get("/api/v1/users", headers=_auth(token))
    assert resp.status_code == 400


def test_me_endpoint():
    _create_user()
    token = _get_token()
    resp = client.get("/api/v1/users/me", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["login"] == "testuser"


def test_me_unauthorized():
    resp = client.get("/api/v1/users/me")
    assert resp.status_code == 401
