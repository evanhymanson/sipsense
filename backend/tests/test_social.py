"""Tests for social endpoints: comments, follows, toasts, search, profiles."""


class TestCheckInComments:
    def test_create_comment(self, client, auth_headers, second_auth_headers, testuser2_rating_id):
        resp = client.post(
            f"/ratings/{testuser2_rating_id}/comment",
            json={"text": "Great pour!"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["text"] == "Great pour!"
        assert data["user_id"] == "testuser"
        assert data["rating_id"] == testuser2_rating_id
        assert "id" in data
        assert "created_at" in data

    def test_create_comment_generates_alert(self, client, auth_headers, second_auth_headers, testuser2_rating_id):
        client.post(
            f"/ratings/{testuser2_rating_id}/comment",
            json={"text": "Nice one!"},
            headers=auth_headers,
        )
        # Check testuser2 has an alert
        resp = client.get("/watchlist/alerts", headers=second_auth_headers)
        assert resp.status_code == 200
        alerts = resp.json()
        comment_alerts = [a for a in alerts if a.get("alert_type") == "comment"]
        assert len(comment_alerts) >= 1
        assert comment_alerts[0]["from_username"] == "testuser"

    def test_comment_on_own_rating_no_alert(self, client, auth_headers, testuser_rating_id):
        client.post(
            f"/ratings/{testuser_rating_id}/comment",
            json={"text": "My own comment"},
            headers=auth_headers,
        )
        resp = client.get("/watchlist/alerts", headers=auth_headers)
        alerts = resp.json()
        comment_alerts = [a for a in alerts if a.get("alert_type") == "comment"]
        assert len(comment_alerts) == 0

    def test_list_comments_empty(self, client, testuser_rating_id):
        resp = client.get(f"/ratings/{testuser_rating_id}/comments")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_comments_returns_comments(self, client, auth_headers, testuser_rating_id):
        client.post(
            f"/ratings/{testuser_rating_id}/comment",
            json={"text": "Comment 1"},
            headers=auth_headers,
        )
        client.post(
            f"/ratings/{testuser_rating_id}/comment",
            json={"text": "Comment 2"},
            headers=auth_headers,
        )
        resp = client.get(f"/ratings/{testuser_rating_id}/comments")
        assert resp.status_code == 200
        comments = resp.json()
        assert len(comments) == 2

    def test_list_comments_pagination(self, client, auth_headers, testuser_rating_id):
        for i in range(3):
            client.post(
                f"/ratings/{testuser_rating_id}/comment",
                json={"text": f"Comment {i}"},
                headers=auth_headers,
            )
        resp = client.get(f"/ratings/{testuser_rating_id}/comments?skip=1&limit=1")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_delete_own_comment(self, client, auth_headers, testuser_rating_id):
        resp = client.post(
            f"/ratings/{testuser_rating_id}/comment",
            json={"text": "To delete"},
            headers=auth_headers,
        )
        comment_id = resp.json()["id"]
        resp = client.delete(f"/ratings/comments/{comment_id}", headers=auth_headers)
        assert resp.status_code == 204

    def test_delete_removes_comment(self, client, auth_headers, testuser_rating_id):
        resp = client.post(
            f"/ratings/{testuser_rating_id}/comment",
            json={"text": "Will be gone"},
            headers=auth_headers,
        )
        comment_id = resp.json()["id"]
        client.delete(f"/ratings/comments/{comment_id}", headers=auth_headers)
        resp = client.get(f"/ratings/{testuser_rating_id}/comments")
        ids = [c["id"] for c in resp.json()]
        assert comment_id not in ids

    def test_create_comment_unauthenticated(self, client, testuser_rating_id):
        resp = client.post(
            f"/ratings/{testuser_rating_id}/comment",
            json={"text": "No auth"},
        )
        assert resp.status_code == 401

    def test_create_comment_invalid_rating(self, client, auth_headers):
        resp = client.post(
            "/ratings/99999/comment",
            json={"text": "No rating"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_create_comment_empty_text(self, client, auth_headers, testuser_rating_id):
        resp = client.post(
            f"/ratings/{testuser_rating_id}/comment",
            json={"text": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_create_comment_text_too_long(self, client, auth_headers, testuser_rating_id):
        resp = client.post(
            f"/ratings/{testuser_rating_id}/comment",
            json={"text": "x" * 501},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_delete_other_users_comment(self, client, auth_headers, second_auth_headers, testuser_rating_id):
        resp = client.post(
            f"/ratings/{testuser_rating_id}/comment",
            json={"text": "My comment"},
            headers=auth_headers,
        )
        comment_id = resp.json()["id"]
        resp = client.delete(f"/ratings/comments/{comment_id}", headers=second_auth_headers)
        assert resp.status_code == 403

    def test_delete_nonexistent_comment(self, client, auth_headers):
        resp = client.delete("/ratings/comments/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestFollowSystem:
    def test_follow_user(self, client, auth_headers, second_auth_headers):
        resp = client.post("/users/testuser2/follow", headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["status"] == "following"

    def test_follow_creates_alert(self, client, auth_headers, second_auth_headers):
        client.post("/users/testuser2/follow", headers=auth_headers)
        resp = client.get("/watchlist/alerts", headers=second_auth_headers)
        alerts = resp.json()
        follow_alerts = [a for a in alerts if a.get("alert_type") == "follow"]
        assert len(follow_alerts) >= 1

    def test_follow_idempotent(self, client, auth_headers, second_auth_headers):
        client.post("/users/testuser2/follow", headers=auth_headers)
        resp = client.post("/users/testuser2/follow", headers=auth_headers)
        assert resp.json()["status"] == "already_following"

    def test_unfollow_user(self, client, auth_headers, second_auth_headers):
        client.post("/users/testuser2/follow", headers=auth_headers)
        resp = client.delete("/users/testuser2/follow", headers=auth_headers)
        assert resp.status_code == 204

    def test_unfollow_when_not_following(self, client, auth_headers, second_auth_headers):
        resp = client.delete("/users/testuser2/follow", headers=auth_headers)
        assert resp.status_code == 204

    def test_get_followers(self, client, auth_headers, second_auth_headers):
        client.post("/users/testuser2/follow", headers=auth_headers)
        resp = client.get("/users/testuser2/followers", headers=auth_headers)
        assert resp.status_code == 200
        usernames = [u["username"] for u in resp.json()]
        assert "testuser" in usernames

    def test_get_followers_empty(self, client, auth_headers):
        resp = client.get("/users/testuser/followers", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_following(self, client, auth_headers, second_auth_headers):
        client.post("/users/testuser2/follow", headers=auth_headers)
        resp = client.get("/users/testuser/following", headers=auth_headers)
        assert resp.status_code == 200
        usernames = [u["username"] for u in resp.json()]
        assert "testuser2" in usernames

    def test_get_following_empty(self, client, auth_headers):
        resp = client.get("/users/testuser/following", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_followers_response_shape(self, client, auth_headers, second_auth_headers):
        client.post("/users/testuser2/follow", headers=auth_headers)
        resp = client.get("/users/testuser2/followers", headers=auth_headers)
        data = resp.json()
        assert len(data) >= 1
        user = data[0]
        assert "username" in user
        assert "total_checkins" in user
        assert "follower_count" in user
        assert "is_following" in user

    def test_follow_self(self, client, auth_headers):
        resp = client.post("/users/testuser/follow", headers=auth_headers)
        assert resp.status_code == 400

    def test_follow_nonexistent_user(self, client, auth_headers):
        resp = client.post("/users/ghostuser/follow", headers=auth_headers)
        assert resp.status_code == 404

    def test_follow_unauthenticated(self, client, second_auth_headers):
        resp = client.post("/users/testuser2/follow")
        assert resp.status_code == 401


class TestSuggestedUsers:
    def test_suggested_returns_results(self, client, both_users_with_ratings):
        headers1, _ = both_users_with_ratings
        resp = client.get("/users/suggested", headers=headers1)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["match_score"] >= 0

    def test_suggested_excludes_followed(self, client, both_users_with_ratings):
        headers1, _ = both_users_with_ratings
        client.post("/users/testuser2/follow", headers=headers1)
        resp = client.get("/users/suggested", headers=headers1)
        usernames = [u["username"] for u in resp.json()]
        assert "testuser2" not in usernames

    def test_suggested_custom_limit(self, client, both_users_with_ratings):
        headers1, _ = both_users_with_ratings
        resp = client.get("/users/suggested?limit=1", headers=headers1)
        assert resp.status_code == 200
        assert len(resp.json()) <= 1

    def test_suggested_result_shape(self, client, both_users_with_ratings):
        headers1, _ = both_users_with_ratings
        resp = client.get("/users/suggested", headers=headers1)
        data = resp.json()
        if len(data) > 0:
            item = data[0]
            assert "username" in item
            assert "total_checkins" in item
            assert "follower_count" in item
            assert "is_following" in item
            assert "match_score" in item
            assert "reason" in item

    def test_suggested_no_ratings_empty(self, client, auth_headers):
        resp = client.get("/users/suggested", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_suggested_unauthenticated(self, client):
        resp = client.get("/users/suggested")
        assert resp.status_code == 401


class TestUserSearch:
    def test_search_finds_user(self, client, auth_headers, second_auth_headers):
        resp = client.get("/users/search?q=testuser", headers=auth_headers)
        assert resp.status_code == 200
        usernames = [u["username"] for u in resp.json()]
        assert "testuser" in usernames

    def test_search_partial_match(self, client, auth_headers, second_auth_headers):
        resp = client.get("/users/search?q=test", headers=auth_headers)
        usernames = [u["username"] for u in resp.json()]
        assert "testuser" in usernames
        assert "testuser2" in usernames

    def test_search_no_results(self, client, auth_headers):
        resp = client.get("/users/search?q=zzzzzzz", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_pagination(self, client, auth_headers, second_auth_headers):
        resp = client.get("/users/search?q=test&skip=0&limit=1", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_search_result_shape(self, client, auth_headers):
        resp = client.get("/users/search?q=testuser", headers=auth_headers)
        data = resp.json()
        assert len(data) >= 1
        user = data[0]
        assert "username" in user
        assert "total_checkins" in user
        assert "follower_count" in user
        assert "is_following" in user

    def test_search_unauthenticated_ok(self, client, auth_headers):
        # search works without auth (get_optional_user)
        resp = client.get("/users/search?q=testuser")
        assert resp.status_code == 200


class TestPublicProfile:
    def test_profile_basic_fields(self, client, auth_headers):
        resp = client.get("/users/testuser/profile", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"
        assert "member_since" in data
        assert "total_checkins" in data
        assert "unique_whiskeys" in data
        assert "follower_count" in data
        assert "following_count" in data

    def test_profile_with_ratings(self, client, sample_user_with_ratings):
        resp = client.get("/users/testuser/profile", headers=sample_user_with_ratings)
        data = resp.json()
        assert data["total_checkins"] >= 3
        assert data["avg_score"] is not None
        assert len(data["top_categories"]) > 0

    def test_profile_recent_checkins_shape(self, client, sample_user_with_ratings):
        resp = client.get("/users/testuser/profile", headers=sample_user_with_ratings)
        data = resp.json()
        assert "recent_checkins" in data
        assert len(data["recent_checkins"]) > 0
        item = data["recent_checkins"][0]
        assert "rating" in item
        assert "whiskey" in item
        assert "username" in item
        assert "toast_count" in item
        assert "comment_count" in item

    def test_profile_follower_counts(self, client, auth_headers, second_auth_headers):
        client.post("/users/testuser/follow", headers=second_auth_headers)
        resp = client.get("/users/testuser/profile", headers=auth_headers)
        data = resp.json()
        assert data["follower_count"] >= 1

    def test_profile_is_following_flag(self, client, auth_headers, second_auth_headers):
        client.post("/users/testuser2/follow", headers=auth_headers)
        resp = client.get("/users/testuser2/profile", headers=auth_headers)
        assert resp.json()["is_following"] is True

    def test_profile_self_is_following_false(self, client, auth_headers):
        resp = client.get("/users/testuser/profile", headers=auth_headers)
        assert resp.json()["is_following"] is False

    def test_profile_nonexistent_user(self, client, auth_headers):
        resp = client.get("/users/ghostuser/profile", headers=auth_headers)
        assert resp.status_code == 404

    def test_profile_unauthenticated_ok(self, client, auth_headers):
        # Profile endpoint uses get_optional_user — should work without auth
        resp = client.get("/users/testuser/profile")
        assert resp.status_code == 200
        assert resp.json()["is_following"] is False


class TestToasts:
    def test_add_toast(self, client, auth_headers, second_auth_headers, testuser2_rating_id):
        resp = client.post(f"/ratings/{testuser2_rating_id}/toast", headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == "testuser"
        assert data["rating_id"] == testuser2_rating_id

    def test_toast_idempotent(self, client, auth_headers, second_auth_headers, testuser2_rating_id):
        client.post(f"/ratings/{testuser2_rating_id}/toast", headers=auth_headers)
        resp = client.post(f"/ratings/{testuser2_rating_id}/toast", headers=auth_headers)
        # Returns existing toast, not error
        assert resp.status_code in (200, 201)

    def test_toast_own_checkin_blocked(self, client, auth_headers, testuser_rating_id):
        resp = client.post(f"/ratings/{testuser_rating_id}/toast", headers=auth_headers)
        assert resp.status_code == 400

    def test_remove_toast(self, client, auth_headers, second_auth_headers, testuser2_rating_id):
        client.post(f"/ratings/{testuser2_rating_id}/toast", headers=auth_headers)
        resp = client.delete(f"/ratings/{testuser2_rating_id}/toast", headers=auth_headers)
        assert resp.status_code == 204

    def test_remove_nonexistent_toast(self, client, auth_headers, testuser2_rating_id):
        resp = client.delete(f"/ratings/{testuser2_rating_id}/toast", headers=auth_headers)
        assert resp.status_code == 404

    def test_toast_unauthenticated(self, client, testuser_rating_id):
        resp = client.post(f"/ratings/{testuser_rating_id}/toast")
        assert resp.status_code == 401

    def test_toast_nonexistent_rating(self, client, auth_headers):
        resp = client.post("/ratings/99999/toast", headers=auth_headers)
        assert resp.status_code == 404
