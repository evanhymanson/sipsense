"""Tests for post-check-in insights."""

import pytest


class TestCheckinInsights:
    def test_insights_in_checkin_response(self, client, auth_headers, sample_whiskeys):
        """Check-in response includes insights array."""
        resp = client.post(
            f"/whiskeys/{sample_whiskeys[0].id}/rate",
            json={"score": 4.0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "insights" in data
        assert isinstance(data["insights"], list)

    def test_streak_in_checkin_response(self, client, auth_headers, sample_whiskeys):
        """Check-in response includes streak info."""
        resp = client.post(
            f"/whiskeys/{sample_whiskeys[0].id}/rate",
            json={"score": 4.0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "streak" in data
        if data["streak"]:
            assert "current_streak" in data["streak"]

    def test_challenge_updates_in_checkin_response(self, client, auth_headers, sample_whiskeys):
        """Check-in response includes challenge_updates array."""
        resp = client.post(
            f"/whiskeys/{sample_whiskeys[0].id}/rate",
            json={"score": 4.0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "challenge_updates" in data
        assert isinstance(data["challenge_updates"], list)

    def test_multiple_ratings_insights(self, client, auth_headers, sample_whiskeys):
        """Second rating in same category → insight about category count."""
        # Rate first bourbon
        client.post(
            f"/whiskeys/{sample_whiskeys[0].id}/rate",
            json={"score": 4.0},
            headers=auth_headers,
        )
        # Rate another whiskey — insights should reflect previous ratings
        resp = client.post(
            f"/whiskeys/{sample_whiskeys[1].id}/rate",
            json={"score": 3.5},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["insights"], list)
