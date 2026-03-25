"""Tests for taste similarity ML module."""

import numpy as np
import pytest

from app.ml.taste_similarity import (
    build_taste_vector,
    compute_palate_match,
    cosine_similarity,
    find_similar_users,
)
from app import models


# ── Cosine similarity (pure math, no DB) ─────────────────────────────────────


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = np.array([1.0, 0.0, 0.0])
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=0.01)

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=0.01)

    def test_zero_vector_returns_zero(self):
        zero = np.zeros(3)
        other = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(zero, other) == 0.0

    def test_similar_vectors_positive(self):
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.1, 2.1, 2.9])
        result = cosine_similarity(a, b)
        assert 0.0 <= result <= 1.0
        assert result > 0.9  # very similar

    def test_different_vectors_lower(self):
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 0.0, 1.0])
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=0.01)


# ── Build taste vector (needs DB) ────────────────────────────────────────────


def _create_user(db, username):
    """Create a test user directly in the DB."""
    user = models.User(
        username=username,
        email=f"{username}@test.com",
        hashed_password="x",
    )
    db.add(user)
    db.flush()
    return user


def _rate_whiskey(db, username, whiskey_id, score):
    """Create a rating directly in the DB."""
    r = models.UserRating(user_id=username, whiskey_id=whiskey_id, score=score)
    db.add(r)
    db.flush()
    return r


class TestBuildTasteVector:
    def test_no_ratings_returns_no_data(self, db_session, sample_whiskeys):
        _create_user(db_session, "empty_user")
        result = build_taste_vector("empty_user", db_session)
        assert result["has_data"] is False
        assert result["total"] == 0

    def test_single_rating_returns_no_data(self, db_session, sample_whiskeys):
        _create_user(db_session, "one_rating")
        _rate_whiskey(db_session, "one_rating", sample_whiskeys[0].id, 4.0)
        result = build_taste_vector("one_rating", db_session)
        assert result["has_data"] is False
        assert result["total"] == 1

    def test_two_ratings_returns_data(self, db_session, sample_whiskeys):
        _create_user(db_session, "two_ratings")
        _rate_whiskey(db_session, "two_ratings", sample_whiskeys[0].id, 4.0)
        _rate_whiskey(db_session, "two_ratings", sample_whiskeys[1].id, 3.5)
        result = build_taste_vector("two_ratings", db_session)
        assert result["has_data"] is True
        assert result["total"] == 2
        assert isinstance(result["vector"], np.ndarray)
        assert len(result["vector"]) > 0

    def test_vector_is_normalized(self, db_session, sample_whiskeys):
        _create_user(db_session, "norm_user")
        _rate_whiskey(db_session, "norm_user", sample_whiskeys[0].id, 5.0)
        _rate_whiskey(db_session, "norm_user", sample_whiskeys[1].id, 3.0)
        result = build_taste_vector("norm_user", db_session)
        assert result["has_data"] is True
        norm = np.linalg.norm(result["vector"])
        assert norm == pytest.approx(1.0, abs=0.01)

    def test_category_scores_computed(self, db_session, sample_whiskeys):
        _create_user(db_session, "cat_user")
        # Rate bourbon (index 0) and scotch (index 1)
        _rate_whiskey(db_session, "cat_user", sample_whiskeys[0].id, 4.0)
        _rate_whiskey(db_session, "cat_user", sample_whiskeys[1].id, 3.0)
        result = build_taste_vector("cat_user", db_session)
        assert "bourbon" in result["category_scores"]
        assert result["category_scores"]["bourbon"]["avg"] == pytest.approx(4.0)
        assert result["category_scores"]["bourbon"]["count"] == 1

    def test_top_flavors_extracted(self, db_session, sample_whiskeys):
        _create_user(db_session, "flav_user")
        # Buffalo Trace has "vanilla, caramel, sweet, oak"
        _rate_whiskey(db_session, "flav_user", sample_whiskeys[0].id, 4.0)
        # Crown Royal has "smooth, vanilla, caramel, gentle spice"
        _rate_whiskey(db_session, "flav_user", sample_whiskeys[5].id, 3.5)
        result = build_taste_vector("flav_user", db_session)
        assert len(result["top_flavors"]) > 0
        # vanilla appears in both — should be in top flavors
        assert "vanilla" in result["top_flavors"]

    def test_top_categories_ordered(self, db_session, sample_whiskeys):
        _create_user(db_session, "cat_order")
        # Rate 2 bourbons (indices 0, 4 are bourbon and rye) and 1 scotch
        _rate_whiskey(db_session, "cat_order", sample_whiskeys[0].id, 4.0)  # bourbon
        _rate_whiskey(db_session, "cat_order", sample_whiskeys[4].id, 3.5)  # rye
        _rate_whiskey(db_session, "cat_order", sample_whiskeys[1].id, 3.0)  # scotch
        result = build_taste_vector("cat_order", db_session)
        # Each category has 1 rating, so order depends on sorting
        assert len(result["top_categories"]) >= 2


