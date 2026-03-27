"""Tests for the subscription router — premium tier management."""

from unittest.mock import patch


class TestGetStatus:
    def test_free_user(self, client, auth_headers):
        resp = client.get("/subscription/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_premium"] is False
        assert data["tier"] is None

    def test_unauthenticated(self, client):
        resp = client.get("/subscription/status")
        assert resp.status_code == 401


class TestActivatePremium:
    def test_activate_as_admin(self, client, auth_headers):
        with patch("app.routers.subscription._ADMIN_USERS", {"testuser"}):
            resp = client.post("/subscription/activate", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "activated"
        assert "expires_at" in resp.json()

    def test_non_admin(self, client, auth_headers):
        resp = client.post("/subscription/activate", headers=auth_headers)
        assert resp.status_code == 403

    def test_already_premium(self, client, auth_headers):
        with patch("app.routers.subscription._ADMIN_USERS", {"testuser"}):
            client.post("/subscription/activate", headers=auth_headers)
            resp = client.post("/subscription/activate", headers=auth_headers)
        assert resp.status_code == 400

    def test_unauthenticated(self, client):
        resp = client.post("/subscription/activate")
        assert resp.status_code == 401

    def test_creates_subscription_record(self, client, auth_headers):
        with patch("app.routers.subscription._ADMIN_USERS", {"testuser"}):
            client.post("/subscription/activate", headers=auth_headers)
        resp = client.get("/subscription/status", headers=auth_headers)
        data = resp.json()
        assert data["is_premium"] is True
        assert data["tier"] == "premium"
        assert data["expires_at"] is not None


class TestCancelSubscription:
    def test_cancel_active(self, client, auth_headers):
        with patch("app.routers.subscription._ADMIN_USERS", {"testuser"}):
            client.post("/subscription/activate", headers=auth_headers)
        resp = client.post("/subscription/cancel", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "canceled"

    def test_cancel_no_subscription(self, client, auth_headers):
        resp = client.post("/subscription/cancel", headers=auth_headers)
        assert resp.status_code == 400

    def test_cancel_updates_status(self, client, auth_headers):
        with patch("app.routers.subscription._ADMIN_USERS", {"testuser"}):
            client.post("/subscription/activate", headers=auth_headers)
        client.post("/subscription/cancel", headers=auth_headers)
        resp = client.get("/subscription/status", headers=auth_headers)
        assert resp.json()["is_premium"] is False

    def test_unauthenticated(self, client):
        resp = client.post("/subscription/cancel")
        assert resp.status_code == 401


class TestGetFeatures:
    def test_returns_list(self, client):
        resp = client.get("/subscription/features")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    def test_shape(self, client):
        item = client.get("/subscription/features").json()[0]
        assert "feature" in item
        assert "free_tier" in item
        assert "premium_tier" in item
