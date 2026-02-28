"""Tests for quiz submission and recommendation scoring."""


class TestQuizSubmit:
    def test_default_params(self, client, sample_whiskeys):
        resp = client.post("/quiz/", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    def test_bourbon_style_preference(self, client, sample_whiskeys):
        resp = client.post("/quiz/", json={
            "style": "bourbon",
            "flavors": ["vanilla", "caramel"],
            "smokiness": "none",
            "body": "medium",
            "budget": "budget",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        # Top result should be a bourbon or have high similarity
        assert data[0]["score"] > 0

    def test_smoky_preference(self, client, sample_whiskeys):
        resp = client.post("/quiz/", json={
            "style": "scotch",
            "flavors": ["smoky", "peaty"],
            "smokiness": "heavy",
            "body": "full",
            "budget": "mid",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    def test_results_include_reason(self, client, sample_whiskeys):
        resp = client.post("/quiz/", json={
            "style": "bourbon",
            "flavors": ["vanilla"],
            "smokiness": "none",
            "budget": "budget",
        })
        data = resp.json()
        for rec in data:
            assert "reason" in rec
            assert len(rec["reason"]) > 0

    def test_top_n_parameter(self, client, sample_whiskeys):
        resp = client.post("/quiz/?top_n=3", json={
            "style": "any",
        })
        assert resp.status_code == 200
        assert len(resp.json()) <= 3

    def test_marks_quiz_completed(self, client, auth_headers, sample_whiskeys):
        resp = client.post("/quiz/", json={
            "style": "bourbon",
        }, headers=auth_headers)
        assert resp.status_code == 200
        me = client.get("/auth/me", headers=auth_headers).json()
        assert me["quiz_completed"] is True
