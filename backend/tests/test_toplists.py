"""Tests for the toplists router — curated and dynamic whiskey rankings."""


class TestListTopLists:
    def test_list_empty(self, client):
        resp = client.get("/toplists/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_active(self, client, sample_top_list_curated):
        resp = client.get("/toplists/")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["slug"] == "best-bourbons"
        assert data[0]["list_type"] == "curated"

    def test_list_response_shape(self, client, sample_top_list_curated):
        item = client.get("/toplists/").json()[0]
        assert "id" in item
        assert "slug" in item
        assert "title" in item
        assert "list_type" in item
        assert "item_count" in item

    def test_list_ordered_by_display_order(self, client, sample_top_list_curated, sample_top_list_dynamic):
        data = client.get("/toplists/").json()
        assert len(data) == 2
        assert data[0]["slug"] == "best-bourbons"  # display_order=1
        assert data[1]["slug"] == "top-rated"  # display_order=2


class TestGetTopListCurated:
    def test_get_by_slug(self, client, sample_top_list_curated):
        resp = client.get("/toplists/best-bourbons")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "best-bourbons"
        assert len(data["items"]) == 3

    def test_items_ranked(self, client, sample_top_list_curated):
        items = client.get("/toplists/best-bourbons").json()["items"]
        ranks = [i["rank"] for i in items]
        assert ranks == [1, 2, 3]

    def test_item_shape(self, client, sample_top_list_curated):
        item = client.get("/toplists/best-bourbons").json()["items"][0]
        assert "rank" in item
        assert "whiskey" in item
        assert "name" in item["whiskey"]
        assert "note" in item


class TestGetTopListDynamic:
    def test_dynamic_computes(self, client, sample_top_list_dynamic):
        resp = client.get("/toplists/top-rated")
        assert resp.status_code == 200
        # Dynamic list computes items from whiskey DB based on filters

    def test_dynamic_items_ranked(self, client, sample_top_list_dynamic):
        items = client.get("/toplists/top-rated").json()["items"]
        if items:
            ranks = [i["rank"] for i in items]
            assert ranks == list(range(1, len(ranks) + 1))


class TestTopListNotFound:
    def test_nonexistent(self, client):
        resp = client.get("/toplists/nonexistent")
        assert resp.status_code == 404
