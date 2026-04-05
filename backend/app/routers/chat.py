"""
SipSense Chat Router

POST /chat/ — accepts a message history and streams the agent response via SSE.
POST /chat/summarize — generates a conversation summary for cross-session memory.

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
import logging
import os
from typing import Optional

from openai import OpenAI
from fastapi import APIRouter, BackgroundTasks, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..database import SessionLocal
from .. import models
from ..ml.agent import agent_graph
from ..auth import decode_access_token as _decode_token
from ..track import track_action
from ..analytics_constants import ACTION_CHAT_MESSAGE, ACTION_CHAT_TOOL_CALL
from ..rate_limit import chat_rate_limiter

logger = logging.getLogger(__name__)

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


class SummarizeRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: str
    token: Optional[str] = None


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# ── User memory loading ──────────────────────────────────────────────────────


def _load_user_memory_sync(user_id: str) -> dict:
    """Return user preferences (str) and recent conversation summaries (list of dicts)."""
    db = SessionLocal()
    try:
        # ── Preferences ──
        prefs_text = ""
        mem = db.query(models.UserMemory).filter(models.UserMemory.user_id == user_id).first()
        if mem and mem.preferences and mem.preferences not in ("{}", ""):
            prefs = json.loads(mem.preferences)
            lines = []
            for key, val in prefs.items():
                if isinstance(val, list):
                    lines.append(f"  {key.title()}: {', '.join(val)}")
                elif val:
                    lines.append(f"  {key.title()}: {val}")
            prefs_text = "\n".join(lines)

        # ── Conversation summaries (last 7) ──
        summaries = (
            db.query(models.ConversationSummary)
            .filter(models.ConversationSummary.user_id == user_id)
            .order_by(models.ConversationSummary.created_at.desc())
            .limit(7)
            .all()
        )
        summary_dicts = [
            {"date": s.created_at.strftime("%b %d"), "summary": s.summary}
            for s in reversed(summaries)  # chronological order
        ]

        return {"preferences": prefs_text, "summaries": summary_dicts}
    finally:
        db.close()


async def _load_user_memory(user_id: str) -> dict:
    """Async wrapper — runs the DB query in a thread to avoid blocking the event loop."""
    return await asyncio.to_thread(_load_user_memory_sync, user_id)


# ── Conversation summarization ────────────────────────────────────────────────

_SUMMARIZE_PROMPT = """\
You are analyzing a whiskey app conversation between a user and an AI whiskey guide.

1. SUMMARIZE the conversation in 2-3 sentences: what the user asked about, \
what was recommended, any outcomes or decisions.

2. EXTRACT any durable user preferences revealed (things they like/dislike, \
budget, style, experience level, name, etc.). Only extract genuinely new, \
durable preferences — not transient requests like "show me bourbons."

