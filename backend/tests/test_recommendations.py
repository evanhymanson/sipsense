"""Tests for recommendation endpoint (content-based filtering)."""


class TestRecommendations:
    def test_cold_start(self, client, auth_headers, sample_whiskeys):
        """User with no ratings gets top-rated whiskeys."""
        resp = client.get("/recommendations/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    def test_with_ratings(self, client, sample_user_with_ratings, sample_whiskeys):
        """User with ratings gets personalized recommendations."""
        resp = client.get("/recommendations/", headers=sample_user_with_ratings)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        for rec in data:
            assert "whiskey" in rec
            assert "score" in rec

    def test_excludes_rated(self, client, auth_headers, sample_whiskeys):
        """Recommended whiskeys should not include already-rated ones."""
        wid = sample_whiskeys[0].id
        client.post(f"/whiskeys/{wid}/rate", json={"score": 5.0}, headers=auth_headers)
        resp = client.get("/recommendations/", headers=auth_headers)
        rec_ids = {r["whiskey"]["id"] for r in resp.json()}
        assert wid not in rec_ids

    def test_top_n_param(self, client, auth_headers, sample_whiskeys):
        resp = client.get("/recommendations/", params={"top_n": 2}, headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) <= 2

    def test_unauthenticated(self, client):
        resp = client.get("/recommendations/")
        assert resp.status_code == 401
