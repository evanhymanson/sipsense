"""Tests for educational content endpoints (categories, distilleries, glossary)."""


class TestCategories:
    def test_list_categories(self, client):
        resp = client.get("/learn/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 6
        slugs = [c["slug"] for c in data]
        assert "bourbon" in slugs
        assert "scotch" in slugs

    def test_get_category(self, client):
        resp = client.get("/learn/categories/bourbon")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Bourbon"
        assert "body" in data
        assert "entry_bottles" in data
        assert "quick_facts" in data

    def test_category_not_found(self, client):
        resp = client.get("/learn/categories/nonexistent")
        assert resp.status_code == 404


class TestDistilleries:
    def test_list_distilleries(self, client):
        resp = client.get("/learn/distilleries")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 5
        slugs = [d["slug"] for d in data]
        assert "buffalo-trace" in slugs

    def test_get_distillery(self, client):
        resp = client.get("/learn/distilleries/buffalo-trace")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Buffalo Trace"
        assert "body" in data

    def test_distillery_not_found(self, client):
        resp = client.get("/learn/distilleries/nonexistent")
        assert resp.status_code == 404


class TestGlossary:
    def test_glossary_sorted(self, client):
        resp = client.get("/learn/glossary")
        assert resp.status_code == 200
        data = resp.json()
        terms = [entry["term"] for entry in data]
        assert terms == sorted(terms)

    def test_glossary_has_definitions(self, client):
        resp = client.get("/learn/glossary")
        data = resp.json()
        for entry in data:
            assert "term" in entry
            assert "definition" in entry
            assert len(entry["definition"]) > 10
