"""Tests for push notification subscription management."""

import pytest
from app import models


class TestPushStatus:
    def test_get_status_unauthenticated(self, client):
        resp = client.get("/push/status")
        assert resp.status_code == 401

    def test_get_status_default(self, client, auth_headers):
        resp = client.get("/push/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["subscribed"] is False
        assert data["subscription_count"] == 0
        assert "vapid_public_key" in data


class TestPushSubscribe:
    SUB_PAYLOAD = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/test-123",
        "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-T4",
        "auth": "tBHItJI5svbpC7cZ0Iaso3A",
        "user_agent": "TestBrowser/1.0",
    }

    def test_subscribe(self, client, auth_headers, db_session):
        resp = client.post("/push/subscribe", headers=auth_headers, json=self.SUB_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert data["endpoint"] == self.SUB_PAYLOAD["endpoint"]
        assert data["is_active"] is True

        # Verify in DB
        sub = db_session.query(models.PushSubscription).filter(
            models.PushSubscription.endpoint == self.SUB_PAYLOAD["endpoint"]
        ).first()
        assert sub is not None
        assert sub.is_active is True

    def test_subscribe_reactivates(self, client, auth_headers, db_session):
        """Re-subscribing with same endpoint reactivates instead of creating duplicate."""
        client.post("/push/subscribe", headers=auth_headers, json=self.SUB_PAYLOAD)
        # Unsubscribe
        client.request("DELETE", "/push/subscribe", headers=auth_headers, json=self.SUB_PAYLOAD)
        # Re-subscribe
        resp = client.post("/push/subscribe", headers=auth_headers, json=self.SUB_PAYLOAD)
        assert resp.status_code == 201
        assert resp.json()["is_active"] is True

        # Should be only 1 row, not 2
        count = db_session.query(models.PushSubscription).filter(
            models.PushSubscription.endpoint == self.SUB_PAYLOAD["endpoint"]
        ).count()
        assert count == 1

    def test_unsubscribe(self, client, auth_headers, db_session):
        client.post("/push/subscribe", headers=auth_headers, json=self.SUB_PAYLOAD)
        resp = client.request("DELETE", "/push/subscribe", headers=auth_headers, json=self.SUB_PAYLOAD)
        assert resp.status_code == 204

        sub = db_session.query(models.PushSubscription).filter(
            models.PushSubscription.endpoint == self.SUB_PAYLOAD["endpoint"]
        ).first()
        assert sub.is_active is False

    def test_status_after_subscribe(self, client, auth_headers):
        client.post("/push/subscribe", headers=auth_headers, json=self.SUB_PAYLOAD)
        resp = client.get("/push/status", headers=auth_headers)
        data = resp.json()
        assert data["subscribed"] is True
        assert data["subscription_count"] == 1


class TestPushPreferences:
    def test_push_prefs_in_email_prefs(self, client, auth_headers):
        """Push preference fields are included in email preferences response."""
        resp = client.get("/email-preferences/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "push_social" in data
        assert "push_price_drop" in data
        assert "push_streak" in data
        assert "push_weekly" in data
        # Defaults are True
        assert data["push_social"] is True

    def test_update_push_prefs(self, client, auth_headers):
        resp = client.put("/email-preferences/", headers=auth_headers, json={
            "push_social": False,
        })
        assert resp.status_code == 200
        assert resp.json()["push_social"] is False

        # Verify persisted
        resp2 = client.get("/email-preferences/", headers=auth_headers)
        assert resp2.json()["push_social"] is False
