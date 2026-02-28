"""Unit tests for the ML recommender module: vectors, similarity, quiz logic."""

import numpy as np
from app.ml.recommender import (
    _whiskey_vector,
    _quiz_vector,
    FLAVOR_TAGS,
    CATEGORIES,
)
from app import models


def _make_whiskey(**kwargs):
    defaults = {
        "name": "Test",
        "distillery": "Test",
        "category": "bourbon",
        "abv": 45.0,
        "age": 10,
        "price_usd": 50.0,
        "flavor_profile": "vanilla, caramel",
        "rating_avg": 4.0,
        "rating_count": 0,
    }
    defaults.update(kwargs)
    return models.Whiskey(**defaults)


class TestWhiskeyVector:
    def test_vector_dimensions(self):
        w = _make_whiskey()
        vec = _whiskey_vector(w)
        expected = len(CATEGORIES) + 3 + len(FLAVOR_TAGS)  # categories + abv/age/price + flavors
        assert len(vec) == expected

    def test_vector_normalized(self):
        w = _make_whiskey()
        vec = _whiskey_vector(w)
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 0.01

    def test_bourbon_more_similar_to_bourbon(self):
        bourbon1 = _make_whiskey(category="bourbon", flavor_profile="vanilla, caramel, sweet")
        bourbon2 = _make_whiskey(category="bourbon", flavor_profile="vanilla, oak, caramel")
        scotch = _make_whiskey(category="scotch", flavor_profile="smoky, peaty, medicinal")

        v1 = _whiskey_vector(bourbon1)
        v2 = _whiskey_vector(bourbon2)
        vs = _whiskey_vector(scotch)

        sim_bb = float(np.dot(v1, v2))
        sim_bs = float(np.dot(v1, vs))
        assert sim_bb > sim_bs

    def test_similarity_range(self):
        w1 = _make_whiskey(category="bourbon")
        w2 = _make_whiskey(category="scotch", flavor_profile="smoky, peaty")
        v1 = _whiskey_vector(w1)
        v2 = _whiskey_vector(w2)
        sim = float(np.dot(v1, v2))
        assert 0 <= sim <= 1.0


class TestQuizVector:
    def test_smoky_quiz_weights_peat(self):
        from app.schemas import QuizAnswers
        answers = QuizAnswers(
            style="scotch",
            flavors=["smoky"],
            smokiness="heavy",
            body="full",
            budget="mid",
        )
        vec = _quiz_vector(answers)
        # Find smoky/peaty indices
        flavor_start = len(CATEGORIES) + 3
        smoky_idx = flavor_start + FLAVOR_TAGS.index("smoky")
        peaty_idx = flavor_start + FLAVOR_TAGS.index("peaty")
        # These should have high values (=1.0 before normalization)
        assert vec[smoky_idx] > 0
        assert vec[peaty_idx] > 0

    def test_quiz_vector_normalized(self):
        from app.schemas import QuizAnswers
        answers = QuizAnswers(style="bourbon", flavors=["vanilla"], smokiness="none")
        vec = _quiz_vector(answers)
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 0.01
