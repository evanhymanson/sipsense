"""Tests for email system: password reset, email preferences."""

import pytest
from app import models


class TestPasswordReset:
    def test_forgot_password_returns_200(self, client):
        """Always returns 200 regardless of whether email exists."""
        resp = client.post("/auth/forgot-password", json={"email": "nobody@test.com"})
        assert resp.status_code == 200
        assert "reset link" in resp.json()["status"].lower()

    def test_forgot_password_creates_token(self, client, auth_headers, db_session):
        """For existing user, creates a PasswordResetToken."""
        user = db_session.query(models.User).filter(models.User.username == "testuser").first()
        assert user is not None

        resp = client.post("/auth/forgot-password", json={"email": user.email})
        assert resp.status_code == 200

        tokens = db_session.query(models.PasswordResetToken).filter(
            models.PasswordResetToken.user_id == user.username
        ).all()
        assert len(tokens) >= 1

    def test_reset_with_invalid_token(self, client):
        """Invalid token → 400."""
        resp = client.post("/auth/reset-password", json={
            "token": "invalid-token",
            "new_password": "NewPass123!",
        })
        assert resp.status_code == 400

    def test_full_reset_flow(self, client, auth_headers, db_session):
        """Forgot → reset → login with new password works."""
        import hashlib, secrets
        from datetime import datetime, timedelta, timezone

        user = db_session.query(models.User).filter(models.User.username == "testuser").first()
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        reset = models.PasswordResetToken(
            user_id=user.username,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(reset)
        db_session.commit()

        resp = client.post("/auth/reset-password", json={
            "token": token,
            "new_password": "BrandNewPass1!",
        })
        assert resp.status_code == 200

        # Login with new password
        login_resp = client.post("/auth/login", json={
            "username": "testuser",
            "password": "BrandNewPass1!",
        })
        assert login_resp.status_code == 200


class TestEmailPreferences:
    def test_get_prefs(self, client, auth_headers):
        resp = client.get("/email-preferences/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "weekly_digest" in data

    def test_update_prefs(self, client, auth_headers):
        resp = client.put("/email-preferences/", headers=auth_headers, json={
            "weekly_digest": False,
        })
        assert resp.status_code == 200

        # Verify update
        resp2 = client.get("/email-preferences/", headers=auth_headers)
        assert resp2.json()["weekly_digest"] is False
