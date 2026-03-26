"""Tests for whiskey personality archetype endpoint."""


class TestPersonality:
    def test_newcomer_with_no_ratings(self, client, auth_headers):
        """Users with <2 interactions get the default archetype."""
        resp = client.get("/personality/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "curious_newcomer"
        assert data["title"] == "The Curious Newcomer"
        assert "stats" in data
        assert data["stats"]["total_rated"] == 0

    def test_personality_with_ratings(self, client, sample_user_with_ratings):
        """User with 3 bourbon/scotch/irish ratings should get an archetype."""
        resp = client.get("/personality/me", headers=sample_user_with_ratings)
        assert resp.status_code == 200
        data = resp.json()
        # Should NOT be newcomer with 3 ratings
        assert "type" in data
        assert "title" in data
        assert "tagline" in data
        assert "description" in data
        assert "emoji" in data
        assert "stats" in data
        assert data["stats"]["total_rated"] == 3

    def test_response_shape(self, client, sample_user_with_ratings):
        resp = client.get("/personality/me", headers=sample_user_with_ratings)
        data = resp.json()
        assert "dominant_trait" in data
        assert "secondary_trait" in data
        assert "top_flavors" in data
        assert "top_categories" in data
        assert isinstance(data["top_flavors"], list)
        assert isinstance(data["top_categories"], list)

    def test_stats_fields(self, client, sample_user_with_ratings):
        resp = client.get("/personality/me", headers=sample_user_with_ratings)
        stats = resp.json()["stats"]
        assert "total_rated" in stats
        assert "total_favorites" in stats
        assert "categories_explored" in stats
        assert stats["categories_explored"] >= 1

    def test_unauthenticated(self, client):
        resp = client.get("/personality/me")
        assert resp.status_code == 401
