"""Tests for favorites endpoints."""


class TestAddFavorite:
    def test_add_favorite(self, client, auth_headers, sample_whiskeys):
        wid = sample_whiskeys[0].id
        resp = client.post(f"/favorites/{wid}", headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["whiskey_id"] == wid

    def test_add_favorite_idempotent(self, client, auth_headers, sample_whiskeys):
        wid = sample_whiskeys[0].id
        client.post(f"/favorites/{wid}", headers=auth_headers)
        resp = client.post(f"/favorites/{wid}", headers=auth_headers)
        # Should return the existing favorite, not error
        assert resp.status_code in (200, 201)
        assert resp.json()["whiskey_id"] == wid

    def test_add_favorite_not_found(self, client, auth_headers):
        resp = client.post("/favorites/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_add_favorite_unauthenticated(self, client, sample_whiskeys):
        resp = client.post(f"/favorites/{sample_whiskeys[0].id}")
        assert resp.status_code == 401


class TestRemoveFavorite:
    def test_remove_favorite(self, client, auth_headers, sample_whiskeys):
        wid = sample_whiskeys[0].id
        client.post(f"/favorites/{wid}", headers=auth_headers)
        resp = client.delete(f"/favorites/{wid}", headers=auth_headers)
        assert resp.status_code == 204

    def test_remove_non_favorite(self, client, auth_headers, sample_whiskeys):
        wid = sample_whiskeys[0].id
        resp = client.delete(f"/favorites/{wid}", headers=auth_headers)
        assert resp.status_code == 204


class TestGetFavorites:
    def test_get_favorites_list(self, client, auth_headers, sample_whiskeys):
        client.post(f"/favorites/{sample_whiskeys[0].id}", headers=auth_headers)
        client.post(f"/favorites/{sample_whiskeys[1].id}", headers=auth_headers)
        resp = client.get("/favorites/me", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_favorite_ids(self, client, auth_headers, sample_whiskeys):
        client.post(f"/favorites/{sample_whiskeys[0].id}", headers=auth_headers)
        resp = client.get("/favorites/me/ids", headers=auth_headers)
        assert resp.status_code == 200
        assert sample_whiskeys[0].id in resp.json()["ids"]
