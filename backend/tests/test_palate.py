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


class TestPalateMatch:
    def test_match_with_data(self, client, both_users_with_ratings):
        headers1, _ = both_users_with_ratings
        resp = client.get("/palate/match/testuser2", headers=headers1)
        assert resp.status_code == 200
        data = resp.json()
        assert data["match_score"] is not None
        assert 0 <= data["match_score"] <= 100

    def test_match_response_shape(self, client, both_users_with_ratings):
        headers1, _ = both_users_with_ratings
        resp = client.get("/palate/match/testuser2", headers=headers1)
        data = resp.json()
        assert "match_score" in data
        assert "shared_flavors" in data
        assert "agreements" in data
        assert "disagreements" in data
        assert "your_total_rated" in data
        assert "their_total_rated" in data
        assert "message" in data

    def test_match_insufficient_data(self, client, auth_headers, second_auth_headers):
        # testuser2 has no ratings -> insufficient data
        resp = client.get("/palate/match/testuser2", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["match_score"] is None
        assert data["message"] is not None

    def test_match_against_self(self, client, sample_user_with_ratings):
        resp = client.get("/palate/match/testuser", headers=sample_user_with_ratings)
        assert resp.status_code == 400

    def test_match_nonexistent_user(self, client, sample_user_with_ratings):
        resp = client.get("/palate/match/ghostuser", headers=sample_user_with_ratings)
        assert resp.status_code == 404

    def test_match_unauthenticated(self, client):
        resp = client.get("/palate/match/testuser")
        assert resp.status_code == 401

    def test_match_agreements_present(self, client, both_users_with_ratings):
        headers1, _ = both_users_with_ratings
        resp = client.get("/palate/match/testuser2", headers=headers1)
        data = resp.json()
        assert isinstance(data["agreements"], list)

    def test_match_shared_flavors_present(self, client, both_users_with_ratings):
        headers1, _ = both_users_with_ratings
        resp = client.get("/palate/match/testuser2", headers=headers1)
        data = resp.json()
        assert isinstance(data["shared_flavors"], list)
