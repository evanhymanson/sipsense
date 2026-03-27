"""Tests for the sponsored router — paid placement serving and tracking."""


class TestGetPlacements:
    def test_empty(self, client, sample_whiskeys):
        resp = client.get("/sponsored/browse")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_data(self, client, sample_sponsored_placement):
        resp = client.get("/sponsored/feed")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["advertiser_name"] == "Test Distillery"

    def test_response_shape(self, client, sample_sponsored_placement):
        item = client.get("/sponsored/feed").json()[0]
        assert "id" in item
        assert "advertiser_name" in item
        assert "whiskey_id" in item
        assert "placement_type" in item
        assert "whiskey" in item

    def test_filters_by_type(self, client, sample_sponsored_placement):
        # Placement is type="feed", so "browse" should return empty
        resp = client.get("/sponsored/browse")
        assert resp.json() == []

    def test_limit_param(self, client, sample_sponsored_placement):
        resp = client.get("/sponsored/feed?limit=1")
        assert resp.status_code == 200
        assert len(resp.json()) <= 1


class TestRecordImpression:
    def test_record(self, client, auth_headers, sample_sponsored_placement):
        resp = client.post(
            f"/sponsored/{sample_sponsored_placement.id}/impression",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "recorded"

    def test_not_found(self, client, auth_headers):
        resp = client.post("/sponsored/99999/impression", headers=auth_headers)
        assert resp.status_code == 404

    def test_unauthenticated(self, client, sample_sponsored_placement):
        resp = client.post(f"/sponsored/{sample_sponsored_placement.id}/impression")
        assert resp.status_code == 401


class TestRecordClick:
    def test_record(self, client, auth_headers, sample_sponsored_placement):
        resp = client.post(
            f"/sponsored/{sample_sponsored_placement.id}/click",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "recorded"

    def test_not_found(self, client, auth_headers):
        resp = client.post("/sponsored/99999/click", headers=auth_headers)
        assert resp.status_code == 404

    def test_unauthenticated(self, client, sample_sponsored_placement):
        resp = client.post(f"/sponsored/{sample_sponsored_placement.id}/click")
        assert resp.status_code == 401