Return valid JSON only:
{
  "summary": "...",
  "topic_tags": "comma,separated,tags",
  "new_preferences": [
    {"key": "likes", "value": "smoky scotch"},
    {"key": "budget", "value": "under $60"}
  ]
}"""


def _summarize_and_extract_sync(
    messages: list[dict], session_id: str, user_id: str,
) -> None:
    """Generate a conversation summary and extract missed preferences. Runs in background."""
    api_key = os.environ.get("TOGETHER_API_KEY", "")
    if not api_key:
        logger.warning("No TOGETHER_API_KEY — skipping conversation summary")
        return

    # Build a compact transcript for the summarizer
    transcript_lines = []
    for m in messages:
        role_label = "User" if m["role"] == "user" else "Assistant"
        content = m["content"][:800] if len(m["content"]) > 800 else m["content"]
        transcript_lines.append(f"{role_label}: {content}")
    transcript = "\n".join(transcript_lines)

    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.together.xyz/v1",
        )
        response = client.chat.completions.create(
            model=os.environ.get("SUMMARIZER_MODEL", "Qwen/Qwen3.5-9B"),
            max_tokens=500,
            messages=[
                {"role": "user", "content": f"{_SUMMARIZE_PROMPT}\n\n<conversation>\n{transcript}\n</conversation>"}
            ],
            timeout=30.0,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        result = json.loads(raw)
    except Exception:
        logger.exception("Failed to generate conversation summary")
        return

    db = SessionLocal()
    try:
        # ── Save summary ──
        summary_text = result.get("summary", "").strip()
        if summary_text:
            existing = (
                db.query(models.ConversationSummary)
                .filter(
                    models.ConversationSummary.user_id == user_id,
                    models.ConversationSummary.session_id == session_id,
                )
                .first()
            )
            if not existing:
                db.add(models.ConversationSummary(
                    user_id=user_id,
                    session_id=session_id,
                    summary=summary_text[:1000],
                    topic_tags=result.get("topic_tags", "")[:200],
                    message_count=len(messages),
                ))

        # ── Merge extracted preferences ──
        new_prefs = result.get("new_preferences", [])
        if new_prefs:
            mem = db.query(models.UserMemory).filter(models.UserMemory.user_id == user_id).first()
            if not mem:
                mem = models.UserMemory(user_id=user_id, preferences="{}")
                db.add(mem)
                db.flush()

            prefs = json.loads(mem.preferences or "{}")
            for p in new_prefs:
                key = str(p.get("key", "")).strip().lower()[:50]
                value = str(p.get("value", "")).replace("\n", " ").strip()[:500]
                if not key or not value:
                    continue
                if key not in prefs and len(prefs) >= 50:
                    break
                if key in ("likes", "dislikes"):
                    lst = prefs.get(key, [])
                    if value not in lst:
                        lst.append(value)
                    prefs[key] = lst
                else:
                    prefs[key] = value
            mem.preferences = json.dumps(prefs)

        db.commit()
    except Exception:
        logger.exception("Failed to save conversation summary")
        db.rollback()
    finally:
        db.close()


# ── Generative UI type mapping ────────────────────────────────────────────────

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

    if parsed.get("stores") and parsed.get("center"):
        events.append(_sse({
            "type": "map",
            "stores": parsed["stores"],
            "center": parsed["center"],
        }))

    elif ui_type == "comparison" and parsed.get("rows"):
        events.append(_sse({
            "type": "comparison",
            "whiskeys": parsed.get("whiskeys", []),
            "rows": parsed["rows"],
        }))

    elif ui_type == "flight" and parsed.get("story"):
        events.append(_sse({
            "type": "flight",
            "story": parsed["story"],
            "whiskeys": parsed.get("whiskeys", []),
        }))

    elif ui_type == "palate_profile" and parsed.get("profile"):
        events.append(_sse({
            "type": "palate_profile",
            "profile": parsed["profile"],
        }))

    elif ui_type == "price_alternatives" and parsed.get("reference"):
        events.append(_sse({
            "type": "price_alternatives",
            "reference": parsed["reference"],
            "whiskeys": parsed.get("whiskeys", []),
        }))

    if parsed.get("whiskeys") and not events:
        events.append(_sse({"type": "whiskeys", "whiskeys": parsed["whiskeys"]}))
    elif parsed.get("whiskeys") and events:
        events.append(_sse({"type": "whiskeys", "whiskeys": parsed["whiskeys"]}))

    return events


_REC_TOOLS = frozenset({
    "search_whiskeys", "get_recommendations", "get_similar_whiskeys",
    "get_top_rated", "find_value_picks", "get_by_occasion",
    "build_tasting_flight", "compare_whiskeys", "find_gift_recommendation",
    "find_cheaper_alternatives",
})


def _track_tool_call_bg(user_id: str, tool_name: str, whiskey_ids: list[int]):
    """Fire-and-forget background tracking for chat tool calls."""
    db = SessionLocal()
    try:
        track_action(
            db, user_id, ACTION_CHAT_TOOL_CALL,
            detail={"tool": tool_name, "whiskey_ids": whiskey_ids[:20]},
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


async def _stream_agent(messages: list[ChatMessage], user_id: str, user_location: dict | None = None):
    """
    Async generator that runs the LangGraph agent and yields SSE strings.

    Event sources:
    - on_chat_model_stream  ->  text token deltas
    - on_tool_end           ->  generative UI events (maps, comparisons, flights, etc.)
                                + whiskey card data
    """
    # Yield thinking immediately so the user sees feedback before DB queries
    yield _sse({"type": "thinking"})

    lc_messages = [{"role": m.role, "content": m.content} for m in messages]
    memory = await _load_user_memory(user_id)

    configurable = {
        "user_id": user_id,
        "user_memory": memory["preferences"],
        "conversation_summaries": memory["summaries"],
    }
    if user_location:
        configurable["user_lat"] = user_location["lat"]
        configurable["user_lng"] = user_location["lng"]

    try:
        async for event in agent_graph.astream_events(
            {"messages": lc_messages},
            version="v2",
            config={"configurable": configurable},
        ):
            event_type = event.get("event")

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

            elif event_type == "on_tool_start":
                tool_name = event.get("name", "")
                if tool_name:
                    yield _sse({"type": "tool_start", "tool": tool_name})

            elif event_type == "on_tool_end":
                tool_name = event.get("name", "")
                tool_output = event["data"].get("output", "")
                if hasattr(tool_output, "content"):
                    tool_output = tool_output.content
                try:
                    parsed = json.loads(tool_output)
                    if isinstance(parsed, dict):
                        for sse_event in _emit_gen_ui_events(parsed):
                            yield sse_event

                        # Track recommendation tool calls for conversion funnel
                        if tool_name in _REC_TOOLS and not user_id.startswith("anon_"):
                            whiskey_ids = [
                                w.get("id") for w in parsed.get("whiskeys", [])
                                if isinstance(w, dict) and w.get("id")
                            ]
                            asyncio.create_task(
                                asyncio.to_thread(_track_tool_call_bg, user_id, tool_name, whiskey_ids)
                            )
                except (json.JSONDecodeError, TypeError):
                    pass

        yield _sse({"type": "done"})

    except Exception as exc:
        logger.exception("Chat stream error")
        short = f"{type(exc).__name__}: {exc}"
        yield _sse({"type": "error", "message": short})
        yield _sse({"type": "done"})


# ── Extract user_id from token ────────────────────────────────────────────────


def _resolve_user_id(authorization: str | None, token_body: str | None) -> str:
    """Extract username from JWT token, or generate an anonymous ID."""
    import uuid
    user_id = f"anon_{uuid.uuid4().hex[:12]}"
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif token_body:
        token = token_body
    if token:
        username = _decode_token(token)
        if username:
            user_id = username
    return user_id


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/")
async def chat(request: ChatRequest, authorization: str | None = Header(None)):
    user_id = _resolve_user_id(authorization, request.token)
    chat_rate_limiter.check(user_id, not user_id.startswith("anon_"))

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


@router.post("/summarize")
async def summarize_conversation(
    request: SummarizeRequest,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
):
    """Generate a conversation summary for cross-session memory.

    Called by the frontend when the user clears the chat or navigates away.
    Runs summarization in a background task so the response is instant.
    """
    user_id = _resolve_user_id(authorization, request.token)

    if user_id.startswith("anon_") or len(request.messages) < 4:
        return {"status": "skipped"}

    messages_dicts = [{"role": m.role, "content": m.content} for m in request.messages]
    background_tasks.add_task(
        _summarize_and_extract_sync, messages_dicts, request.session_id, user_id,
    )
    return {"status": "accepted"}
