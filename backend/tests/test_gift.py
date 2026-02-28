"""Tests for gift finder endpoint."""


class TestGiftFinder:
    def test_default_params(self, client, sample_whiskeys):
        resp = client.post("/gift/", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert "picks" in data

    def test_newbie_gets_sweet(self, client, sample_whiskeys):
        resp = client.post("/gift/", json={
            "drinker_level": "newbie",
            "budget": "budget",
        })
        assert resp.status_code == 200
        data = resp.json()
        if data["picks"]:
            # Newbie filter prefers vanilla/honey/caramel/sweet
            profiles = [p.get("flavor_profile", "") or "" for p in data["picks"]]
            has_sweet = any(
                any(t in fp.lower() for t in ["vanilla", "honey", "caramel", "sweet"])
                for fp in profiles
            )
            assert has_sweet

    def test_connoisseur_high_rated(self, client, sample_whiskeys):
        resp = client.post("/gift/", json={
            "drinker_level": "connoisseur",
            "budget": "premium",
        })
        assert resp.status_code == 200

    def test_style_filter(self, client, sample_whiskeys):
        resp = client.post("/gift/", json={
            "style": "bourbon",
            "budget": "budget",
        })
        data = resp.json()
        for pick in data.get("picks", []):
            assert pick["category"] == "bourbon"

    def test_budget_tiers(self, client, sample_whiskeys):
        for tier in ["budget", "mid", "premium", "luxury"]:
            resp = client.post("/gift/", json={"budget": tier})
            assert resp.status_code == 200
