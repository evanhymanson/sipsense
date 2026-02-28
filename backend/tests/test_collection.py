"""Tests for collection (My Shelf) endpoints."""


class TestAddToCollection:
    def test_add_to_collection(self, client, auth_headers, sample_whiskeys):
        resp = client.post("/collection/", json={
            "whiskey_id": sample_whiskeys[0].id,
            "status": "sealed",
            "purchase_price": 28.0,
            "purchase_location": "Local store",
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["status"] == "added"

    def test_add_nonexistent_whiskey(self, client, auth_headers):
        resp = client.post("/collection/", json={
            "whiskey_id": 99999,
        }, headers=auth_headers)
        assert resp.status_code == 404

    def test_add_unauthenticated(self, client, sample_whiskeys):
        resp = client.post("/collection/", json={
            "whiskey_id": sample_whiskeys[0].id,
        })
        assert resp.status_code == 401


class TestGetCollection:
    def test_get_collection(self, client, auth_headers, sample_whiskeys):
        client.post("/collection/", json={
            "whiskey_id": sample_whiskeys[0].id,
            "status": "sealed",
        }, headers=auth_headers)
        client.post("/collection/", json={
            "whiskey_id": sample_whiskeys[1].id,
            "status": "opened",
        }, headers=auth_headers)
        resp = client.get("/collection/", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_collection_filter_status(self, client, auth_headers, sample_whiskeys):
        client.post("/collection/", json={
            "whiskey_id": sample_whiskeys[0].id,
            "status": "sealed",
        }, headers=auth_headers)
        client.post("/collection/", json={
            "whiskey_id": sample_whiskeys[1].id,
            "status": "opened",
        }, headers=auth_headers)
        resp = client.get("/collection/", params={"status": "sealed"}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "sealed"

    def test_collection_includes_whiskey_data(self, client, auth_headers, sample_whiskeys):
        client.post("/collection/", json={
            "whiskey_id": sample_whiskeys[0].id,
        }, headers=auth_headers)
        resp = client.get("/collection/", headers=auth_headers)
        item = resp.json()[0]
        assert item["whiskey"] is not None
        assert item["whiskey"]["name"] == "Buffalo Trace"


class TestUpdateCollectionItem:
    def test_update_status(self, client, auth_headers, sample_whiskeys):
        add_resp = client.post("/collection/", json={
            "whiskey_id": sample_whiskeys[0].id,
            "status": "sealed",
        }, headers=auth_headers)
        item_id = add_resp.json()["id"]
        resp = client.patch(f"/collection/{item_id}", json={
            "status": "opened",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "opened"

    def test_update_not_owned(self, client, auth_headers, second_auth_headers, sample_whiskeys):
        add_resp = client.post("/collection/", json={
            "whiskey_id": sample_whiskeys[0].id,
        }, headers=auth_headers)
        item_id = add_resp.json()["id"]
        resp = client.patch(f"/collection/{item_id}", json={
            "status": "opened",
        }, headers=second_auth_headers)
        assert resp.status_code == 404


class TestDeleteCollectionItem:
    def test_delete(self, client, auth_headers, sample_whiskeys):
        add_resp = client.post("/collection/", json={
            "whiskey_id": sample_whiskeys[0].id,
        }, headers=auth_headers)
        item_id = add_resp.json()["id"]
        resp = client.delete(f"/collection/{item_id}", headers=auth_headers)
        assert resp.status_code == 204


class TestCollectionStats:
    def test_stats(self, client, auth_headers, sample_whiskeys):
        client.post("/collection/", json={
            "whiskey_id": sample_whiskeys[0].id,
            "status": "sealed",
            "purchase_price": 28.0,
        }, headers=auth_headers)
        client.post("/collection/", json={
            "whiskey_id": sample_whiskeys[1].id,
            "status": "opened",
            "purchase_price": 55.0,
        }, headers=auth_headers)
        resp = client.get("/collection/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["sealed"] == 1
        assert data["opened"] == 1
        assert data["total_spent"] == 83.0

    def test_stats_empty(self, client, auth_headers):
        resp = client.get("/collection/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["total_spent"] == 0
