"""Tests for discover (knowledge graph) endpoint."""


class TestDiscoverGraph:
    def test_graph_returns_nodes_and_links(self, client):
        resp = client.get("/discover/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "links" in data
        assert len(data["nodes"]) > 0
        assert len(data["links"]) > 0

    def test_node_types(self, client):
        resp = client.get("/discover/graph")
        nodes = resp.json()["nodes"]
        types = {n["type"] for n in nodes}
        assert "category" in types
        assert "flavor" in types
        assert "region" in types
        assert "distillery" in types
        assert "activity" in types

    def test_category_nodes_have_required_fields(self, client):
        resp = client.get("/discover/graph")
        cat_nodes = [n for n in resp.json()["nodes"] if n["type"] == "category"]
        assert len(cat_nodes) >= 5  # bourbon, scotch, irish, japanese, rye at minimum
        for node in cat_nodes:
            assert "id" in node
            assert "label" in node
            assert "emoji" in node
            assert "slug" in node

    def test_flavor_nodes(self, client):
        resp = client.get("/discover/graph")
        flavor_nodes = [n for n in resp.json()["nodes"] if n["type"] == "flavor"]
        labels = {n["label"] for n in flavor_nodes}
        assert "Smoky" in labels
        assert "Sweet" in labels
        assert "Fruity" in labels

    def test_links_reference_existing_nodes(self, client):
        resp = client.get("/discover/graph")
        data = resp.json()
        node_ids = {n["id"] for n in data["nodes"]}
        for link in data["links"]:
            assert link["source"] in node_ids, f"Link source {link['source']} not in nodes"
            assert link["target"] in node_ids, f"Link target {link['target']} not in nodes"

    def test_region_nodes(self, client):
        resp = client.get("/discover/graph")
        region_nodes = [n for n in resp.json()["nodes"] if n["type"] == "region"]
        labels = {n["label"] for n in region_nodes}
        assert "Kentucky" in labels
        assert "Islay" in labels
        assert "Japan" in labels
