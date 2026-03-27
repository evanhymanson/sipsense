"""Tests for the affiliate router — buy-link click tracking."""


class TestRecordClick:
    def test_authenticated(self, client, auth_headers, sample_whiskeys):
        resp = client.post(
            "/affiliate/click",
            json={
                "whiskey_id": sample_whiskeys[0].id,
                "retailer": "total_wine",
                "source": "detail",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "recorded"

    def test_anonymous(self, client, sample_whiskeys):
        resp = client.post(
            "/affiliate/click",
            json={
                "whiskey_id": sample_whiskeys[0].id,
                "retailer": "drizly",
                "source": "browse",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "recorded"

    def test_whiskey_not_found(self, client):
        resp = client.post(
            "/affiliate/click",
            json={"whiskey_id": 99999, "retailer": "test", "source": "detail"},
        )
        assert resp.status_code == 404


class TestGetStats:
    def test_empty(self, client, auth_headers):
        resp = client.get("/affiliate/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_clicks"] == 0

    def test_after_clicks(self, client, auth_headers, sample_whiskeys):
        client.post(
            "/affiliate/click",
            json={"whiskey_id": sample_whiskeys[0].id, "retailer": "total_wine", "source": "detail"},
            headers=auth_headers,
        )
        client.post(
            "/affiliate/click",
            json={"whiskey_id": sample_whiskeys[1].id, "retailer": "drizly", "source": "browse"},
            headers=auth_headers,
        )
        resp = client.get("/affiliate/stats", headers=auth_headers)
        data = resp.json()
        assert data["total_clicks"] == 2

    def test_by_retailer(self, client, auth_headers, sample_whiskeys):
        client.post(
            "/affiliate/click",
            json={"whiskey_id": sample_whiskeys[0].id, "retailer": "total_wine", "source": "detail"},
            headers=auth_headers,
        )
        resp = client.get("/affiliate/stats", headers=auth_headers)
        assert "total_wine" in resp.json()["clicks_by_retailer"]

    def test_unauthenticated(self, client):
        resp = client.get("/affiliate/stats")
        assert resp.status_code == 401

    def test_scoped_to_user(self, client, auth_headers, second_auth_headers, sample_whiskeys):
        # testuser clicks
        client.post(
            "/affiliate/click",
            json={"whiskey_id": sample_whiskeys[0].id, "retailer": "test", "source": "detail"},
            headers=auth_headers,
        )
        # testuser2 should not see testuser's clicks
        resp = client.get("/affiliate/stats", headers=second_auth_headers)
        assert resp.json()["total_clicks"] == 0


class TestPendingFollowups:
    def test_no_clicks(self, client, auth_headers):
        resp = client.get("/affiliate/pending-followups", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["followups"] == []

    def test_with_unrated_click(self, client, auth_headers, sample_whiskeys):
        client.post(
            "/affiliate/click",
            json={"whiskey_id": sample_whiskeys[0].id, "retailer": "test", "source": "detail"},
            headers=auth_headers,
        )
        resp = client.get("/affiliate/pending-followups", headers=auth_headers)
        followups = resp.json()["followups"]
        assert len(followups) == 1
        assert followups[0]["id"] == sample_whiskeys[0].id
