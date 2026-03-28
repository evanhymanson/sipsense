"""Tests for community challenges."""

import pytest
from app import models
from app.seed_challenges import seed_challenges


@pytest.fixture
def seeded_challenges(db_session):
    """Seed sample challenges into the DB."""
    seed_challenges(db_session)
    return db_session.query(models.Challenge).all()


class TestChallengeEndpoints:
    def test_list_active(self, client, seeded_challenges):
        resp = client.get("/challenges/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_by_slug(self, client, seeded_challenges):
        slug = seeded_challenges[0].slug
        resp = client.get(f"/challenges/{slug}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == slug
        assert "leaderboard" in data

    def test_join_challenge(self, client, auth_headers, seeded_challenges):
        slug = seeded_challenges[0].slug
        resp = client.post(f"/challenges/{slug}/join", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "joined"

    def test_duplicate_join_409(self, client, auth_headers, seeded_challenges):
        slug = seeded_challenges[0].slug
        client.post(f"/challenges/{slug}/join", headers=auth_headers)
        resp = client.post(f"/challenges/{slug}/join", headers=auth_headers)
        assert resp.status_code == 409

    def test_my_challenges(self, client, auth_headers, seeded_challenges):
        slug = seeded_challenges[0].slug
        client.post(f"/challenges/{slug}/join", headers=auth_headers)
        resp = client.get("/challenges/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["slug"] == slug

    def test_not_found(self, client):
        resp = client.get("/challenges/nonexistent-slug")
        assert resp.status_code == 404
