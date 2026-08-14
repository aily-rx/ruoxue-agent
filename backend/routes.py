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
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map
    "\U0001f1e0-\U0001f1ff"  # flags
    "\U0001f900-\U0001f9ff"  # supplemental symbols
    "\U0001fa00-\U0001fa6f"  # chess symbols
    "\U0001fa70-\U0001faff"  # symbols extended-A
    "\U00002600-\U000026ff"  # misc symbols
    "\U00002702-\U000027b0"  # dingbats
    "\U0000fe00-\U0000fe0f"  # variation selectors
    "\U0001f3fb-\U0001f3ff"  # skin tone modifiers
    "\U0000200d"  # zero-width joiner
    "\U00002328-\U0000232a"  # keyboard symbols
    "\U000023cf"
    "\U000023e9-\U000023f3"
    "\U000023f8-\U000023fa"
    "\U000024c2"
    "\U000025aa-\U000025ab"
    "\U000025b6"
    "\U000025c0"
    "\U000025fb-\U000025fe"
    "\U00002934-\U00002935"
    "\U00002b05-\U00002b07"
    "\U00002b1b-\U00002b1c"
    "\U00002b50"
    "\U00002b55"
    "\U00003030"
    "\U0000303d"
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
_ACTION_TAG_RE = re.compile(r"[（(][^）)]*[）)]")


def _strip_action_tags(text: str) -> str:
    """Remove ALL parenthetical content (Chinese or English brackets)."""
    return _ACTION_TAG_RE.sub("", text).strip()


# Symbols that TTS cannot pronounce or sound bad — strip before synthesis.
_SYMBOL_RE = re.compile(r"[\*#_`\|>～〜☆★♪♫♥❤→←↑↓▼▲◆◇◎●○◉◎※〓]" r"|(?:\*\*|__|~~|--|——)")


def _strip_symbols(text: str) -> str:
    """Remove markdown formatting and symbols that TTS cannot pronounce."""
    return _SYMBOL_RE.sub("", text).strip()


