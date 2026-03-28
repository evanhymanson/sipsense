"""Tests for the journeys router — guided tasting paths."""


class TestListJourneys:
    def test_list_empty(self, client):
        resp = client.get("/journeys/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_data(self, client, sample_journey):
        resp = client.get("/journeys/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["slug"] == "bourbon-basics"
        assert data[0]["bottle_count"] == 3
        assert data[0]["user_progress"] is None

    def test_list_unauthenticated(self, client, sample_journey):
        resp = client.get("/journeys/")
        assert resp.status_code == 200

    def test_list_with_progress(self, client, auth_headers, sample_journey):
        client.post("/journeys/bourbon-basics/start", headers=auth_headers)
        resp = client.get("/journeys/", headers=auth_headers)
        data = resp.json()
        assert data[0]["user_progress"] is not None
        assert data[0]["user_progress"]["current_step"] == 1


class TestGetJourney:
    def test_get_by_slug(self, client, sample_journey):
        resp = client.get("/journeys/bourbon-basics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "bourbon-basics"
        assert len(data["steps"]) == 3

    def test_steps_sorted(self, client, sample_journey):
        resp = client.get("/journeys/bourbon-basics")
        steps = resp.json()["steps"]
        assert [s["step_number"] for s in steps] == [1, 2, 3]

    def test_steps_include_whiskey(self, client, sample_journey):
        resp = client.get("/journeys/bourbon-basics")
        step = resp.json()["steps"][0]
        assert step["whiskey"] is not None
        assert "name" in step["whiskey"]

    def test_not_found(self, client):
        resp = client.get("/journeys/nonexistent")
        assert resp.status_code == 404


class TestMyJourneys:
    def test_empty(self, client, auth_headers):
        resp = client.get("/journeys/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"active": [], "completed": []}

    def test_active(self, client, auth_headers, sample_journey):
        client.post("/journeys/bourbon-basics/start", headers=auth_headers)
        resp = client.get("/journeys/me", headers=auth_headers)
        data = resp.json()
        assert len(data["active"]) == 1
        assert len(data["completed"]) == 0

    def test_unauthenticated(self, client):
        resp = client.get("/journeys/me")
        assert resp.status_code == 401


class TestStartJourney:
    def test_start(self, client, auth_headers, sample_journey):
        resp = client.post("/journeys/bourbon-basics/start", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"
        assert resp.json()["current_step"] == 1

    def test_already_started(self, client, auth_headers, sample_journey):
        client.post("/journeys/bourbon-basics/start", headers=auth_headers)
        resp = client.post("/journeys/bourbon-basics/start", headers=auth_headers)
        assert resp.json()["status"] == "already_started"

    def test_not_found(self, client, auth_headers):
        resp = client.post("/journeys/nonexistent/start", headers=auth_headers)
        assert resp.status_code == 404

    def test_unauthenticated(self, client, sample_journey):
        resp = client.post("/journeys/bourbon-basics/start")
        assert resp.status_code == 401


class TestCompleteStep:
    def test_advances(self, client, auth_headers, sample_journey):
        client.post("/journeys/bourbon-basics/start", headers=auth_headers)
        resp = client.post("/journeys/bourbon-basics/steps/1/complete", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "step_complete"
        assert resp.json()["current_step"] == 2

    def test_complete_final_step(self, client, auth_headers, sample_journey):
        client.post("/journeys/bourbon-basics/start", headers=auth_headers)
        client.post("/journeys/bourbon-basics/steps/1/complete", headers=auth_headers)
        client.post("/journeys/bourbon-basics/steps/2/complete", headers=auth_headers)
        resp = client.post("/journeys/bourbon-basics/steps/3/complete", headers=auth_headers)
        assert resp.json()["status"] == "journey_complete"

    def test_wrong_step(self, client, auth_headers, sample_journey):
        client.post("/journeys/bourbon-basics/start", headers=auth_headers)
        resp = client.post("/journeys/bourbon-basics/steps/3/complete", headers=auth_headers)
        assert resp.status_code == 400

    def test_not_started(self, client, auth_headers, sample_journey):
        resp = client.post("/journeys/bourbon-basics/steps/1/complete", headers=auth_headers)
        assert resp.status_code == 400

    def test_journey_not_found(self, client, auth_headers):
        resp = client.post("/journeys/nonexistent/steps/1/complete", headers=auth_headers)
        assert resp.status_code == 404

    def test_unauthenticated(self, client, sample_journey):
        resp = client.post("/journeys/bourbon-basics/steps/1/complete")
        assert resp.status_code == 401
