"""Tests for watchlist & alerts endpoints."""


class TestWatchUnwatch:
    def test_watch_whiskey(self, client, auth_headers, sample_whiskeys):
        wid = sample_whiskeys[0].id
        resp = client.post(f"/watchlist/{wid}", headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["watching"] is True
        assert data["whiskey_id"] == wid

    def test_watch_idempotent(self, client, auth_headers, sample_whiskeys):
        wid = sample_whiskeys[0].id
        client.post(f"/watchlist/{wid}", headers=auth_headers)
        resp = client.post(f"/watchlist/{wid}", headers=auth_headers)
        # Should not error on duplicate
        assert resp.status_code == 201
        assert resp.json()["watching"] is True

    def test_watch_nonexistent_whiskey(self, client, auth_headers):
        resp = client.post("/watchlist/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_watch_unauthenticated(self, client, sample_whiskeys):
        resp = client.post(f"/watchlist/{sample_whiskeys[0].id}")
        assert resp.status_code == 401

    def test_unwatch_whiskey(self, client, auth_headers, sample_whiskeys):
        wid = sample_whiskeys[0].id
        client.post(f"/watchlist/{wid}", headers=auth_headers)
        resp = client.delete(f"/watchlist/{wid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["watching"] is False

    def test_unwatch_not_watched(self, client, auth_headers, sample_whiskeys):
        """Unwatching something you never watched should succeed gracefully."""
        resp = client.delete(f"/watchlist/{sample_whiskeys[0].id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["watching"] is False


class TestWatchStatus:
    def test_status_watched(self, client, auth_headers, sample_whiskeys):
        wid = sample_whiskeys[0].id
        client.post(f"/watchlist/{wid}", headers=auth_headers)
        resp = client.get(f"/watchlist/status/{wid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["watching"] is True

    def test_status_not_watched(self, client, auth_headers, sample_whiskeys):
        resp = client.get(f"/watchlist/status/{sample_whiskeys[0].id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["watching"] is False


class TestMyWatchlist:
    def test_empty_watchlist(self, client, auth_headers):
        resp = client.get("/watchlist/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_watchlist_with_items(self, client, auth_headers, sample_whiskeys):
        client.post(f"/watchlist/{sample_whiskeys[0].id}", headers=auth_headers)
        client.post(f"/watchlist/{sample_whiskeys[1].id}", headers=auth_headers)
        resp = client.get("/watchlist/", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2
        assert "whiskey_id" in items[0]
        assert "whiskey_name" in items[0]
        assert "created_at" in items[0]

    def test_watchlist_unauthenticated(self, client):
        resp = client.get("/watchlist/")
        assert resp.status_code == 401


class TestAlerts:
    def test_alerts_empty(self, client, auth_headers):
        resp = client.get("/watchlist/alerts", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_unread_count_zero(self, client, auth_headers):
        resp = client.get("/watchlist/alerts/unread-count", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_mark_alert_not_found(self, client, auth_headers):
        resp = client.post("/watchlist/alerts/99999/read", headers=auth_headers)
        assert resp.status_code == 404

    def test_mark_all_read(self, client, auth_headers):
        resp = client.post("/watchlist/alerts/read-all", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
