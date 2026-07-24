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
from backend.tts.tts_service import synthesize_with_word_boundary
from backend.tts.viseme_mapper import text_to_viseme_sequence
from backend.asr.asr_service import asr_service

router = APIRouter()


# --- Helpers ---

import re

_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols extended-A
    "\U00002600-\U000026FF"  # misc symbols
    "\U00002702-\U000027B0"  # dingbats
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0001F3FB-\U0001F3FF"  # skin tone modifiers
    "\U0000200D"             # zero-width joiner
    "\U00002328-\U0000232A"  # keyboard symbols
    "\U000023CF"
    "\U000023E9-\U000023F3"
    "\U000023F8-\U000023FA"
    "\U000024C2"
    "\U000025AA-\U000025AB"
    "\U000025B6"
    "\U000025C0"
    "\U000025FB-\U000025FE"
    "\U00002934-\U00002935"
    "\U00002B05-\U00002B07"
    "\U00002B1B-\U00002B1C"
    "\U00002B50"
    "\U00002B55"
    "\U00003030"
    "\U0000303D"
    "\U00003297"
    "\U00003299"
    "]+",
    flags=re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    """Remove emoji characters before TTS synthesis."""
    return _EMOJI_RE.sub("", text).strip()


# Parenthetical action descriptions like (笑), (憋笑中), （叹气）etc.
# LLMs occasionally emit these despite prompt instructions — strip them.
_ACTION_KEYWORDS = '|'.join([
    '笑', '哭', '气', '惊', '叹', '怒', '愁', '忧', '虑',
    '思', '想', '惑', '默', '羞', '愧', '尬', '急',
    '慌', '怕', '厌', '烦', '恨', '爱', '喜', '乐', '哀',
    '憋', '捂', '扶', '摇', '点', '偷', '苦', '微', '大',
    '哈', '嘻', '嘿', '呵', '呜', '啊', '哦', '嗯', '咦',
    '认真', '严肃', '无奈', '担心', '骄傲', '得意', '感动',
    '欣慰', '尴尬', '害羞', '脸红', '沉默', '摇头', '点头',
    '疑惑', '困惑', '不解', '无语', '生气', '惊讶', '吃惊',
    '思考', '叹气', '叹息', '感慨', '哭泣', '偷笑', '苦笑',
    '微笑', '大笑', '憋笑', '哈哈', '嘻嘻', '嘿嘿', '扶额',
    '捂脸',
])
_ACTION_TAG_RE = re.compile(r'[（(](?:' + _ACTION_KEYWORDS + r')[^）)]{0,4}[）)]')


def _strip_action_tags(text: str) -> str:
    """Remove parenthetical action/emotion descriptions like (憋笑中) or （叹气）."""
    return _ACTION_TAG_RE.sub('', text).strip()


# Symbols that TTS cannot pronounce or sound bad — strip before synthesis.
_SYMBOL_RE = re.compile(
    r'[\*#_`\|>～〜☆★♪♫♥❤→←↑↓▼▲◆◇◎●○◉◎※〓]'
    r'|(?:\*\*|__|~~|--|——)'
)


def _strip_symbols(text: str) -> str:
    """Remove markdown formatting and symbols that TTS cannot pronounce."""
    return _SYMBOL_RE.sub('', text).strip()


def _mp3_duration(data: bytes) -> int:
    """Calculate MP3 audio duration in milliseconds from frame count."""
    frame_count = 0
    i = 0
    n = len(data)
    while i < n - 1:
        if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
            frame_count += 1
            i += 200
        else:
            i += 1
    if frame_count == 0:
        return int(len(data) * 8 * 1000 / 48000)
    return int(frame_count * 1152 * 1000 / 44100)




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
                    text = data.get("text", "")
                    full_reply += text  # raw for memory
                    # Strip action tags + emoji + symbols from display text
                    clean = _strip_action_tags(text)
                    clean = _strip_emoji(clean)
                    clean = _strip_symbols(clean)
                    if clean:
                        yield f"event: token\n"
                        yield f"data: {json.dumps({'text': clean}, ensure_ascii=False)}\n"
                        yield "\n"
                    continue

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
                    # Strip non-speakable content: emoji, action tags, symbols
                    tts_text = _strip_emoji(full_reply)
                    tts_text = _strip_action_tags(tts_text)
                    tts_text = _strip_symbols(tts_text)
                    if not tts_text:
                        tts_text = full_reply  # fallback if everything was stripped

                    # Synthesize with word boundaries for precise viseme timing
                    mp3_bytes, word_boundaries = await synthesize_with_word_boundary(
                        tts_text, proxy=TTS_PROXY
                    )
                    audio_b64 = base64.b64encode(mp3_bytes).decode("ascii")

                    # Calculate precise audio duration from word boundaries (100ns → ms)
                    audio_duration_ms = 0
                    if word_boundaries:
                        last = word_boundaries[-1]
                        audio_duration_ms = int((last["offset"] + last["duration"]) / 10000)
                    if audio_duration_ms <= 0:
                        audio_duration_ms = _mp3_duration(mp3_bytes)  # fallback
                    print(f"[TTS] duration={audio_duration_ms}ms, words={len(word_boundaries)}, text_len={len(tts_text)}")

                    yield f"event: audio\n"
                    yield f"data: {json.dumps({'base64': audio_b64, 'format': 'mp3', 'duration_ms': audio_duration_ms}, ensure_ascii=False)}\n"
                    yield "\n"

                    # Generate viseme sequence, scale to real audio duration
                    viseme_seq = text_to_viseme_sequence(tts_text)
                    if viseme_seq and audio_duration_ms > 0:
                        raw_last_ms = viseme_seq[-1]["time_ms"]
                        if raw_last_ms > 0:
                            scale = audio_duration_ms / raw_last_ms
                            for v in viseme_seq:
                                v["time_ms"] = round(v["time_ms"] * scale, 1)

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
