"""Tests for the chat router — SSE streaming and helper functions."""

import json
from unittest.mock import patch, MagicMock


class TestChatEndpoint:
    def test_returns_sse_stream(self, client, auth_headers):
        with patch("app.routers.chat.agent_graph") as mock_graph:
            # Mock astream_events to be an empty async generator
            async def _empty_stream(*a, **kw):
                return
                yield  # make it an async generator

            mock_graph.astream_events = _empty_stream
            resp = client.post(
                "/chat/",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    def test_anonymous(self, client):
        with patch("app.routers.chat.agent_graph") as mock_graph:
            async def _empty_stream(*a, **kw):
                return
                yield

            mock_graph.astream_events = _empty_stream
            resp = client.post(
                "/chat/",
                json={"messages": [{"role": "user", "content": "Hi"}]},
            )
        assert resp.status_code == 200


class TestSummarizeEndpoint:
    def test_skips_anonymous(self, client):
        resp = client.post(
            "/chat/summarize",
            json={
                "messages": [{"role": "user", "content": f"msg {i}"} for i in range(5)],
                "session_id": "test-session",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped"

    def test_skips_short_convo(self, client, auth_headers):
        resp = client.post(
            "/chat/summarize",
            json={
                "messages": [{"role": "user", "content": "short"}],
                "session_id": "test-session",
            },
            headers=auth_headers,
        )
        assert resp.json()["status"] == "skipped"

    def test_accepts_valid(self, client, auth_headers):
        resp = client.post(
            "/chat/summarize",
            json={
                "messages": [{"role": "user", "content": f"msg {i}"} for i in range(5)],
                "session_id": "test-session",
            },
            headers=auth_headers,
        )
        assert resp.json()["status"] == "accepted"


class TestHelperFunctions:
    def test_sse_format(self):
        from app.routers.chat import _sse
        result = _sse({"type": "text", "content": "hello"})
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        parsed = json.loads(result[6:].strip())
        assert parsed["type"] == "text"
        assert parsed["content"] == "hello"

    def test_resolve_user_id_bearer(self):
        from app.routers.chat import _resolve_user_id
        with patch("app.routers.chat._decode_token", return_value="testuser"):
            uid = _resolve_user_id("Bearer fake_token", None)
        assert uid == "testuser"

    def test_resolve_user_id_body_token(self):
        from app.routers.chat import _resolve_user_id
        with patch("app.routers.chat._decode_token", return_value="testuser"):
            uid = _resolve_user_id(None, "body_token")
        assert uid == "testuser"

    def test_resolve_user_id_anonymous(self):
        from app.routers.chat import _resolve_user_id
        uid = _resolve_user_id(None, None)
        assert uid.startswith("anon_")

    def test_emit_gen_ui_map(self):
        from app.routers.chat import _emit_gen_ui_events
        events = _emit_gen_ui_events({"stores": [{"name": "Shop"}], "center": {"lat": 0, "lng": 0}})
        assert len(events) >= 1
        parsed = json.loads(events[0][6:].strip())
        assert parsed["type"] == "map"

    def test_emit_gen_ui_whiskeys(self):
        from app.routers.chat import _emit_gen_ui_events
        events = _emit_gen_ui_events({"whiskeys": [{"id": 1, "name": "Test"}]})
        assert len(events) >= 1
        parsed = json.loads(events[0][6:].strip())
        assert parsed["type"] == "whiskeys"

    def test_emit_gen_ui_comparison(self):
        from app.routers.chat import _emit_gen_ui_events
        events = _emit_gen_ui_events({
            "ui_type": "comparison",
            "whiskeys": [{"id": 1}],
            "rows": [{"label": "ABV"}],
        })
        types = [json.loads(e[6:].strip())["type"] for e in events]
        assert "comparison" in types
