"""Tests for trending and new arrivals endpoints."""


class TestTrending:
    def test_trending_fallback_to_top_rated(self, client, sample_whiskeys):
        """Without recent activity, should fall back to top-rated."""
        resp = client.get("/trending/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    def test_trending_with_activity(self, client, auth_headers, sample_whiskeys):
        """Rate some whiskeys, they should appear in trending."""
        client.post(
            f"/whiskeys/{sample_whiskeys[0].id}/rate",
            json={"score": 5.0},
            headers=auth_headers,
        )
        resp = client.get("/trending/")
        assert resp.status_code == 200
        assert len(resp.json()) > 0

    def test_trending_category_filter(self, client, sample_whiskeys):
        resp = client.get("/trending/", params={"category": "bourbon"})
        assert resp.status_code == 200
        data = resp.json()
        for w in data:
            assert "bourbon" in w["category"].lower()

    def test_trending_limit(self, client, sample_whiskeys):
        resp = client.get("/trending/", params={"limit": 3})
        assert resp.status_code == 200
        assert len(resp.json()) <= 3


class TestNewArrivals:
    def test_new_arrivals(self, client, sample_whiskeys):
        resp = client.get("/trending/new-arrivals")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        # Should be ordered by id descending (newest first)
        ids = [w["id"] for w in data]
        assert ids == sorted(ids, reverse=True)