# ── Compute palate match (needs DB + two users) ─────────────────────────────


class TestComputePalateMatch:
    def test_both_users_sufficient_data(self, db_session, sample_whiskeys):
        _create_user(db_session, "alice")
        _create_user(db_session, "bob")
        for w in sample_whiskeys[:3]:
            _rate_whiskey(db_session, "alice", w.id, 4.0)
            _rate_whiskey(db_session, "bob", w.id, 3.8)
        result = compute_palate_match("alice", "bob", db_session)
        assert result["match_score"] is not None
        assert 0 <= result["match_score"] <= 100

    def test_insufficient_data_user_a(self, db_session, sample_whiskeys):
        _create_user(db_session, "short_a")
        _create_user(db_session, "full_b")
        _rate_whiskey(db_session, "short_a", sample_whiskeys[0].id, 4.0)
        _rate_whiskey(db_session, "full_b", sample_whiskeys[0].id, 4.0)
        _rate_whiskey(db_session, "full_b", sample_whiskeys[1].id, 3.5)
        result = compute_palate_match("short_a", "full_b", db_session)
        assert result["match_score"] is None
        assert result["message"] is not None

    def test_insufficient_data_user_b(self, db_session, sample_whiskeys):
        _create_user(db_session, "full_a2")
        _create_user(db_session, "empty_b")
        _rate_whiskey(db_session, "full_a2", sample_whiskeys[0].id, 4.0)
        _rate_whiskey(db_session, "full_a2", sample_whiskeys[1].id, 3.5)
        result = compute_palate_match("full_a2", "empty_b", db_session)
        assert result["match_score"] is None

    def test_similar_users_high_score(self, db_session, sample_whiskeys):
        _create_user(db_session, "sim_a")
        _create_user(db_session, "sim_b")
        # Same whiskeys, same scores
        for w in sample_whiskeys[:3]:
            _rate_whiskey(db_session, "sim_a", w.id, 4.5)
            _rate_whiskey(db_session, "sim_b", w.id, 4.5)
        result = compute_palate_match("sim_a", "sim_b", db_session)
        assert result["match_score"] is not None
        assert result["match_score"] >= 80  # very similar

    def test_agreements_populated(self, db_session, sample_whiskeys):
        _create_user(db_session, "agree_a")
        _create_user(db_session, "agree_b")
        # Both rate bourbon and scotch similarly (diff < 0.8)
        _rate_whiskey(db_session, "agree_a", sample_whiskeys[0].id, 4.0)  # bourbon
        _rate_whiskey(db_session, "agree_a", sample_whiskeys[1].id, 3.5)  # scotch
        _rate_whiskey(db_session, "agree_b", sample_whiskeys[0].id, 4.2)  # bourbon
        _rate_whiskey(db_session, "agree_b", sample_whiskeys[1].id, 3.3)  # scotch
        result = compute_palate_match("agree_a", "agree_b", db_session)
        assert len(result["agreements"]) > 0

    def test_shared_flavors_computed(self, db_session, sample_whiskeys):
        _create_user(db_session, "flav_a")
        _create_user(db_session, "flav_b")
        # Both rate Buffalo Trace (vanilla, caramel) and Crown Royal (vanilla, caramel)
        _rate_whiskey(db_session, "flav_a", sample_whiskeys[0].id, 4.0)
        _rate_whiskey(db_session, "flav_a", sample_whiskeys[5].id, 3.5)
        _rate_whiskey(db_session, "flav_b", sample_whiskeys[0].id, 4.2)
        _rate_whiskey(db_session, "flav_b", sample_whiskeys[5].id, 3.8)
        result = compute_palate_match("flav_a", "flav_b", db_session)
        assert len(result["shared_flavors"]) > 0

    def test_response_shape(self, db_session, sample_whiskeys):
        _create_user(db_session, "shape_a")
        _create_user(db_session, "shape_b")
        for w in sample_whiskeys[:2]:
            _rate_whiskey(db_session, "shape_a", w.id, 4.0)
            _rate_whiskey(db_session, "shape_b", w.id, 3.5)
        result = compute_palate_match("shape_a", "shape_b", db_session)
        assert "match_score" in result
        assert "shared_flavors" in result
        assert "agreements" in result
        assert "disagreements" in result
        assert "your_total_rated" in result
        assert "their_total_rated" in result
        assert "message" in result


