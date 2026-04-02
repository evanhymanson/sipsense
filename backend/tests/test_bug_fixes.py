"""
Regression tests for bugs identified and fixed:

1. Duplicate `import math` inside agent.py find_value_picks()
2. Journal image URL format returned by /journal/me (must be /uploads/... not /api/uploads/...)
3. Redundant file-serve routes removed from journal.py (static mount handles /uploads/*)
4. Barcode route /whiskeys/barcode/{upc} not shadowed by /{whiskey_id}
5. CheckInResponse always includes `toast_count` field on the nested rating
"""

import ast
import importlib.util
from pathlib import Path

import pytest
from app import models
from app.badges import seed_badges


# ── Fixture helpers ──────────────────────────────────────────────────────────

@pytest.fixture()
def seeded_whiskey(db_session):
    seed_badges(db_session)
    w = models.Whiskey(
        name="Test Bourbon",
        distillery="Test Distillery",
        category="bourbon",
        abv=46.0,
        price_usd=40.0,
        rating_avg=0.0,
        rating_count=0,
    )
    db_session.add(w)
    db_session.flush()
    return w


@pytest.fixture()
def whiskey_with_upc(db_session):
    seed_badges(db_session)
    w = models.Whiskey(
        name="Barcode Bourbon",
        distillery="Scan Distillery",
        category="bourbon",
        abv=45.0,
        price_usd=35.0,
        rating_avg=4.1,
        rating_count=0,
        upc="080432400005",
    )
    db_session.add(w)
    db_session.flush()
    return w


# ── Bug 1: No duplicate `import math` in agent.py ───────────────────────────

class TestNoDuplicateMathImport:
    def test_import_math_not_inside_function(self):
        """agent.py must not have `import math` buried inside a function body."""
        agent_path = Path(__file__).resolve().parent.parent / "app" / "ml" / "agent.py"
        source = agent_path.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            # Function definitions (sync or async)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if isinstance(child, ast.Import):
                        for alias in child.names:
                            assert alias.name != "math", (
                                f"Found `import math` inside function "
                                f"'{node.name}' at line {child.lineno}. "
                                "Remove it — math is already imported at module level."
                            )

    def test_math_imported_at_module_level(self):
        """math must be imported at the module level of agent.py."""
        agent_path = Path(__file__).resolve().parent.parent / "app" / "ml" / "agent.py"
        source = agent_path.read_text()
        tree = ast.parse(source)

        module_imports = [
            alias.name
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        ]
        assert "math" in module_imports, (
            "math is no longer imported at module level in agent.py"
        )


# ── Bug 2: Journal image_url format must be /uploads/... ────────────────────

