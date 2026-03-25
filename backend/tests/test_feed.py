"""Tests for the activity feed endpoint."""


class TestFeedEndpoint:
    def test_feed_returns_items(self, client, sample_user_with_ratings):
        resp = client.get("/feed/", headers=sample_user_with_ratings)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) > 0

    def test_feed_empty_db(self, client):
        resp = client.get("/feed/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["has_more"] is False

    def test_feed_item_shape(self, client, sample_user_with_ratings):
        resp = client.get("/feed/", headers=sample_user_with_ratings)
        item = resp.json()["items"][0]
        assert "rating" in item
        assert "whiskey" in item
        assert "username" in item
        assert "toast_count" in item
        assert "user_toasted" in item
        assert "comment_count" in item

    def test_feed_comment_count_populated(self, client, auth_headers, second_auth_headers, testuser2_rating_id):
        # Add 2 comments to testuser2's rating
        client.post(
            f"/ratings/{testuser2_rating_id}/comment",
            json={"text": "Comment 1"},
            headers=auth_headers,
        )
        client.post(
            f"/ratings/{testuser2_rating_id}/comment",
            json={"text": "Comment 2"},
            headers=auth_headers,
        )
        resp = client.get("/feed/", headers=auth_headers)
        items = resp.json()["items"]
        # Find the item for testuser2's rating
        target = [i for i in items if i["rating"]["id"] == testuser2_rating_id]
        assert len(target) == 1
        assert target[0]["comment_count"] == 2

    def test_feed_toast_count_populated(self, client, auth_headers, second_auth_headers, testuser2_rating_id):
        client.post(f"/ratings/{testuser2_rating_id}/toast", headers=auth_headers)
        resp = client.get("/feed/", headers=auth_headers)
        items = resp.json()["items"]
        target = [i for i in items if i["rating"]["id"] == testuser2_rating_id]
        assert len(target) == 1
        assert target[0]["toast_count"] >= 1

    def test_feed_user_toasted_flag(self, client, auth_headers, second_auth_headers, testuser2_rating_id):
        client.post(f"/ratings/{testuser2_rating_id}/toast", headers=auth_headers)
        resp = client.get("/feed/", headers=auth_headers)
        items = resp.json()["items"]
        target = [i for i in items if i["rating"]["id"] == testuser2_rating_id]
        assert target[0]["user_toasted"] is True

    def test_feed_pagination(self, client, sample_user_with_ratings):
        resp = client.get("/feed/?skip=0&limit=2", headers=sample_user_with_ratings)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) <= 2

    def test_feed_has_more_flag(self, client, sample_user_with_ratings):
        # sample_user_with_ratings creates 3 ratings, limit=2 should set has_more
        resp = client.get("/feed/?limit=2", headers=sample_user_with_ratings)
        assert resp.json()["has_more"] is True

    def test_feed_no_more(self, client, sample_user_with_ratings):
        resp = client.get("/feed/?limit=50", headers=sample_user_with_ratings)
        assert resp.json()["has_more"] is False

    def test_feed_category_filter(self, client, sample_user_with_ratings, sample_whiskeys):
        resp = client.get("/feed/?category=bourbon", headers=sample_user_with_ratings)
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["whiskey"]["category"].lower() == "bourbon"

    def test_feed_unauthenticated_ok(self, client, sample_user_with_ratings):
        # Feed uses get_optional_user — works without auth
        resp = client.get("/feed/")
        assert resp.status_code == 200

    def test_feed_unauthenticated_toasted_false(self, client, sample_user_with_ratings):
        resp = client.get("/feed/")
        items = resp.json()["items"]
        for item in items:
            assert item["user_toasted"] is False

    def test_feed_following_only(self, client, auth_headers, second_auth_headers, sample_whiskeys):
        # testuser2 rates a whiskey
        client.post(
            f"/whiskeys/{sample_whiskeys[3].id}/rate",
            json={"score": 4.5},
            headers=second_auth_headers,
        )
        # testuser follows testuser2
        client.post("/users/testuser2/follow", headers=auth_headers)
        resp = client.get("/feed/?following_only=true", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        usernames = {i["username"] for i in items}
        # Should only contain testuser and testuser2 (followed)
        assert usernames <= {"testuser", "testuser2"}

    def test_feed_following_only_includes_self(self, client, sample_user_with_ratings):
        resp = client.get("/feed/?following_only=true", headers=sample_user_with_ratings)
        items = resp.json()["items"]
        # Even with no follows, own ratings should appear
        assert len(items) > 0
        assert all(i["username"] == "testuser" for i in items)

    def test_feed_ordered_by_date_desc(self, client, sample_user_with_ratings):
        resp = client.get("/feed/", headers=sample_user_with_ratings)
        items = resp.json()["items"]
        if len(items) >= 2:
            dates = [i["rating"]["created_at"] for i in items]
            assert dates == sorted(dates, reverse=True)
