"""FastAPI route handlers for the Ruoxue agent.

Phase 2: adds ASR endpoint and TTS audio + viseme events.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from pathlib import Path

from backend.agent.agent_graph import run_agent_stream
from backend.agent.chroma_memory import chroma_memory
from backend.agent.memory import memory
from backend.asr.asr_service import asr_service
from backend.tts.tts_service import synthesize_with_word_boundary
from backend.tts.viseme_mapper import text_to_viseme_sequence
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

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


# Parenthetical action descriptions like (笑), (憋笑中), （叹气）, （内心欢呼）etc.
# LLMs occasionally emit these as emotional asides or stage directions.
# Previous approach used a keyword list but LLMs invent new phrases outside the list.
# Now: remove ALL content inside Chinese/English parentheses — broad and reliable.
_ACTION_TAG_RE = re.compile(r'[（(][^）)]*[）)]')


def _strip_action_tags(text: str) -> str:
    """Remove ALL parenthetical content (Chinese or English brackets)."""
    return _ACTION_TAG_RE.sub('', text).strip()


# Symbols that TTS cannot pronounce or sound bad — strip before synthesis.
_SYMBOL_RE = re.compile(
    r'[\*#_`\|>～〜☆★♪♫♥❤→←↑↓▼▲◆◇◎●○◉◎※〓]'
    r'|(?:\*\*|__|~~|--|——)'
)


def _strip_symbols(text: str) -> str:
    """Remove markdown formatting and symbols that TTS cannot pronounce."""
    return _SYMBOL_RE.sub('', text).strip()


def _wav_duration(data: bytes) -> int:
    """Calculate WAV audio duration in milliseconds from header.

    Falls back to estimating from byte size if header is invalid.
    """
    import struct
    try:
        # WAV header: RIFF ... fmt  -> sample_rate at byte 24, byte_rate at byte 28
        if len(data) >= 44 and data[:4] == b"RIFF":
            sample_rate: int = struct.unpack_from("<I", data, 24)[0]
            data_size: int = struct.unpack_from("<I", data, 40)[0]
            channels: int = struct.unpack_from("<H", data, 22)[0]
            bits_per_sample: int = struct.unpack_from("<H", data, 34)[0]
            bytes_per_second = sample_rate * channels * (bits_per_sample // 8)
            if bytes_per_second > 0:
                return int(data_size * 1000 / bytes_per_second)
    except Exception:
        pass
    # Fallback: estimate from raw size (24kHz 16-bit mono = 48000 bytes/s)
    return int(len(data) * 1000 / 48000)




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
            async for sse_event in run_agent_stream(req.text, history):
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
                        yield "event: token\n"
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

                    # Synthesize with ChatTTS (offline, no proxy needed)
                    # ChatTTS does not provide word boundaries — viseme uses
                    # fixed per-character timing estimation (30ms/char)
                    wav_bytes, _word_boundaries = await synthesize_with_word_boundary(
                        tts_text
                    )
                    audio_b64 = base64.b64encode(wav_bytes).decode("ascii")

                    # Calculate audio duration from WAV header
                    audio_duration_ms = _wav_duration(wav_bytes)
                    print(f"[TTS] duration={audio_duration_ms}ms, text_len={len(tts_text)}")

                    yield "event: audio\n"
                    yield f"data: {json.dumps({'base64': audio_b64, 'format': 'wav', 'duration_ms': audio_duration_ms}, ensure_ascii=False)}\n"
                    yield "\n"

                    # Generate viseme sequence with fixed per-character timing
                    viseme_seq = text_to_viseme_sequence(
                        tts_text,
                        ms_per_char=30.0,
                        char_durations=None,
                    )
                    if viseme_seq and audio_duration_ms > 0:
                        raw_last_ms = viseme_seq[-1]["time_ms"]
                        if raw_last_ms > 0:
                            scale = audio_duration_ms / raw_last_ms
                            for v in viseme_seq:
                                v["time_ms"] = round(v["time_ms"] * scale, 1)

                    yield "event: viseme\n"
                    yield f"data: {json.dumps(viseme_seq, ensure_ascii=False)}\n"
                    yield "\n"
                except Exception as tts_err:
                    # TTS failure is non-fatal; conversation continues
                    print(f"[TTS] synthesis failed: {tts_err}")

            # Save to short-term memory
            memory.add_user_message(req.session_id, req.text)
            if full_reply.strip():
                memory.add_assistant_message(req.session_id, full_reply)
                # Also store in Chroma long-term memory (fire-and-forget)
                try:
                    chroma_memory.store_turn(req.session_id, req.text, full_reply)
                except Exception as e:
                    print(f"[Chroma] store_turn error: {e}")

            yield "event: done\n"
            yield "data: {}\n"
            yield "\n"

        except Exception as exc:
            yield "event: error\n"
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
        raise HTTPException(500, f"ASR failed: {exc}") from exc


@router.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """File upload endpoint — saves to uploads/ and returns path for read_file tool.

    Max 20 MB. Supported: text, PDF, documents.
    """
    max_size = 20 * 1024 * 1024  # 20 MB

    # Sanitize: extract only the base filename (prevents path traversal)
    filename = file.filename or "unknown"
    safe_name = Path(filename).name  # strips directory components
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in "._- ()")
    if not safe_name.strip():
        raise HTTPException(400, "Invalid filename")

    # Ensure uploads directory exists
    upload_dir = Path(__file__).resolve().parent / "uploads"
    upload_dir.mkdir(exist_ok=True)

    # Read file, checking size
    contents = await file.read()
    if len(contents) > max_size:
        raise HTTPException(400, f"File too large (max {max_size // 1024 // 1024} MB)")

    # Write to disk
    filepath = upload_dir / safe_name
    counter = 1
    stem, ext = os.path.splitext(safe_name)
    while filepath.exists():
        filepath = upload_dir / f"{stem}_{counter}{ext}"
        counter += 1

    filepath.write_bytes(contents)

    return {
        "path": str(filepath),
        "filename": filepath.name,
        "size": len(contents),
    }


@router.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint with ASR status."""
    return HealthResponse(
        status="ok",
        version="0.2.0",
        llm_available=True,
        asr_available=asr_service.is_loaded,
    )
