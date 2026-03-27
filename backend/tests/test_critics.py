"""Tests for the critics router — expert/critic score endpoints."""


class TestGetCriticScores:
    def test_empty(self, client, sample_whiskeys):
        resp = client.get(f"/critics/whiskey/{sample_whiskeys[0].id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scores"] == []
        assert data["avg_critic_score"] is None

    def test_with_data(self, client, auth_headers, sample_whiskeys):
        client.post(
            "/critics/",
            json={
                "whiskey_id": sample_whiskeys[0].id,
                "source": "whisky_advocate",
                "source_display": "Whisky Advocate",
                "score": 90,
                "max_score": 100,
            },
            headers=auth_headers,
        )
        resp = client.get(f"/critics/whiskey/{sample_whiskeys[0].id}")
        data = resp.json()
        assert len(data["scores"]) == 1
        assert data["avg_critic_score"] is not None

    def test_normalized_score(self, client, auth_headers, sample_whiskeys):
        client.post(
            "/critics/",
            json={
                "whiskey_id": sample_whiskeys[0].id,
                "source": "jim_murray",
                "source_display": "Jim Murray",
                "score": 85,
                "max_score": 100,
            },
            headers=auth_headers,
        )
        score = client.get(f"/critics/whiskey/{sample_whiskeys[0].id}").json()["scores"][0]
        assert score["normalized_score"] == 85.0

    def test_whiskey_not_found(self, client):
        resp = client.get("/critics/whiskey/99999")
        assert resp.status_code == 404


class TestAddCriticScore:
    def test_add(self, client, auth_headers, sample_whiskeys):
        resp = client.post(
            "/critics/",
            json={
                "whiskey_id": sample_whiskeys[0].id,
                "source": "whisky_advocate",
                "source_display": "Whisky Advocate",
                "score": 92,
                "max_score": 100,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["source"] == "whisky_advocate"
        assert data["score"] == 92

    def test_duplicate_source(self, client, auth_headers, sample_whiskeys):
        payload = {
            "whiskey_id": sample_whiskeys[0].id,
            "source": "whisky_advocate",
            "source_display": "Whisky Advocate",
            "score": 90,
            "max_score": 100,
        }
        client.post("/critics/", json=payload, headers=auth_headers)
        resp = client.post("/critics/", json=payload, headers=auth_headers)
        assert resp.status_code == 409

    def test_whiskey_not_found(self, client, auth_headers):
        resp = client.post(
            "/critics/",
            json={
                "whiskey_id": 99999,
                "source": "test",
                "source_display": "Test",
                "score": 50,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_unauthenticated(self, client, sample_whiskeys):
        resp = client.post(
            "/critics/",
            json={
                "whiskey_id": sample_whiskeys[0].id,
                "source": "test",
                "source_display": "Test",
                "score": 50,
            },
        )
        assert resp.status_code == 401


class TestListSources:
    def test_list(self, client):
        resp = client.get("/critics/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        assert "key" in data[0]
        assert "name" in data[0]
