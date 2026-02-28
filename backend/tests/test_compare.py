"""Tests for bottle comparison endpoint."""


class TestCompare:
    def test_compare_two_whiskeys(self, client, sample_whiskeys):
        a, b = sample_whiskeys[0], sample_whiskeys[1]
        resp = client.get("/compare/", params={"id_a": a.id, "id_b": b.id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["a"]["name"] == "Buffalo Trace"
        assert data["b"]["name"] == "Laphroaig 10"
        assert "flavor_profile" in data["a"]
        assert "flavor_profile" in data["b"]

    def test_one_not_found(self, client, sample_whiskeys):
        resp = client.get("/compare/", params={"id_a": sample_whiskeys[0].id, "id_b": 99999})
        assert resp.status_code == 404

    def test_missing_params(self, client):
        resp = client.get("/compare/")
        assert resp.status_code == 422
