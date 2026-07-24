"""FastAPI route handlers for the Ruoxue agent."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agent.emotional_agent import generate_reply
from backend.agent.memory import memory

router = APIRouter()


# --- Request/Response schemas ---

class ChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="User message")
    session_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex[:12],
        description="Session identifier for multi-turn conversation",
    )


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_available: bool


# --- Routes ---

@router.post("/api/chat")
async def chat(req: ChatRequest):
    """SSE streaming chat endpoint.

    Returns text/event-stream with events: emotion, token, done.
    """
    history = memory.get_history(req.session_id)

    async def event_stream():
        full_reply = ""
        try:
            async for sse_event in generate_reply(req.text, history):
                event = sse_event.event
                data = sse_event.data

                if event == "token":
                    full_reply += data.get("text", "")

                yield f"event: {event}\n"
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n"
                yield "\n"

            # Save to memory after successful generation
            memory.add_user_message(req.session_id, req.text)
            if full_reply.strip():
                memory.add_assistant_message(req.session_id, full_reply)

        except Exception as exc:
            yield f"event: error\n"
            yield f"data: {json.dumps({'message': str(exc), 'code': 500}, ensure_ascii=False)}\n"
            yield "\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        llm_available=True,
    )
