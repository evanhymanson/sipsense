"""Tests for the sharecard router — branded PNG share card generation."""

import pytest

PIL = pytest.importorskip("PIL", reason="Pillow not installed — skipping share card tests")


class TestRatingShareCard:
    def test_returns_png(self, client, testuser_rating_id):
        resp = client.get(f"/share/rating/{testuser_rating_id}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"

    def test_not_found(self, client):
        resp = client.get("/share/rating/99999")
        assert resp.status_code == 404

    def test_content_disposition(self, client, testuser_rating_id):
        resp = client.get(f"/share/rating/{testuser_rating_id}")
        assert "content-disposition" in resp.headers


class TestWhiskeyShareCard:
    def test_returns_png(self, client, sample_whiskeys):
        resp = client.get(f"/share/whiskey/{sample_whiskeys[0].id}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"

    def test_not_found(self, client):
        resp = client.get("/share/whiskey/99999")
        assert resp.status_code == 404


class TestPalateDNACard:
    def test_returns_png(self, client, sample_user_with_ratings):
        resp = client.get("/share/palate/testuser")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"

    def test_user_not_found(self, client):
        resp = client.get("/share/palate/nonexistent")
        assert resp.status_code == 404

    def test_no_ratings(self, client, auth_headers):
        resp = client.get("/share/palate/testuser")
        assert resp.status_code == 404