class TestJournalImageUrl:
    def test_journal_image_url_format(self, client, auth_headers, seeded_whiskey, monkeypatch):
        """image_url returned by /journal/me must start with /uploads/, not /api/uploads/."""
        # Ensure CDN is disabled so we test the raw path logic
        import app.storage as storage_mod
        monkeypatch.setattr(storage_mod, "CDN_BASE_URL", None)

        wid = seeded_whiskey.id

        # Create a rating
        resp = client.post(
            f"/whiskeys/{wid}/rate",
            json={"score": 4.0, "notes": "Nice"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        rating_id = resp.json()["rating"]["id"]

        # Simulate a stored image_path on the rating by patching the DB directly
        from app.database import get_db
        db = next(client.app.dependency_overrides[get_db]())
        rating = db.query(models.UserRating).filter(models.UserRating.id == rating_id).first()
        rating.image_path = f"ratings/{rating_id}_abc123.jpg"
        db.flush()

        # Fetch journal
        journal_resp = client.get("/journal/me", headers=auth_headers)
        assert journal_resp.status_code == 200
        entries = journal_resp.json()["entries"]
        assert len(entries) >= 1

        entry_with_image = next((e for e in entries if e["image_url"]), None)
        assert entry_with_image is not None, "Expected an entry with an image_url"

        image_url = entry_with_image["image_url"]
        assert image_url.startswith("/uploads/"), (
            f"image_url should start with /uploads/ but got: {image_url!r}"
        )
        assert not image_url.startswith("/api/"), (
            f"image_url must NOT start with /api/ but got: {image_url!r}"
        )

    def test_journal_no_image_returns_none(self, client, auth_headers, seeded_whiskey):
        """Entries without a photo should have image_url == None."""
        wid = seeded_whiskey.id
        client.post(
            f"/whiskeys/{wid}/rate",
            json={"score": 3.5},
            headers=auth_headers,
        )
        resp = client.get("/journal/me", headers=auth_headers)
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        # Ratings without image_path should produce null image_url
        entries_without_image = [e for e in entries if e["image_url"] is None]
        assert len(entries_without_image) >= 1


# ── Bug 3: Removed redundant /uploads/ router routes ────────────────────────

class TestRemovedRedundantUploadRoutes:
    def test_uploads_ratings_route_not_registered_as_api_route(self):
        """The /uploads/ratings/{filename} path must NOT be a registered APIRouter route
        in journal.py (it was redundant with the static file mount)."""
        from app.routers import journal

        # Collect all route paths registered on the journal router
        route_paths = [r.path for r in journal.router.routes]
        assert "/uploads/ratings/{filename}" not in route_paths, (
            "Redundant /uploads/ratings/{filename} route still exists in journal.py"
        )
        assert "/uploads/bottles/{filename}" not in route_paths, (
            "Redundant /uploads/bottles/{filename} route still exists in journal.py"
        )

    def test_journal_core_routes_still_present(self):
        """Essential journal routes must still be registered after cleanup."""
        from app.routers import journal

        route_paths = [r.path for r in journal.router.routes]
        assert "/ratings/{rating_id}/image" in route_paths, (
            "Upload image route must still exist"
        )
        assert "/journal/me" in route_paths, (
            "Journal timeline route must still exist"
        )


# ── Bug 4: Barcode route not shadowed by /{whiskey_id} ──────────────────────

class TestBarcodeRouteResolution:
    def test_barcode_lookup_found(self, client, whiskey_with_upc):
        """GET /whiskeys/barcode/{upc} should return the matching whiskey."""
        resp = client.get(f"/whiskeys/barcode/{whiskey_with_upc.upc}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Barcode Bourbon"
        assert data["id"] == whiskey_with_upc.id

    def test_barcode_lookup_not_found(self, client, whiskey_with_upc):
        """Unknown UPC should return 404, not try to fetch a whiskey by ID."""
        resp = client.get("/whiskeys/barcode/000000000000")
        assert resp.status_code == 404

    def test_barcode_path_not_confused_with_whiskey_id(self, client, whiskey_with_upc):
        """`barcode` must NOT be interpreted as a whiskey_id integer."""
        # If the route was broken, GET /whiskeys/barcode/... would try to cast
        # 'barcode' as int and return 422 instead of routing to the barcode handler.
        resp = client.get(f"/whiskeys/barcode/{whiskey_with_upc.upc}")
        assert resp.status_code != 422, (
            "Got 422 — 'barcode' is being misinterpreted as a whiskey_id integer"
        )

    def test_barcode_leading_zeros_stripped(self, client, whiskey_with_upc):
        """Barcode lookup should match even when leading zeros differ."""
        # Try looking up with extra leading zeros
        padded_upc = "00" + whiskey_with_upc.upc
        resp = client.get(f"/whiskeys/barcode/{padded_upc}")
        assert resp.status_code == 200
        assert resp.json()["id"] == whiskey_with_upc.id


# ── Bug 5: CheckInResponse always includes toast_count ──────────────────────

class TestCheckInResponseShape:
    def test_rating_has_toast_count(self, client, auth_headers, seeded_whiskey):
        """The rating object inside CheckInResponse must always include toast_count."""
        wid = seeded_whiskey.id
        resp = client.post(
            f"/whiskeys/{wid}/rate",
            json={"score": 4.2, "notes": "Smooth"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        rating = data["rating"]
        assert "toast_count" in rating, (
            "rating in CheckInResponse is missing toast_count field"
        )
        assert rating["toast_count"] == 0

    def test_checkin_response_has_new_badges(self, client, auth_headers, seeded_whiskey):
        """CheckInResponse must always include new_badges (list, may be empty)."""
        wid = seeded_whiskey.id
        resp = client.post(
            f"/whiskeys/{wid}/rate",
            json={"score": 3.8},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "new_badges" in data
        assert isinstance(data["new_badges"], list)

    def test_rating_fields_complete(self, client, auth_headers, seeded_whiskey):
        """All expected fields must be present on the rating object."""
        wid = seeded_whiskey.id
        resp = client.post(
            f"/whiskeys/{wid}/rate",
            json={
                "score": 4.0,
                "notes": "Good",
                "serving_style": "neat",
                "location_note": "Home bar",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        rating = resp.json()["rating"]
        for field in ("id", "user_id", "whiskey_id", "score", "notes",
                      "serving_style", "location_note", "image_url",
                      "created_at", "toast_count"):
            assert field in rating, f"Missing field: {field}"

        assert rating["score"] == 4.0
        assert rating["serving_style"] == "neat"
        assert rating["location_note"] == "Home bar"
        assert rating["image_url"] is None  # no photo uploaded
