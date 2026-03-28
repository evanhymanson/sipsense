"""Tests for taste identity endpoints: evolution, percentiles, quiz."""

import pytest


class TestPalateEvolution:
    def test_evolution_empty(self, client, auth_headers):
        """No ratings → empty months."""
        resp = client.get("/taste-identity/evolution", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["months"] == []

    def test_evolution_with_ratings(self, client, auth_headers, sample_user_with_ratings):
        """User with ratings → gets monthly snapshots."""
        resp = client.get("/taste-identity/evolution", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["months"], list)

    def test_evolution_requires_auth(self, client):
        resp = client.get("/taste-identity/evolution")
        assert resp.status_code in (401, 403)


class TestPercentiles:
    def test_percentiles_with_ratings(self, client, auth_headers, sample_user_with_ratings):
        resp = client.get("/taste-identity/percentiles", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_rated_percentile" in data
        assert "diversity_score" in data

    def test_percentiles_requires_auth(self, client):
        resp = client.get("/taste-identity/percentiles")
        assert resp.status_code in (401, 403)


class TestQuiz:
    def test_quiz_question_format(self, client, sample_whiskeys):
        """Quiz question returns 4 options with clues."""
        resp = client.get("/taste-identity/quiz-question")
        assert resp.status_code == 200
        data = resp.json()
        assert "options" in data
        assert len(data["options"]) == 4
        assert "correct_id" in data

    def test_quiz_answer_correct(self, client, sample_whiskeys):
        """Submitting the correct answer returns correct: true."""
        q = client.get("/taste-identity/quiz-question").json()
        resp = client.post("/taste-identity/quiz-answer", json={
            "correct_id": q["correct_id"],
            "answer_id": q["correct_id"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["correct"] is True

    def test_quiz_answer_wrong(self, client, sample_whiskeys):
        """Submitting wrong answer returns correct: false."""
        q = client.get("/taste-identity/quiz-question").json()
        wrong_id = [o["id"] for o in q["options"] if o["id"] != q["correct_id"]][0]
        resp = client.post("/taste-identity/quiz-answer", json={
            "correct_id": q["correct_id"],
            "answer_id": wrong_id,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["correct"] is False
        assert "correct_whiskey" in data
