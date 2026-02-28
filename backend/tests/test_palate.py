"""Tests for palate profile endpoint."""


class TestPalateProfile:
    def test_with_ratings(self, client, sample_user_with_ratings, sample_whiskeys):
        resp = client.get("/palate/me", headers=sample_user_with_ratings)
        assert resp.status_code == 200
        data = resp.json()
        assert "narrative" in data
        assert "stats" in data
        assert data["stats"]["total_rated"] >= 1
        assert data["stats"]["avg_score"] > 0
        assert "top_categories" in data
        assert "top_flavors" in data
        assert "recent_ratings" in data

    def test_empty_profile(self, client, auth_headers):
        resp = client.get("/palate/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["stats"]["total_rated"] == 0
        assert "Rate some whiskeys" in data["narrative"]

    def test_unauthenticated(self, client):
        resp = client.get("/palate/me")
        assert resp.status_code == 401

    def test_narrative_changes_with_activity(self, client, auth_headers, sample_whiskeys):
        # Rate a whiskey
        client.post(
            f"/whiskeys/{sample_whiskeys[0].id}/rate",
            json={"score": 4.5},
            headers=auth_headers,
        )
        resp = client.get("/palate/me", headers=auth_headers)
        data = resp.json()
        assert data["stats"]["total_rated"] == 1
        assert "just getting started" in data["narrative"].lower()

    def test_favorites_included(self, client, auth_headers, sample_whiskeys):
        client.post(f"/favorites/{sample_whiskeys[0].id}", headers=auth_headers)
        resp = client.get("/palate/me", headers=auth_headers)
        data = resp.json()
        assert "favorites" in data