# 敏感输出过滤（输出护栏）: 防止回复泄露密钥类信息（简单版 demo 防护）
_SENSITIVE_RE = re.compile(
    r"(password|api[_-]?key|secret|access[_-]?token)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


def _filter_sensitive(text: str) -> str:
    """拦截回复中的敏感模式, 替换为 [已过滤]。"""
    return _SENSITIVE_RE.sub("[已过滤]", text)


def _boundaries_to_char_durations(
    word_boundaries: list[dict],
) -> list[float]:
    """Convert Edge TTS word boundaries to per-character durations in ms.

    Uses len(wb_text) — ALL characters in the boundary word (including
    punctuation) — to distribute duration evenly. This matches the total
    character count of tts_text because Edge TTS processes the exact same
    text and emits one boundary per word.

    Args:
        word_boundaries: List of {"offset": int, "duration": int, "text": str}
                         from Edge TTS, offset/duration in 100ns units.

    Returns:
        List of millisecond durations, one per character in tts_text.
    """
    if not word_boundaries:
        return []
    char_durations: list[float] = []
    for wb in word_boundaries:
        wb_text = wb.get("text", "")
        wb_duration_ms = wb["duration"] / 10000.0  # 100ns → ms
        char_count = len(wb_text)
        if char_count > 0:
            dur_per_char = wb_duration_ms / char_count
            for _ in range(char_count):
                char_durations.append(dur_per_char)
    return char_durations


def _mp3_duration(data: bytes) -> int:
    """Calculate MP3 audio duration in milliseconds from frame count.

    Scans for MPEG audio frame sync markers (0xFFE0) and multiplies
    by 1152 samples/frame ÷ 44100 Hz. Falls back to byte-size estimate.
    """
    frame_count = 0
    i = 0
    n = len(data)
    while i < n - 1:
        if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
            frame_count += 1
            i += 200  # skip ahead (typical frame ~417 bytes, 200 is safe lower bound)
        else:
            i += 1
    if frame_count == 0:
        return int(len(data) * 8 * 1000 / 48000)  # fallback: 48 kbps
    return int(frame_count * 1152 * 1000 / 44100)


def _wav_duration(data: bytes) -> int:
    """Calculate WAV audio duration in milliseconds from header.

    Handles standard PCM WAV as well as pyttsx3/SAPI5 output which may
    have non-standard chunk ordering. Falls back to estimating from byte
    size and a set of common sample rates if header is invalid.
    """
    import struct

    try:
        if len(data) >= 44 and data[:4] == b"RIFF":
            # Parse fmt  chunk to find audio format details
            # Standard WAV: "fmt " at offset 12, but pyttsx3 may have
            # extra chunks before fmt. Search for "fmt " chunk.
            offset = 12
            while 0 < offset < len(data) - 8:
                chunk_id = data[offset : offset + 4]
                chunk_size: int = struct.unpack_from("<I", data, offset + 4)[0]
                if chunk_size <= 0 or offset + 8 + chunk_size > len(data):
                    break  # malformed chunk
                if chunk_id == b"fmt ":
                    fmt_offset = offset + 8
                    channels: int = struct.unpack_from("<H", data, fmt_offset + 2)[0]
                    sample_rate: int = struct.unpack_from("<I", data, fmt_offset + 4)[0]
                    bits_per_sample: int = struct.unpack_from("<H", data, fmt_offset + 14)[0]
                    # Find "data" chunk to get actual audio data size
                    data_offset = offset + 8 + chunk_size
                    while data_offset < len(data) - 8:
                        dchunk_id = data[data_offset : data_offset + 4]
                        dchunk_size: int = struct.unpack_from("<I", data, data_offset + 4)[0]
                        if dchunk_size <= 0 or data_offset + 8 + dchunk_size > len(data):
                            break  # malformed chunk
                        if dchunk_id == b"data":
                            data_size = dchunk_size
                            bytes_per_second = sample_rate * channels * (bits_per_sample // 8)
                            if bytes_per_second > 0:
                                return int(data_size * 1000 / bytes_per_second)
                            break
                        data_offset += 8 + dchunk_size
                    break
                offset += 8 + chunk_size

            # Fallback: try standard offsets (works for simple PCM WAV)
            if len(data) >= 44:
                sample_rate2: int = struct.unpack_from("<I", data, 24)[0]
                data_size2: int = struct.unpack_from("<I", data, 40)[0]
                channels2: int = struct.unpack_from("<H", data, 22)[0]
                bits2: int = struct.unpack_from("<H", data, 34)[0]
                bps = sample_rate2 * channels2 * (bits2 // 8)
                if bps > 0:
                    return int(data_size2 * 1000 / bps)
    except Exception:
        pass

    # Fallback: estimate from raw size against common sample rates.
    # pyttsx3/SAPI5 typically outputs 16-bit mono at 16kHz or 22.05kHz.
    # Try each rate and pick the most plausible duration (< 300s for TTS).
    audio_bytes = len(data) - 44 if len(data) >= 44 else len(data)
    if audio_bytes <= 0:
        return 0
    for rate in (22050, 16000, 24000, 44100, 48000, 8000):
        duration = int(audio_bytes * 1000 / (rate * 2))  # 16-bit mono = 2 bytes/sample
        if 100 < duration < 300_000:  # between 0.1s and 300s — plausible for TTS
            return duration
    return int(audio_bytes * 1000 / 32000)  # last resort


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

    Every request gets a request_id (also returned as X-Request-Id header)
    that threads through all agent-stage JSON logs for tracing.
    """
    request_id = uuid.uuid4().hex[:12]
    history = memory.get_history(req.session_id)

    async def event_stream():
        full_reply = ""
        has_error = False
        try:
            async for sse_event in run_agent_stream(req.text, history, request_id=request_id, use_cache=True):
                event = sse_event.event
                data = sse_event.data

                if event == "token":
                    text = data.get("text", "")
                    full_reply += text  # raw for memory
                    # Strip action tags + emoji + symbols + sensitive patterns
                    clean = _strip_action_tags(text)
                    clean = _strip_emoji(clean)
                    clean = _strip_symbols(clean)
                    clean = _filter_sensitive(clean)
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
                    # Strip non-speakable content: emoji, action tags, symbols, sensitive
                    tts_text = _strip_emoji(full_reply)
                    tts_text = _strip_action_tags(tts_text)
                    tts_text = _strip_symbols(tts_text)
                    tts_text = _filter_sensitive(tts_text)
                    if not tts_text:
                        tts_text = full_reply  # fallback if everything was stripped

                    # Synthesize: Edge TTS (neural, online) → pyttsx3 (offline fallback).
                    # Edge TTS returns (MP3 bytes, word_boundaries), pyttsx3 returns
                    # (WAV bytes, []) — we detect format from boundary presence.
                    audio_bytes, word_boundaries = await synthesize_with_word_boundary(tts_text)
                    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

                    has_boundaries = len(word_boundaries) > 0
                    audio_fmt = "mp3" if has_boundaries else "wav"

                    # Calculate precise audio duration.
                    if has_boundaries:
                        # Edge TTS MP3: use boundaries for word-level precision,
                        # fall back to MP3 frame scanning (more accurate than byte-size estimate).
                        last = word_boundaries[-1]
                        boundary_ms = int((last["offset"] + last["duration"]) / 10000)
                        mp3_frame_ms = _mp3_duration(audio_bytes)
                        # Take the larger of the two (boundaries can miss trailing silence)
                        audio_duration_ms = max(boundary_ms, mp3_frame_ms)
                    else:
                        # pyttsx3 WAV: parse from header
                        audio_duration_ms = _wav_duration(audio_bytes)

                    # Build per-character durations from Edge TTS word boundaries.
                    # Uses len(wb_text) for ALL characters in the boundary word (including
                    # punctuation) — this matches tts_text character count exactly because
                    # Edge TTS processes the same text.
                    char_durations: list[float] | None = None
                    if has_boundaries:
                        char_durations = _boundaries_to_char_durations(word_boundaries)

                    # Fallback ms_per_char for pyttsx3 (no boundaries)
                    cjk_count = sum(1 for ch in tts_text if "一" <= ch <= "鿿")
                    non_cjk_count = len(tts_text) - cjk_count
                    total_speak_ms = audio_duration_ms - non_cjk_count * 80
                    ms_per_char = (
                        max(total_speak_ms / cjk_count, 20.0) if (cjk_count > 0 and total_speak_ms > 0) else 30.0
                    )

                    print(
                        f"[TTS] format={audio_fmt}, duration={audio_duration_ms}ms, "
                        f"bytes={len(audio_bytes)}, text_len={len(tts_text)}, "
                        f"boundaries={len(word_boundaries)}, "
                        f"char_dur_len={len(char_durations) if char_durations else 0}, "
                        f"ms_per_char={ms_per_char:.1f}"
                    )

                    yield "event: audio\n"
                    yield f"data: {json.dumps({'base64': audio_b64, 'format': audio_fmt, 'duration_ms': audio_duration_ms}, ensure_ascii=False)}\n"
                    yield "\n"

                    # Generate viseme sequence with word-boundary timing when available,
                    # otherwise uniform per-character distribution.
                    viseme_seq = text_to_viseme_sequence(
                        tts_text,
                        ms_per_char=ms_per_char,
                        char_durations=char_durations,
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
            "X-Request-Id": request_id,
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
