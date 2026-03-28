"""Tests for the userlists router — user-created whiskey lists."""


class TestCreateList:
    def test_create_list(self, client, auth_headers):
        resp = client.post(
            "/userlists/",
            json={"title": "My Favorites"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My Favorites"
        assert "slug" in data
        assert data["item_count"] == 0

    def test_create_with_whiskeys(self, client, auth_headers, sample_whiskeys):
        ids = [sample_whiskeys[0].id, sample_whiskeys[1].id]
        resp = client.post(
            "/userlists/",
            json={"title": "Top Picks", "whiskey_ids": ids},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["item_count"] == 2

    def test_create_invalid_whiskey_ids_skipped(self, client, auth_headers):
        resp = client.post(
            "/userlists/",
            json={"title": "Bad IDs", "whiskey_ids": [99999]},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["item_count"] == 0

    def test_create_unauthenticated(self, client):
        resp = client.post("/userlists/", json={"title": "Nope"})
        assert resp.status_code == 401


class TestBrowseLists:
    def test_browse_empty(self, client):
        resp = client.get("/userlists/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_browse_public_only(self, client, auth_headers, sample_whiskeys):
        client.post(
            "/userlists/",
            json={"title": "Public", "is_public": True},
            headers=auth_headers,
        )
        client.post(
            "/userlists/",
            json={"title": "Private", "is_public": False},
            headers=auth_headers,
        )
        resp = client.get("/userlists/")
        titles = [l["title"] for l in resp.json()]
        assert "Public" in titles
        assert "Private" not in titles


class TestGetUserLists:
    def test_own_lists_include_private(self, client, auth_headers):
        client.post(
            "/userlists/",
            json={"title": "Private List", "is_public": False},
            headers=auth_headers,
        )
        resp = client.get("/userlists/user/testuser", headers=auth_headers)
        assert len(resp.json()) == 1

    def test_other_user_public_only(self, client, auth_headers, second_auth_headers):
        client.post(
            "/userlists/",
            json={"title": "Secret", "is_public": False},
            headers=auth_headers,
        )
        resp = client.get("/userlists/user/testuser", headers=second_auth_headers)
        assert len(resp.json()) == 0


class TestGetListDetail:
    def test_get_detail(self, client, auth_headers, sample_whiskeys):
        create = client.post(
            "/userlists/",
            json={"title": "Detail List", "whiskey_ids": [sample_whiskeys[0].id]},
            headers=auth_headers,
        )
        slug = create.json()["slug"]
        resp = client.get(f"/userlists/{slug}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Detail List"
        assert len(data["items"]) == 1

    def test_not_found(self, client):
        resp = client.get("/userlists/nonexistent-slug")
        assert resp.status_code == 404

    def test_private_list_owner(self, client, auth_headers):
        create = client.post(
            "/userlists/",
            json={"title": "My Secret", "is_public": False},
            headers=auth_headers,
        )
        slug = create.json()["slug"]
        resp = client.get(f"/userlists/{slug}", headers=auth_headers)
        assert resp.status_code == 200

    def test_private_list_other_user(self, client, auth_headers, second_auth_headers):
        create = client.post(
            "/userlists/",
            json={"title": "Hidden", "is_public": False},
            headers=auth_headers,
        )
        slug = create.json()["slug"]
        resp = client.get(f"/userlists/{slug}", headers=second_auth_headers)
        assert resp.status_code == 404


class TestUpdateList:
    def test_update_title(self, client, auth_headers):
        create = client.post(
            "/userlists/",
            json={"title": "Original"},
            headers=auth_headers,
        )
        slug = create.json()["slug"]
        resp = client.patch(
            f"/userlists/{slug}",
            json={"title": "Updated"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"

    def test_update_not_owner(self, client, auth_headers, second_auth_headers):
        create = client.post(
            "/userlists/",
            json={"title": "Mine"},
            headers=auth_headers,
        )
        slug = create.json()["slug"]
        resp = client.patch(
            f"/userlists/{slug}",
            json={"title": "Stolen"},
            headers=second_auth_headers,
        )
        assert resp.status_code == 404


class TestDeleteList:
    def test_delete(self, client, auth_headers):
        create = client.post(
            "/userlists/",
            json={"title": "To Delete"},
            headers=auth_headers,
        )
        slug = create.json()["slug"]
        resp = client.delete(f"/userlists/{slug}", headers=auth_headers)
        assert resp.status_code == 204

    def test_delete_not_owner(self, client, auth_headers, second_auth_headers):
        create = client.post(
            "/userlists/",
            json={"title": "Protected"},
            headers=auth_headers,
        )
        slug = create.json()["slug"]
        resp = client.delete(f"/userlists/{slug}", headers=second_auth_headers)
        assert resp.status_code == 404


class TestAddItem:
    def test_add_item(self, client, auth_headers, sample_whiskeys):
        create = client.post(
            "/userlists/",
            json={"title": "Add Test"},
            headers=auth_headers,
        )
        slug = create.json()["slug"]
        resp = client.post(
            f"/userlists/{slug}/items",
            json={"whiskey_id": sample_whiskeys[0].id},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["position"] == 0

    def test_add_duplicate(self, client, auth_headers, sample_whiskeys):
        create = client.post(
            "/userlists/",
            json={"title": "Dup Test"},
            headers=auth_headers,
        )
        slug = create.json()["slug"]
        client.post(
            f"/userlists/{slug}/items",
            json={"whiskey_id": sample_whiskeys[0].id},
            headers=auth_headers,
        )
        resp = client.post(
            f"/userlists/{slug}/items",
            json={"whiskey_id": sample_whiskeys[0].id},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    def test_add_nonexistent_whiskey(self, client, auth_headers):
        create = client.post(
            "/userlists/",
            json={"title": "Bad Whiskey"},
            headers=auth_headers,
        )
        slug = create.json()["slug"]
        resp = client.post(
            f"/userlists/{slug}/items",
            json={"whiskey_id": 99999},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_add_increments_position(self, client, auth_headers, sample_whiskeys):
        create = client.post(
            "/userlists/",
            json={"title": "Position Test"},
            headers=auth_headers,
        )
        slug = create.json()["slug"]
        r1 = client.post(
            f"/userlists/{slug}/items",
            json={"whiskey_id": sample_whiskeys[0].id},
            headers=auth_headers,
        )
        r2 = client.post(
            f"/userlists/{slug}/items",
            json={"whiskey_id": sample_whiskeys[1].id},
            headers=auth_headers,
        )
        assert r2.json()["position"] > r1.json()["position"]


class TestRemoveItem:
    def test_remove(self, client, auth_headers, sample_whiskeys):
        create = client.post(
            "/userlists/",
            json={"title": "Remove Test", "whiskey_ids": [sample_whiskeys[0].id]},
            headers=auth_headers,
        )
        slug = create.json()["slug"]
        resp = client.delete(
            f"/userlists/{slug}/items/{sample_whiskeys[0].id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    def test_remove_nonexistent(self, client, auth_headers):
        create = client.post(
            "/userlists/",
            json={"title": "Empty"},
            headers=auth_headers,
        )
        slug = create.json()["slug"]
        resp = client.delete(f"/userlists/{slug}/items/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestReorderItems:
    def test_reorder(self, client, auth_headers, sample_whiskeys):
        ids = [sample_whiskeys[0].id, sample_whiskeys[1].id, sample_whiskeys[2].id]
        create = client.post(
            "/userlists/",
            json={"title": "Reorder Test", "whiskey_ids": ids},
            headers=auth_headers,
        )
        slug = create.json()["slug"]
        # Reverse the order
        resp = client.put(
            f"/userlists/{slug}/reorder",
            json={"whiskey_ids": list(reversed(ids))},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_reorder_not_owner(self, client, auth_headers, second_auth_headers, sample_whiskeys):
        create = client.post(
            "/userlists/",
            json={"title": "Not Yours"},
            headers=auth_headers,
        )
        slug = create.json()["slug"]
        resp = client.put(
            f"/userlists/{slug}/reorder",
            json={"whiskey_ids": []},
            headers=second_auth_headers,
        )
        assert resp.status_code == 404
