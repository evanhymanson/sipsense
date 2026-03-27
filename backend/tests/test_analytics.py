"""Tests for the analytics router — admin dashboard and frontend event tracking."""

from unittest.mock import patch


class TestTrackFrontendEvent:
    def test_page_view(self, client):
        resp = client.post(
            "/analytics/track",
            json={"event": "page_view", "path": "/browse"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_time_on_page(self, client):
        resp = client.post(
            "/analytics/track",
            json={"event": "time_on_page", "path": "/browse", "data": {"seconds": 30}},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_invalid_body(self, client):
        resp = client.post(
            "/analytics/track",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert resp.json()["status"] == "invalid"

    def test_unknown_event(self, client):
        resp = client.post(
            "/analytics/track",
            json={"event": "unknown_event", "path": "/"},
        )
        assert resp.json()["status"] == "ok"


class TestOverview:
    def test_admin(self, client, auth_headers):
        with patch("app.routers.analytics._ADMIN_USERS", {"testuser"}):
            resp = client.get("/analytics/overview", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "dau" in data
        assert "total_users" in data
        assert "total_whiskeys" in data

    def test_non_admin(self, client, auth_headers):
        resp = client.get("/analytics/overview", headers=auth_headers)
        assert resp.status_code == 403

    def test_unauthenticated(self, client):
        resp = client.get("/analytics/overview")
        assert resp.status_code == 401


class TestFunnel:
    def test_admin(self, client, auth_headers):
        with patch("app.routers.analytics._ADMIN_USERS", {"testuser"}):
            resp = client.get("/analytics/funnel", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "registered" in data
        assert "first_rating" in data

    def test_non_admin(self, client, auth_headers):
        resp = client.get("/analytics/funnel", headers=auth_headers)
        assert resp.status_code == 403


class TestTopWhiskeys:
    def test_admin(self, client, auth_headers):
        with patch("app.routers.analytics._ADMIN_USERS", {"testuser"}):
            resp = client.get("/analytics/top-whiskeys", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "most_viewed" in data
        assert "most_rated" in data

    def test_non_admin(self, client, auth_headers):
        resp = client.get("/analytics/top-whiskeys", headers=auth_headers)
        assert resp.status_code == 403


class TestFeatureAdoption:
    def test_admin(self, client, auth_headers):
        with patch("app.routers.analytics._ADMIN_USERS", {"testuser"}):
            resp = client.get("/analytics/feature-adoption", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_non_admin(self, client, auth_headers):
        resp = client.get("/analytics/feature-adoption", headers=auth_headers)
        assert resp.status_code == 403


class TestPerformance:
    def test_admin(self, client, auth_headers):
        with patch("app.routers.analytics._ADMIN_USERS", {"testuser"}):
            resp = client.get("/analytics/performance", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_requests" in data
        assert "p50" in data

    def test_empty(self, client, auth_headers):
        with patch("app.routers.analytics._ADMIN_USERS", {"testuser"}):
            resp = client.get("/analytics/performance", headers=auth_headers)
        data = resp.json()
        assert data["total_requests"] == 0

    def test_non_admin(self, client, auth_headers):
        resp = client.get("/analytics/performance", headers=auth_headers)
        assert resp.status_code == 403
