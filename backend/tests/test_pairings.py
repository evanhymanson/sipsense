"""Tests for food pairings and cocktail suggestion endpoints."""


class TestPairings:
    def test_bourbon_pairings(self, client, sample_whiskeys):
        bourbon = next(w for w in sample_whiskeys if w.category == "bourbon")
        resp = client.get(f"/pairings/{bourbon.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["whiskey_name"] == "Buffalo Trace"
        assert len(data["food_pairings"]) > 0
        assert len(data["cocktails"]) > 0
        food_items = [p["item"] for p in data["food_pairings"]]
        assert "Smoked BBQ Brisket" in food_items
        cocktail_names = [c["name"] for c in data["cocktails"]]
        assert "Old Fashioned" in cocktail_names

    def test_scotch_pairings(self, client, sample_whiskeys):
        scotch = next(w for w in sample_whiskeys if w.category == "scotch")
        resp = client.get(f"/pairings/{scotch.id}")
        assert resp.status_code == 200
        data = resp.json()
        food_items = [p["item"] for p in data["food_pairings"]]
        assert "Smoked Salmon" in food_items

    def test_smoky_flavor_bonus(self, client, sample_whiskeys):
        scotch = next(w for w in sample_whiskeys if w.category == "scotch")
        resp = client.get(f"/pairings/{scotch.id}")
        data = resp.json()
        food_items = [p["item"] for p in data["food_pairings"]]
        assert "Grilled Steak" in food_items

    def test_not_found(self, client):
        resp = client.get("/pairings/99999")
        assert resp.status_code == 404
