"""
Tests for the three new GenAI features:
  - POST /blind-tasting/coach
  - GET  /pairings/{whiskey_id}/ai-cocktail
  - GET  /collection/ai-insight

All Anthropic API calls are mocked so tests run offline without burning tokens.
The happy-path tests exercise the Claude-response branch; separate tests verify
the graceful fallback when the response is malformed JSON.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app import models


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_claude_response(text: str):
    """Build a minimal fake Anthropic response object."""
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def bourbon(sample_whiskeys):
    return next(w for w in sample_whiskeys if w.category == "bourbon")


@pytest.fixture()
def scotch(sample_whiskeys):
    return next(w for w in sample_whiskeys if w.category == "scotch")


@pytest.fixture()
def collection_with_items(client, auth_headers, sample_whiskeys, db_session):
    """Add two bottles to the authenticated user's collection."""
    for w in sample_whiskeys[:2]:
        client.post(
            "/collection/",
            json={"whiskey_id": w.id, "status": "sealed"},
            headers=auth_headers,
        )
    return auth_headers


# ── Blind Tasting Coach ───────────────────────────────────────────────────────


class TestBlindTastingCoach:
    _COACH_JSON = json.dumps({
        "lesson": "Bourbon's caramel notes come from the charred oak barrel.",
        "production_insight": "New charred oak is legally required for bourbon.",
        "next_tip": "Look for vanilla and caramel — that's the new oak talking.",
    })

    def test_correct_guess_with_ai(self, client, bourbon):
        with patch(
            "app.routers.ai_features._get_client",
            return_value=MagicMock(
                messages=MagicMock(
                    create=MagicMock(return_value=_make_claude_response(self._COACH_JSON))
                )
            ),
        ):
            resp = client.post(
                "/blind-tasting/coach",
                json={"whiskey_id": bourbon.id, "user_guess": "bourbon", "difficulty": "easy"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["correct"] is True
        assert data["whiskey_id"] == bourbon.id
        assert "lesson" in data
        assert "production_insight" in data
        assert "next_tip" in data

    def test_wrong_guess_correct_flag(self, client, bourbon):
        with patch(
            "app.routers.ai_features._get_client",
            return_value=MagicMock(
                messages=MagicMock(
                    create=MagicMock(return_value=_make_claude_response(self._COACH_JSON))
                )
            ),
        ):
            resp = client.post(
                "/blind-tasting/coach",
                json={"whiskey_id": bourbon.id, "user_guess": "scotch", "difficulty": "medium"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["correct"] is False
        assert data["whiskey_category"] == "bourbon"
        assert data["user_guess"] == "scotch"

    def test_fallback_on_bad_json(self, client, bourbon):
        """If Claude returns non-JSON, the fallback response is used (no 500)."""
        with patch(
            "app.routers.ai_features._get_client",
            return_value=MagicMock(
                messages=MagicMock(
                    create=MagicMock(return_value=_make_claude_response("not valid json !!!"))
                )
            ),
        ):
            resp = client.post(
                "/blind-tasting/coach",
                json={"whiskey_id": bourbon.id, "user_guess": "bourbon"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "lesson" in data
        assert "production_insight" in data
        assert "next_tip" in data

    def test_whiskey_not_found(self, client):
        resp = client.post(
            "/blind-tasting/coach",
            json={"whiskey_id": 99999, "user_guess": "bourbon"},
        )
        assert resp.status_code == 404

    def test_coach_contains_whiskey_name(self, client, bourbon):
        with patch(
            "app.routers.ai_features._get_client",
            return_value=MagicMock(
                messages=MagicMock(
                    create=MagicMock(return_value=_make_claude_response(self._COACH_JSON))
                )
            ),
        ):
            resp = client.post(
                "/blind-tasting/coach",
                json={"whiskey_id": bourbon.id, "user_guess": "bourbon"},
            )
        data = resp.json()
        assert data["whiskey_name"] == bourbon.name


# ── AI Bespoke Cocktail ────────────────────────────────────────────────────────


class TestAIBespokeCocktail:
    _COCKTAIL_JSON = json.dumps({
        "name": "The Peat Fog",
        "tagline": "Smoky, briny, and dangerously easy to drink.",
        "ingredients": [
            {"amount": "2 oz", "item": "Laphroaig 10"},
            {"amount": "0.5 oz", "item": "honey syrup"},
            {"amount": "0.75 oz", "item": "lemon juice"},
            {"amount": "2 dashes", "item": "Angostura bitters"},
        ],
        "instructions": "Shake with ice. Double strain into a chilled coupe.",
        "garnish": "Lemon twist",
        "glassware": "Coupe",
        "why": "Honey and lemon round out the aggressive peat. Bitters add depth without fighting the smoke.",
    })

    def test_happy_path(self, client, scotch):
        with patch(
            "app.routers.ai_features._get_client",
            return_value=MagicMock(
                messages=MagicMock(
                    create=MagicMock(return_value=_make_claude_response(self._COCKTAIL_JSON))
                )
            ),
        ):
            resp = client.get(f"/pairings/{scotch.id}/ai-cocktail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["whiskey_id"] == scotch.id
        assert data["whiskey_name"] == scotch.name
        assert "name" in data
        assert "ingredients" in data
        assert isinstance(data["ingredients"], list)
        assert len(data["ingredients"]) > 0
        assert "instructions" in data
        assert "why" in data

    def test_ingredients_have_required_keys(self, client, scotch):
        with patch(
            "app.routers.ai_features._get_client",
            return_value=MagicMock(
                messages=MagicMock(
                    create=MagicMock(return_value=_make_claude_response(self._COCKTAIL_JSON))
                )
            ),
        ):
            resp = client.get(f"/pairings/{scotch.id}/ai-cocktail")
        data = resp.json()
        for ingredient in data["ingredients"]:
            assert "amount" in ingredient
            assert "item" in ingredient

    def test_fallback_on_bad_json(self, client, scotch):
        with patch(
            "app.routers.ai_features._get_client",
            return_value=MagicMock(
                messages=MagicMock(
                    create=MagicMock(return_value=_make_claude_response("not json"))
                )
            ),
        ):
            resp = client.get(f"/pairings/{scotch.id}/ai-cocktail")
        assert resp.status_code == 200
        data = resp.json()
        # Fallback returns a simple highball recipe
        assert "name" in data
        assert "ingredients" in data
        assert len(data["ingredients"]) > 0

    def test_whiskey_not_found(self, client):
        resp = client.get("/pairings/99999/ai-cocktail")
        assert resp.status_code == 404

    def test_bourbon_cocktail(self, client, bourbon):
        with patch(
            "app.routers.ai_features._get_client",
            return_value=MagicMock(
                messages=MagicMock(
                    create=MagicMock(return_value=_make_claude_response(self._COCKTAIL_JSON))
                )
            ),
        ):
            resp = client.get(f"/pairings/{bourbon.id}/ai-cocktail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["whiskey_category"] == "bourbon"


# ── AI Collection Insight ──────────────────────────────────────────────────────


class TestAICollectionInsight:
    _INSIGHT_JSON = json.dumps({
        "headline": "A bourbon-forward shelf with an Islay adventurous streak.",
        "collection_story": "Two bottles, two styles, one curious palate.",
        "open_tonight_reason": "It's the highest rated bottle — a perfect Friday pour.",
        "gap_to_fill": "A Japanese whisky would add delicacy. Try Suntory Toki.",
        "fun_stat": "Your collection spans two continents.",
    })

    def test_empty_collection_no_ai_call(self, client, auth_headers):
        """Empty collection returns a helpful message without calling Claude."""
        resp = client.get("/collection/ai-insight", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["bottle_count"] == 0
        assert "open_tonight" in data
        assert data["open_tonight"] is None
        assert "gap_to_fill" in data

    def test_requires_auth(self, client):
        resp = client.get("/collection/ai-insight")
        assert resp.status_code == 401

    def test_happy_path_with_collection(self, client, collection_with_items):
        with patch(
            "app.routers.ai_features._get_client",
            return_value=MagicMock(
                messages=MagicMock(
                    create=MagicMock(return_value=_make_claude_response(self._INSIGHT_JSON))
                )
            ),
        ):
            resp = client.get("/collection/ai-insight", headers=collection_with_items)
        assert resp.status_code == 200
        data = resp.json()
        assert data["bottle_count"] == 2
        assert "headline" in data
        assert "collection_story" in data
        assert "gap_to_fill" in data
        assert "fun_stat" in data

    def test_open_tonight_is_populated(self, client, collection_with_items):
        with patch(
            "app.routers.ai_features._get_client",
            return_value=MagicMock(
                messages=MagicMock(
                    create=MagicMock(return_value=_make_claude_response(self._INSIGHT_JSON))
                )
            ),
        ):
            resp = client.get("/collection/ai-insight", headers=collection_with_items)
        data = resp.json()
        ot = data["open_tonight"]
        assert ot is not None
        assert "whiskey_id" in ot
        assert "name" in ot
        assert "reason" in ot

    def test_fallback_on_bad_json(self, client, collection_with_items):
        with patch(
            "app.routers.ai_features._get_client",
            return_value=MagicMock(
                messages=MagicMock(
                    create=MagicMock(return_value=_make_claude_response("not json!!"))
                )
            ),
        ):
            resp = client.get("/collection/ai-insight", headers=collection_with_items)
        assert resp.status_code == 200
        data = resp.json()
        assert "headline" in data
        assert "collection_story" in data
        assert data["bottle_count"] == 2
