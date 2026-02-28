"""Tests for store locator endpoints (Overpass API mocked)."""

from unittest.mock import patch, MagicMock
from app import models


MOCK_OVERPASS_RESPONSE = {
    "elements": [
        {
            "type": "node",
            "id": 12345,
            "lat": 40.7580,
            "lon": -73.9855,
            "tags": {
                "name": "Times Square Liquors",
                "shop": "alcohol",
                "addr:housenumber": "100",
                "addr:street": "Broadway",
                "addr:city": "New York",
                "phone": "212-555-0100",
            },
        },
        {
            "type": "node",
            "id": 67890,
            "lat": 40.7520,
            "lon": -73.9780,
            "tags": {
                "name": "Midtown Wine & Spirits",
                "shop": "alcohol",
            },
        },
    ],
}


def _mock_overpass_post(*args, **kwargs):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = MOCK_OVERPASS_RESPONSE
    return mock_resp


class TestNearbyStores:
    @patch("app.routers.stores.httpx.Client")
    def test_nearby_stores(self, mock_client_cls, client, db_session):
        mock_client = MagicMock()
        mock_client.post = _mock_overpass_post
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = client.get("/stores/nearby", params={
            "lat": 40.7580,
            "lng": -73.9855,
            "radius": 5000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "Times Square Liquors"
        assert "distance_m" in data[0]

    @patch("app.routers.stores.httpx.Client")
    def test_cached_results(self, mock_client_cls, client, db_session):
        """Second call should use cache, not hit Overpass."""
        mock_client = MagicMock()
        mock_client.post = _mock_overpass_post
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # First call populates cache
        client.get("/stores/nearby", params={"lat": 40.758, "lng": -73.9855, "radius": 5000})
        # Second call should use cache
        resp = client.get("/stores/nearby", params={"lat": 40.758, "lng": -73.9855, "radius": 5000})
        assert resp.status_code == 200
        # Overpass should only be called once (the first request)
        assert mock_client_cls.call_count == 1

    def test_invalid_coordinates(self, client):
        resp = client.get("/stores/nearby", params={"lat": 999, "lng": -73.9855})
        assert resp.status_code == 422


class TestStoreAvailability:
    @patch("app.routers.stores.httpx.Client")
    def test_report_availability(self, mock_client_cls, client, auth_headers, sample_whiskeys, db_session):
        mock_client = MagicMock()
        mock_client.post = _mock_overpass_post
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # First, fetch stores to populate DB
        client.get("/stores/nearby", params={"lat": 40.758, "lng": -73.9855, "radius": 5000})

        resp = client.post("/stores/12345/report", json={
            "whiskey_id": sample_whiskeys[0].id,
            "status": "in_stock",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "in_stock"

    def test_report_nonexistent_store(self, client, auth_headers, sample_whiskeys):
        resp = client.post("/stores/999999/report", json={
            "whiskey_id": sample_whiskeys[0].id,
            "status": "in_stock",
        }, headers=auth_headers)
        assert resp.status_code == 404

    @patch("app.routers.stores.httpx.Client")
    def test_get_store_availability(self, mock_client_cls, client, auth_headers, sample_whiskeys, db_session):
        mock_client = MagicMock()
        mock_client.post = _mock_overpass_post
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        client.get("/stores/nearby", params={"lat": 40.758, "lng": -73.9855, "radius": 5000})
        client.post("/stores/12345/report", json={
            "whiskey_id": sample_whiskeys[0].id,
            "status": "in_stock",
        }, headers=auth_headers)

        resp = client.get("/stores/12345/availability")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestHaversine:
    def test_known_distance(self):
        from app.routers.stores import _haversine
        # NYC (40.7128, -74.0060) to JFK (40.6413, -73.7781) ≈ 19km
        dist = _haversine(40.7128, -74.0060, 40.6413, -73.7781)
        assert 18_000 < dist < 21_000
