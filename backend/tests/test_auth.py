"""Tests for auth endpoints: register, login, /me."""


class TestRegister:
    def test_register_success(self, client):
        resp = client.post("/auth/register", json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "secret123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "newuser"
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_username(self, client):
        client.post("/auth/register", json={
            "username": "dupeuser",
            "email": "a@example.com",
            "password": "secret123",
        })
        resp = client.post("/auth/register", json={
            "username": "dupeuser",
            "email": "b@example.com",
            "password": "secret123",
        })
        assert resp.status_code == 409
        assert "Username already taken" in resp.json()["detail"]

    def test_register_duplicate_email(self, client):
        client.post("/auth/register", json={
            "username": "emailuser1",
            "email": "same@example.com",
            "password": "secret123",
        })
        resp = client.post("/auth/register", json={
            "username": "emailuser2",
            "email": "same@example.com",
            "password": "secret123",
        })
        assert resp.status_code == 409
        assert "Email already registered" in resp.json()["detail"]

    def test_register_invalid_username(self, client):
        resp = client.post("/auth/register", json={
            "username": "bad user!",
            "email": "x@example.com",
            "password": "secret123",
        })
        assert resp.status_code == 422

    def test_register_short_password(self, client):
        resp = client.post("/auth/register", json={
            "username": "shortpw",
            "email": "pw@example.com",
            "password": "abc",
        })
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, client):
        client.post("/auth/register", json={
            "username": "loginuser",
            "email": "login@example.com",
            "password": "mypassword",
        })
        resp = client.post("/auth/login", json={
            "username": "loginuser",
            "password": "mypassword",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["username"] == "loginuser"

    def test_login_wrong_password(self, client):
        client.post("/auth/register", json={
            "username": "wrongpw",
            "email": "wp@example.com",
            "password": "correct",
        })
        resp = client.post("/auth/login", json={
            "username": "wrongpw",
            "password": "wrong",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/auth/login", json={
            "username": "ghost",
            "password": "whatever",
        })
        assert resp.status_code == 401


class TestMe:
    def test_me_with_valid_token(self, client, auth_headers):
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["is_active"] is True

    def test_me_no_token(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client):
        resp = client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401
