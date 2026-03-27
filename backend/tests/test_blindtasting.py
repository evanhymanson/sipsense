"""Tests for the blindtasting router — gamified whiskey education."""

import random


class TestGetChallenge:
    def test_easy(self, client, sample_whiskeys):
        random.seed(42)
        resp = client.get("/blind-tasting/challenge?difficulty=easy")
        assert resp.status_code == 200
        data = resp.json()
        assert "challenge_id" in data
        assert "clues" in data

    def test_easy_has_abv(self, client, sample_whiskeys):
        random.seed(42)
        clues = client.get("/blind-tasting/challenge?difficulty=easy").json()["clues"]
        assert "abv" in clues

    def test_easy_has_flavors(self, client, sample_whiskeys):
        random.seed(42)
        clues = client.get("/blind-tasting/challenge?difficulty=easy").json()["clues"]
        assert "flavors" in clues

    def test_hard_limited_flavors(self, client, sample_whiskeys):
        random.seed(42)
        clues = client.get("/blind-tasting/challenge?difficulty=hard").json()["clues"]
        if "flavors" in clues:
            assert len(clues["flavors"]) <= 2

    def test_hard_no_abv(self, client, sample_whiskeys):
        random.seed(42)
        clues = client.get("/blind-tasting/challenge?difficulty=hard").json()["clues"]
        assert "abv" not in clues

    def test_invalid_difficulty(self, client, sample_whiskeys):
        resp = client.get("/blind-tasting/challenge?difficulty=extreme")
        assert resp.status_code == 400

    def test_clue_shape(self, client, sample_whiskeys):
        random.seed(42)
        clues = client.get("/blind-tasting/challenge?difficulty=easy").json()["clues"]
        assert "difficulty" in clues
        assert "points" in clues
        assert "guess_options" in clues

    def test_no_whiskeys(self, client):
        # No sample_whiskeys fixture = empty DB
        resp = client.get("/blind-tasting/challenge")
        assert resp.status_code == 404


class TestSubmitGuess:
    def test_correct_guess(self, client, sample_whiskeys):
        # Buffalo Trace is category "bourbon"
        resp = client.post(
            "/blind-tasting/guess",
            json={
                "whiskey_id": sample_whiskeys[0].id,
                "guess_category": "bourbon",
                "difficulty": "easy",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["correct"] is True
        assert data["points"] > 0

    def test_incorrect_guess(self, client, sample_whiskeys):
        # Buffalo Trace is "bourbon", guessing "irish"
        resp = client.post(
            "/blind-tasting/guess",
            json={
                "whiskey_id": sample_whiskeys[0].id,
                "guess_category": "irish",
                "difficulty": "easy",
            },
        )
        data = resp.json()
        assert data["correct"] is False
        assert data["points"] == 0

    def test_partial_credit(self, client, sample_whiskeys):
        # Laphroaig is "scotch", guessing "single malt" should get partial
        resp = client.post(
            "/blind-tasting/guess",
            json={
                "whiskey_id": sample_whiskeys[1].id,
                "guess_category": "single malt",
                "difficulty": "easy",
            },
        )
        data = resp.json()
        assert data["partial"] is True

    def test_reveals_whiskey(self, client, sample_whiskeys):
        resp = client.post(
            "/blind-tasting/guess",
            json={
                "whiskey_id": sample_whiskeys[0].id,
                "guess_category": "bourbon",
            },
        )
        reveal = resp.json()["reveal"]
        assert reveal["name"] == "Buffalo Trace"
        assert "category" in reveal

    def test_includes_fun_fact(self, client, sample_whiskeys):
        resp = client.post(
            "/blind-tasting/guess",
            json={
                "whiskey_id": sample_whiskeys[0].id,
                "guess_category": "bourbon",
            },
        )
        assert "fun_fact" in resp.json()
        assert len(resp.json()["fun_fact"]) > 0

    def test_nonexistent_whiskey(self, client):
        resp = client.post(
            "/blind-tasting/guess",
            json={"whiskey_id": 99999, "guess_category": "bourbon"},
        )
        assert resp.status_code == 404

    def test_response_shape(self, client, sample_whiskeys):
        resp = client.post(
            "/blind-tasting/guess",
            json={
                "whiskey_id": sample_whiskeys[0].id,
                "guess_category": "bourbon",
            },
        )
        data = resp.json()
        for key in ("correct", "partial", "points", "message", "reveal", "fun_fact"):
            assert key in data
