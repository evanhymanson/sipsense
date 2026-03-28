"""Tests for streak system."""

from datetime import date, timedelta

import pytest
from app.streaks import record_daily_activity
from app import models


class TestRecordDailyActivity:
    def test_first_activity_creates_streak(self, db_session):
        """First activity → streak of 1."""
        user = models.User(username="streakuser", email="s@test.com", hashed_password="x")
        db_session.add(user)
        db_session.commit()

        result = record_daily_activity("streakuser", db_session)
        assert result["current_streak"] == 1
        assert result["longest_streak"] == 1
        assert result["is_new_day"] is True

    def test_same_day_noop(self, db_session):
        """Same day activity → no-op."""
        user = models.User(username="streakuser2", email="s2@test.com", hashed_password="x")
        db_session.add(user)
        db_session.commit()

        result1 = record_daily_activity("streakuser2", db_session)
        assert result1["is_new_day"] is True

        result2 = record_daily_activity("streakuser2", db_session)
        assert result2["is_new_day"] is False
        assert result2["current_streak"] == 1

    def test_consecutive_day_increments(self, db_session):
        """Yesterday activity + today → streak increments."""
        user = models.User(username="streakuser3", email="s3@test.com", hashed_password="x")
        db_session.add(user)
        db_session.commit()

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        streak = models.UserStreak(
            user_id="streakuser3",
            current_streak=3,
            longest_streak=5,
            last_active_date=yesterday,
        )
        db_session.add(streak)
        db_session.commit()

        result = record_daily_activity("streakuser3", db_session)
        assert result["current_streak"] == 4
        assert result["longest_streak"] == 5
        assert result["is_new_day"] is True

    def test_gap_resets_streak(self, db_session):
        """2+ day gap → streak resets to 1."""
        user = models.User(username="streakuser4", email="s4@test.com", hashed_password="x")
        db_session.add(user)
        db_session.commit()

        old_date = (date.today() - timedelta(days=3)).isoformat()
        streak = models.UserStreak(
            user_id="streakuser4",
            current_streak=10,
            longest_streak=10,
            last_active_date=old_date,
        )
        db_session.add(streak)
        db_session.commit()

        result = record_daily_activity("streakuser4", db_session)
        assert result["current_streak"] == 1
        assert result["longest_streak"] == 10


class TestStreakEndpoints:
    def test_get_streak(self, client, auth_headers):
        resp = client.get("/streaks/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "current_streak" in data

    def test_heartbeat(self, client, auth_headers):
        resp = client.post("/streaks/heartbeat", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "current_streak" in data
