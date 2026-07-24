"""FastAPI route handlers for the Ruoxue agent.

Phase 2: adds ASR endpoint and TTS audio + viseme events.
"""

from __future__ import annotations

import base64
import json
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agent.emotional_agent import generate_reply
from backend.agent.memory import memory
from backend.config import TTS_PROXY
from backend.tts.tts_service import synthesize
from backend.tts.viseme_mapper import text_to_viseme_sequence
from backend.asr.asr_service import asr_service

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
    asr_available: bool


# --- Routes ---

@router.post("/api/chat")
async def chat(req: ChatRequest):
    """SSE streaming chat endpoint with TTS audio and viseme events.

    Returns text/event-stream with events:
        emotion, token*, audio, viseme, done
    """
    history = memory.get_history(req.session_id)

    async def event_stream():
        full_reply = ""
        has_error = False
        try:
            async for sse_event in generate_reply(req.text, history):
                event = sse_event.event
                data = sse_event.data

                if event == "token":
                    full_reply += data.get("text", "")

                # Intercept "done" from emotional_agent — we send it later
                # after TTS audio + viseme events
                if event == "done":
                    continue

                if event == "error":
                    has_error = True

                yield f"event: {event}\n"
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n"
                yield "\n"

            # ---- Phase 2: TTS + Viseme after LLM reply is complete ----
            if not has_error and full_reply.strip():
                try:
                    # Synthesize speech
                    mp3_bytes = await synthesize(full_reply, proxy=TTS_PROXY)
                    audio_b64 = base64.b64encode(mp3_bytes).decode("ascii")

                    yield f"event: audio\n"
                    yield f"data: {json.dumps({'base64': audio_b64, 'format': 'mp3', 'duration_ms': 0}, ensure_ascii=False)}\n"
                    yield "\n"

                    # Generate viseme sequence
                    viseme_seq = text_to_viseme_sequence(full_reply)

                    yield f"event: viseme\n"
                    yield f"data: {json.dumps(viseme_seq, ensure_ascii=False)}\n"
                    yield "\n"
                except Exception as tts_err:
                    # TTS failure is non-fatal; conversation continues
                    print(f"[TTS] synthesis failed: {tts_err}")

            # Save to memory after successful generation
            memory.add_user_message(req.session_id, req.text)
            if full_reply.strip():
                memory.add_assistant_message(req.session_id, full_reply)

            yield f"event: done\n"
            yield f"data: {{}}\n"
            yield "\n"

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


@router.post("/api/asr")
async def asr_recognize(file: UploadFile = File(...)):
    """Speech recognition endpoint.

    Accepts WAV audio file (16-bit PCM, mono, 16kHz preferred).

    Returns:
        JSON with text, language, emotion.
    """
    if not file.filename or not file.filename.lower().endswith(".wav"):
        raise HTTPException(400, "Only WAV files are supported")

    wav_bytes = await file.read()
    if len(wav_bytes) < 44:  # WAV header is 44 bytes minimum
        raise HTTPException(400, "Audio too short or invalid WAV format")

    try:
        result = asr_service.recognize(wav_bytes)
        return result
    except Exception as exc:
        raise HTTPException(500, f"ASR failed: {exc}")


@router.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint with ASR status."""
    return HealthResponse(
        status="ok",
        version="0.2.0",
        llm_available=True,
        asr_available=asr_service.is_loaded,
    )
