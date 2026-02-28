"""Tests for flight theme endpoints."""


class TestListThemes:
    def test_list_all_themes(self, client):
        resp = client.get("/flights/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 7
        slugs = {t["slug"] for t in data}
        assert "beginner" in slugs
        assert "smoky-journey" in slugs
        assert "bourbon-ladder" in slugs
        assert "scotch-regions" in slugs
        assert "world-tour" in slugs

    def test_theme_has_metadata(self, client):
        resp = client.get("/flights/")
        theme = resp.json()[0]
        assert "label" in theme
        assert "emoji" in theme
        assert "tagline" in theme


class TestGetFlight:
    def test_beginner_flight(self, client, sample_whiskeys):
        resp = client.get("/flights/beginner")
        assert resp.status_code == 200
        data = resp.json()
        assert data["theme"] == "beginner"
        assert "bottles" in data
        for bottle in data["bottles"]:
            assert "step" in bottle
            assert "whiskey" in bottle
            assert "lesson" in bottle

    def test_bourbon_ladder(self, client, sample_whiskeys):
        resp = client.get("/flights/bourbon-ladder")
        assert resp.status_code == 200
        data = resp.json()
        assert data["theme"] == "bourbon-ladder"

    def test_world_tour(self, client, sample_whiskeys):
        resp = client.get("/flights/world-tour")
        assert resp.status_code == 200

    def test_invalid_theme(self, client):
        resp = client.get("/flights/nonexistent")
        assert resp.status_code == 404

    def test_max_price_filter(self, client, sample_whiskeys):
        resp = client.get("/flights/beginner", params={"max_price": 30})
        assert resp.status_code == 200

    def test_count_param(self, client, sample_whiskeys):
        resp = client.get("/flights/bourbon-ladder", params={"count": 2})
        if resp.status_code == 200:
            assert len(resp.json()["bottles"]) <= 2
