"""Tests for daily discovery (whiskey of the day) endpoint."""


class TestDailyDiscovery:
    def test_daily_returns_whiskey(self, client, sample_whiskeys):
        resp = client.get("/daily/")
        assert resp.status_code == 200
        data = resp.json()
        assert "date" in data
        assert "weekday" in data
        assert "whiskey" in data
        assert "tasting_tip" in data
        assert "did_you_know" in data
        assert "conversation_starter" in data

    def test_whiskey_structure(self, client, sample_whiskeys):
        resp = client.get("/daily/")
        whiskey = resp.json()["whiskey"]
        assert "id" in whiskey
        assert "name" in whiskey
        assert "distillery" in whiskey
        assert "category" in whiskey
        assert "abv" in whiskey

    def test_flavors_parsed(self, client, sample_whiskeys):
        resp = client.get("/daily/")
        data = resp.json()
        assert "flavors" in data
        assert isinstance(data["flavors"], list)
        assert len(data["flavors"]) > 0

    def test_same_day_consistency(self, client, sample_whiskeys):
        """Two calls on the same day should return the same whiskey."""
        resp1 = client.get("/daily/")
        resp2 = client.get("/daily/")
        assert resp1.json()["whiskey"]["id"] == resp2.json()["whiskey"]["id"]

    def test_tasting_tip_is_string(self, client, sample_whiskeys):
        resp = client.get("/daily/")
        assert isinstance(resp.json()["tasting_tip"], str)
        assert len(resp.json()["tasting_tip"]) > 10

    def test_weekday_message(self, client, sample_whiskeys):
        resp = client.get("/daily/")
        data = resp.json()
        assert "weekday_message" in data
        assert isinstance(data["weekday_message"], str)
