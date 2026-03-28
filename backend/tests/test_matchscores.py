"""Tests for the matchscores router — personal match score computation."""

import pytest


@pytest.fixture(autouse=True)
def clear_taste_cache():
    from app.routers.matchscores import _taste_cache
    _taste_cache.clear()
    yield
    _taste_cache.clear()


class TestBatchMatchScores:
    def test_no_ratings(self, client, auth_headers, sample_whiskeys):
        resp = client.post(
            "/match-scores/batch",
            json=[sample_whiskeys[0].id],
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_profile"] is False
        assert data["scores"] == {}

    def test_with_ratings(self, client, sample_user_with_ratings, sample_whiskeys):
        resp = client.post(
            "/match-scores/batch",
            json=[sample_whiskeys[3].id, sample_whiskeys[4].id],
            headers=sample_user_with_ratings,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_profile"] is True
        assert len(data["scores"]) > 0

    def test_scores_in_range(self, client, sample_user_with_ratings, sample_whiskeys):
        resp = client.post(
            "/match-scores/batch",
            json=[w.id for w in sample_whiskeys],
            headers=sample_user_with_ratings,
        )
        for score in resp.json()["scores"].values():
            assert 0 <= score <= 100

    def test_unauthenticated(self, client, sample_whiskeys):
        resp = client.post("/match-scores/batch", json=[sample_whiskeys[0].id])
        assert resp.status_code == 401

    def test_nonexistent_whiskeys_omitted(self, client, sample_user_with_ratings):
        resp = client.post(
            "/match-scores/batch",
            json=[99999],
            headers=sample_user_with_ratings,
        )
        data = resp.json()
        assert data["has_profile"] is True
        assert len(data["scores"]) == 0
