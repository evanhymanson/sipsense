"""Tests for the videos router — short-form video feed, engagement, comments."""


class TestVideoFeed:
    def test_feed_empty(self, client):
        resp = client.get("/videos/feed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["has_more"] is False

    def test_feed_returns_videos(self, client, sample_video):
        resp = client.get("/videos/feed")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    def test_feed_response_shape(self, client, sample_video):
        item = client.get("/videos/feed").json()["items"][0]
        assert "id" in item
        assert "user_id" in item
        assert "title" in item
        assert "video_url" in item
        assert "toast_count" in item
        assert "comment_count" in item

    def test_feed_pagination(self, client, sample_video):
        resp = client.get("/videos/feed?skip=1&limit=10")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_feed_unauthenticated(self, client, sample_video):
        resp = client.get("/videos/feed")
        assert resp.status_code == 200


class TestGetVideo:
    def test_get_video(self, client, sample_video):
        resp = client.get(f"/videos/{sample_video.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sample_video.id

    def test_not_found(self, client):
        resp = client.get("/videos/99999")
        assert resp.status_code == 404

    def test_response_shape(self, client, sample_video):
        data = client.get(f"/videos/{sample_video.id}").json()
        assert "toast_count" in data
        assert "comment_count" in data
        assert "user_toasted" in data


class TestDeleteVideo:
    def test_delete_own(self, client, auth_headers, sample_video):
        resp = client.delete(f"/videos/{sample_video.id}", headers=auth_headers)
        assert resp.status_code == 204

    def test_deleted_video_hidden(self, client, auth_headers, sample_video):
        client.delete(f"/videos/{sample_video.id}", headers=auth_headers)
        resp = client.get(f"/videos/{sample_video.id}")
        assert resp.status_code == 404

    def test_delete_other_users_video(self, client, second_auth_headers, sample_video):
        resp = client.delete(f"/videos/{sample_video.id}", headers=second_auth_headers)
        assert resp.status_code == 403

    def test_delete_nonexistent(self, client, auth_headers):
        resp = client.delete("/videos/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_unauthenticated(self, client, sample_video):
        resp = client.delete(f"/videos/{sample_video.id}")
        assert resp.status_code == 401


class TestVideoView:
    def test_record_view(self, client, sample_video):
        resp = client.post(f"/videos/{sample_video.id}/view")
        assert resp.status_code == 200
        assert resp.json()["view_count"] >= 1

    def test_view_not_found(self, client):
        resp = client.post("/videos/99999/view")
        assert resp.status_code == 404


class TestVideoToast:
    def test_toast(self, client, auth_headers, sample_video):
        resp = client.post(f"/videos/{sample_video.id}/toast", headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["status"] == "toasted"

    def test_toast_idempotent(self, client, auth_headers, sample_video):
        client.post(f"/videos/{sample_video.id}/toast", headers=auth_headers)
        resp = client.post(f"/videos/{sample_video.id}/toast", headers=auth_headers)
        assert resp.json()["status"] == "already_toasted"

    def test_untoast(self, client, auth_headers, sample_video):
        client.post(f"/videos/{sample_video.id}/toast", headers=auth_headers)
        resp = client.delete(f"/videos/{sample_video.id}/toast", headers=auth_headers)
        assert resp.status_code == 204

    def test_untoast_nonexistent(self, client, auth_headers, sample_video):
        resp = client.delete(f"/videos/{sample_video.id}/toast", headers=auth_headers)
        assert resp.status_code == 404

    def test_toast_nonexistent_video(self, client, auth_headers):
        resp = client.post("/videos/99999/toast", headers=auth_headers)
        assert resp.status_code == 404

    def test_toast_unauthenticated(self, client, sample_video):
        resp = client.post(f"/videos/{sample_video.id}/toast")
        assert resp.status_code == 401


class TestVideoComments:
    def test_add_comment(self, client, auth_headers, sample_video):
        resp = client.post(
            f"/videos/{sample_video.id}/comment",
            json={"text": "Great video!"},
            headers=auth_headers,
        )
        assert resp.status_code == 201

    def test_add_comment_response_shape(self, client, auth_headers, sample_video):
        resp = client.post(
            f"/videos/{sample_video.id}/comment",
            json={"text": "Nice!"},
            headers=auth_headers,
        )
        data = resp.json()
        assert data["user_id"] == "testuser"
        assert data["video_id"] == sample_video.id
        assert data["text"] == "Nice!"

    def test_get_comments_empty(self, client, sample_video):
        resp = client.get(f"/videos/{sample_video.id}/comments")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_comments_returns_data(self, client, auth_headers, sample_video):
        client.post(
            f"/videos/{sample_video.id}/comment",
            json={"text": "Comment 1"},
            headers=auth_headers,
        )
        resp = client.get(f"/videos/{sample_video.id}/comments")
        assert len(resp.json()) == 1

    def test_delete_own_comment(self, client, auth_headers, sample_video):
        resp = client.post(
            f"/videos/{sample_video.id}/comment",
            json={"text": "To delete"},
            headers=auth_headers,
        )
        comment_id = resp.json()["id"]
        resp = client.delete(f"/videos/comments/{comment_id}", headers=auth_headers)
        assert resp.status_code == 204

    def test_delete_other_users_comment(self, client, auth_headers, second_auth_headers, sample_video):
        resp = client.post(
            f"/videos/{sample_video.id}/comment",
            json={"text": "Not yours"},
            headers=auth_headers,
        )
        comment_id = resp.json()["id"]
        resp = client.delete(f"/videos/comments/{comment_id}", headers=second_auth_headers)
        assert resp.status_code == 403

    def test_add_comment_unauthenticated(self, client, sample_video):
        resp = client.post(
            f"/videos/{sample_video.id}/comment",
            json={"text": "Anon"},
        )
        assert resp.status_code == 401

    def test_add_comment_nonexistent_video(self, client, auth_headers):
        resp = client.post(
            "/videos/99999/comment",
            json={"text": "No video"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestUserVideos:
    def test_get_user_videos(self, client, sample_video):
        resp = client.get("/videos/user/testuser")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    def test_get_user_videos_empty(self, client, auth_headers):
        resp = client.get("/videos/user/nobody")
        assert resp.status_code == 200
        assert resp.json()["items"] == []


class TestWhiskeyVideos:
    def test_get_whiskey_videos(self, client, sample_video, sample_whiskeys):
        resp = client.get(f"/videos/whiskey/{sample_whiskeys[0].id}")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    def test_get_whiskey_videos_empty(self, client, sample_whiskeys):
        resp = client.get(f"/videos/whiskey/{sample_whiskeys[1].id}")
        assert resp.status_code == 200
        assert resp.json()["items"] == []