# ── Find similar users ───────────────────────────────────────────────────────


class TestFindSimilarUsers:
    def test_returns_similar_users(self, db_session, sample_whiskeys):
        _create_user(db_session, "me")
        _create_user(db_session, "candidate1")
        for w in sample_whiskeys[:3]:
            _rate_whiskey(db_session, "me", w.id, 4.0)
            _rate_whiskey(db_session, "candidate1", w.id, 3.8)
        results = find_similar_users("me", db_session, set(), limit=5)
        assert len(results) >= 1
        assert results[0]["username"] == "candidate1"

    def test_excludes_self(self, db_session, sample_whiskeys):
        _create_user(db_session, "self_test")
        for w in sample_whiskeys[:2]:
            _rate_whiskey(db_session, "self_test", w.id, 4.0)
        results = find_similar_users("self_test", db_session, set(), limit=5)
        usernames = [r["username"] for r in results]
        assert "self_test" not in usernames

    def test_excludes_specified_ids(self, db_session, sample_whiskeys):
        _create_user(db_session, "exc_me")
        _create_user(db_session, "exc_other")
        for w in sample_whiskeys[:2]:
            _rate_whiskey(db_session, "exc_me", w.id, 4.0)
            _rate_whiskey(db_session, "exc_other", w.id, 3.5)
        results = find_similar_users("exc_me", db_session, {"exc_other"}, limit=5)
        usernames = [r["username"] for r in results]
        assert "exc_other" not in usernames

    def test_respects_limit(self, db_session, sample_whiskeys):
        _create_user(db_session, "lim_me")
        for i in range(3):
            name = f"lim_cand_{i}"
            _create_user(db_session, name)
            for w in sample_whiskeys[:2]:
                _rate_whiskey(db_session, name, w.id, 4.0 - i * 0.5)
        for w in sample_whiskeys[:2]:
            _rate_whiskey(db_session, "lim_me", w.id, 4.0)
        results = find_similar_users("lim_me", db_session, set(), limit=2)
        assert len(results) <= 2

    def test_no_data_returns_empty(self, db_session, sample_whiskeys):
        _create_user(db_session, "no_data")
        results = find_similar_users("no_data", db_session, set(), limit=5)
        assert results == []

    def test_candidates_need_two_ratings(self, db_session, sample_whiskeys):
        _create_user(db_session, "req_me")
        _create_user(db_session, "single_rater")
        for w in sample_whiskeys[:2]:
            _rate_whiskey(db_session, "req_me", w.id, 4.0)
        _rate_whiskey(db_session, "single_rater", sample_whiskeys[0].id, 4.0)
        results = find_similar_users("req_me", db_session, set(), limit=5)
        usernames = [r["username"] for r in results]
        assert "single_rater" not in usernames

    def test_result_shape(self, db_session, sample_whiskeys):
        _create_user(db_session, "shape_me")
        _create_user(db_session, "shape_cand")
        for w in sample_whiskeys[:2]:
            _rate_whiskey(db_session, "shape_me", w.id, 4.0)
            _rate_whiskey(db_session, "shape_cand", w.id, 3.5)
        results = find_similar_users("shape_me", db_session, set(), limit=5)
        assert len(results) >= 1
        r = results[0]
        assert "username" in r
        assert "match_score" in r
        assert "reason" in r
        assert "checkin_count" in r
