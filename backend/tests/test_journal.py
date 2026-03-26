"""Tests for journal (rating photo upload + timeline) endpoints."""
import io


class TestUploadRatingImage:
    def test_upload_unauthenticated(self, client):
        resp = client.post("/ratings/1/image", files={"file": ("test.jpg", b"fake", "image/jpeg")})
        assert resp.status_code == 401

    def test_upload_invalid_rating(self, client, auth_headers, sample_whiskeys):
        resp = client.post(
            "/ratings/99999/image",
            files={"file": ("test.jpg", b"fake", "image/jpeg")},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_upload_not_your_rating(self, client, auth_headers, second_auth_headers, sample_whiskeys):
        """User A cannot upload to User B's rating."""
        # Create a rating as testuser2
        rate_resp = client.post(
            f"/whiskeys/{sample_whiskeys[0].id}/rate",
            json={"score": 4.0, "notes": "My rating"},
            headers=second_auth_headers,
        )
        rating_id = rate_resp.json()["rating"]["id"]
        # Try to upload as testuser
        resp = client.post(
            f"/ratings/{rating_id}/image",
            files={"file": ("test.jpg", b"fake", "image/jpeg")},
            headers=auth_headers,
        )
        assert resp.status_code == 403


class TestJournalTimeline:
    def test_journal_empty(self, client, auth_headers):
        resp = client.get("/journal/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["entries"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    def test_journal_with_ratings(self, client, sample_user_with_ratings, sample_whiskeys):
        resp = client.get("/journal/me", headers=sample_user_with_ratings)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["entries"]) >= 1
        entry = data["entries"][0]
        assert "id" in entry
        assert "score" in entry
        assert "whiskey" in entry
        assert entry["whiskey"]["name"] is not None

    def test_journal_unauthenticated(self, client):
        resp = client.get("/journal/me")
        assert resp.status_code == 401

    def test_journal_pagination(self, client, sample_user_with_ratings):
        resp = client.get("/journal/me", params={"limit": 1}, headers=sample_user_with_ratings)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) <= 1
