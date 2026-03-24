"""
SipSense Chat Router

POST /chat/ — accepts a message history and streams the agent response via SSE.

SSE event types:
  {"type": "text",     "content": "..."}              — token-by-token text delta
  {"type": "whiskeys", "whiskeys": [...]}              — whiskey cards from a tool result
  {"type": "map",      "stores": [...], "center": {}}  — store map from find_nearby_stores
  {"type": "comparison", "whiskeys": [...], "rows": []} — side-by-side comparison
  {"type": "flight",   "story": "...", "whiskeys": []}  — tasting flight visualization
  {"type": "palate_profile", "profile": {...}}          — palate radar chart
  {"type": "thinking"}                                   — agent is processing
  {"type": "tool_start", "tool": "search_whiskeys"}      — tool execution started
  {"type": "done"}                                      — stream complete
  {"type": "error",    "message": "..."}                — on exception
"""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..database import SessionLocal
from .. import models
from ..ml.agent import agent_graph
from ..auth import decode_access_token as _decode_token
from ..track import track_action
from ..analytics_constants import ACTION_CHAT_MESSAGE

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str    # "user" or "assistant"
    content: str


class UserLocation(BaseModel):
    lat: float
    lng: float


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: Optional[str] = None
    token: Optional[str] = None
    user_location: Optional[UserLocation] = None


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _load_user_memory_sync(user_id: str) -> str:
    """Return a plain-English summary of the user's remembered preferences, or empty string."""
    db = SessionLocal()
    try:
        mem = db.query(models.UserMemory).filter(models.UserMemory.user_id == user_id).first()
        if not mem or not mem.preferences or mem.preferences in ("{}", ""):
            return ""
        prefs = json.loads(mem.preferences)
        parts = []
        for key, val in prefs.items():
            if isinstance(val, list):
                parts.append(f"{key.title()}: {', '.join(val)}")
            elif val:
                parts.append(f"{key.title()}: {val}")
        return " | ".join(parts)
    finally:
        db.close()


async def _load_user_memory(user_id: str) -> str:
    """Async wrapper — runs the DB query in a thread to avoid blocking the event loop."""
    return await asyncio.to_thread(_load_user_memory_sync, user_id)


# ── Generative UI type mapping ────────────────────────────────────────────────
# Maps the ui_type field from tool results to SSE event types.

_UI_TYPE_MAP = {
    "comparison": "comparison",
    "flight": "flight",
    "palate_profile": "palate_profile",
    "price_alternatives": "price_alternatives",
}


def _emit_gen_ui_events(parsed: dict):
    """Yield SSE events for generative UI based on tool result structure."""
    events = []

    ui_type = parsed.get("ui_type")

    # Map-specific event for stores
    if parsed.get("stores") and parsed.get("center"):
        events.append(_sse({
            "type": "map",
            "stores": parsed["stores"],
            "center": parsed["center"],
        }))

    # Comparison event
    elif ui_type == "comparison" and parsed.get("rows"):
        events.append(_sse({
            "type": "comparison",
            "whiskeys": parsed.get("whiskeys", []),
            "rows": parsed["rows"],
        }))

    # Flight event
    elif ui_type == "flight" and parsed.get("story"):
        events.append(_sse({
            "type": "flight",
            "story": parsed["story"],
            "whiskeys": parsed.get("whiskeys", []),
        }))

    # Palate profile event
    elif ui_type == "palate_profile" and parsed.get("profile"):
        events.append(_sse({
            "type": "palate_profile",
            "profile": parsed["profile"],
        }))

    # Price alternatives event
    elif ui_type == "price_alternatives" and parsed.get("reference"):
        events.append(_sse({
            "type": "price_alternatives",
            "reference": parsed["reference"],
            "whiskeys": parsed.get("whiskeys", []),
        }))

    # Always emit whiskey cards if present (for clickable navigation)
    if parsed.get("whiskeys") and not events:
        # Only emit plain whiskeys if no specialized UI was emitted
        events.append(_sse({"type": "whiskeys", "whiskeys": parsed["whiskeys"]}))
    elif parsed.get("whiskeys") and events:
        # Specialized UI was emitted — still send whiskey cards for navigation
        events.append(_sse({"type": "whiskeys", "whiskeys": parsed["whiskeys"]}))

    return events


async def _stream_agent(messages: list[ChatMessage], user_id: str, user_location: dict | None = None):
    """
    Async generator that runs the LangGraph agent and yields SSE strings.

    Event sources:
    - on_chat_model_stream  →  text token deltas
    - on_tool_end           →  generative UI events (maps, comparisons, flights, etc.)
                                + whiskey card data
    """
    lc_messages = [{"role": m.role, "content": m.content} for m in messages]
    user_memory = await _load_user_memory(user_id)

    configurable = {"user_id": user_id, "user_memory": user_memory}
    if user_location:
        configurable["user_lat"] = user_location["lat"]
        configurable["user_lng"] = user_location["lng"]

    # Immediate feedback so the frontend can show a thinking indicator
    yield _sse({"type": "thinking"})

    try:
        async for event in agent_graph.astream_events(
            {"messages": lc_messages},
            version="v2",
            config={"configurable": configurable},
        ):
            event_type = event.get("event")

            # ── Text token streaming ──────────────────────────────────────────
            if event_type == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk is None:
                    continue

                content = chunk.content

                if isinstance(content, str):
                    if content:
                        yield _sse({"type": "text", "content": content})

                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text = block.get("text", "")
                                if text:
                                    yield _sse({"type": "text", "content": text})

            # ── Tool start → show activity indicator ──────────────────────────
            elif event_type == "on_tool_start":
                tool_name = event.get("name", "")
                if tool_name:
                    yield _sse({"type": "tool_start", "tool": tool_name})

            # ── Tool result → generative UI events ────────────────────────────
            elif event_type == "on_tool_end":
                tool_output = event["data"].get("output", "")
                # LangGraph >=1.0 returns ToolMessage objects, not raw strings
                if hasattr(tool_output, "content"):
                    tool_output = tool_output.content
                try:
                    parsed = json.loads(tool_output)
                    if isinstance(parsed, dict):
                        for sse_event in _emit_gen_ui_events(parsed):
                            yield sse_event
                except (json.JSONDecodeError, TypeError):
                    pass

        yield _sse({"type": "done"})

    except Exception as exc:
        import logging, traceback
        logging.getLogger(__name__).exception("Chat stream error")
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        short = f"{type(exc).__name__}: {exc}"
        yield _sse({"type": "error", "message": short})
        yield _sse({"type": "done"})


@router.post("/")
async def chat(request: ChatRequest, authorization: str | None = Header(None)):
    # Extract user from Authorization header, fall back to body token
    import uuid
    user_id = f"anon_{uuid.uuid4().hex[:12]}"
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif request.token:
        token = request.token
    if token:
        username = _decode_token(token)
        if username:
            user_id = username

    # Track chat message for authenticated users
    if not user_id.startswith("anon_"):
        last_msg = request.messages[-1].content if request.messages else ""
        db = SessionLocal()
        try:
            track_action(db, user_id, ACTION_CHAT_MESSAGE,
                         detail={"message_length": len(last_msg)})
            db.commit()
        finally:
            db.close()

    user_loc = None
    if request.user_location:
        user_loc = {"lat": request.user_location.lat, "lng": request.user_location.lng}

    return StreamingResponse(
        _stream_agent(request.messages, user_id, user_loc),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        },
    )
