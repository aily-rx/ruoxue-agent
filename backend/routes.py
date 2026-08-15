"""FastAPI route handlers for the Ruoxue agent.

Phase 2: adds ASR endpoint and TTS audio + viseme events.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
import uuid
from pathlib import Path

from backend.agent.agent_graph import ping_llm, run_agent_stream
from backend.agent.chroma_memory import chroma_memory
from backend.agent.emotional_agent import SSEEvent
from backend.agent.memory import memory
from backend.asr.asr_service import asr_service
from backend.tts.tts_service import synthesize_with_word_boundary
from backend.tts.viseme_mapper import text_to_viseme_sequence
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter()

_logger = logging.getLogger("routes")

# LLM 健康探测缓存: 探测要发真实请求, TTL 内复用结果避免每次 /api/health 都打 API
_LLM_HEALTH_TTL_S = 60.0
_llm_health_cache: tuple[float, bool] | None = None


async def _check_llm_available() -> bool:
    """LLM 可用性探测（带 60s 结果缓存, 首次调用最多阻塞 2.5s）。"""
    global _llm_health_cache
    now = time.monotonic()
    if _llm_health_cache is not None and now - _llm_health_cache[0] < _LLM_HEALTH_TTL_S:
        return _llm_health_cache[1]
    ok = await ping_llm(timeout=2.5)
    _llm_health_cache = (now, ok)
    return ok


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


def _clean_for_tts(text: str) -> str:
    """逐句 TTS 前的文本清洗 — 与 token 显示过滤同规则（四重过滤）。"""
    text = _strip_action_tags(text)
    text = _strip_emoji(text)
    text = _strip_symbols(text)
    return _filter_sensitive(text).strip()


# ── 句子级分片（边生成边合成）────────────────────────────────────────

# 句末标点集合: 中文句末符 + 半角 !?;。刻意不含 ASCII '.' 和 '．',
# 避免 3.14 / Mr. / 版本号 1.2.3 被误断句。
_SENTENCE_END = "。！？!?；;…\n"
_SENTENCE_SPLIT_RE = re.compile(rf"[^{_SENTENCE_END}]*[{_SENTENCE_END}]+")

# 残句兜底切分阈值: 模型偶发漏打句末标点时, 残句超过该长度就在最近逗号处
# 强切, 保证分片延迟有界（否则长尾文本会一直等到流结束才合成）。
_MAX_CHUNK_CHARS = 40
_MIN_CUT_CHARS = 20


def _split_sentences(buffer: str) -> tuple[list[str], str]:
    """从流式累积文本中切出完整句: 返回 (完整句列表, 剩余残句)。

    逐 token 调用: 文本不含句末符时全部留在残句; 句末符一到, 其前面的
    整句立即被切出——保证句子文本完整后才进入 TTS。
    残句超长（漏标点）时在最近逗号处兜底强切。
    """
    sentences = _SENTENCE_SPLIT_RE.findall(buffer)
    consumed = sum(len(s) for s in sentences)
    rest = buffer[consumed:]

    if len(rest) >= _MAX_CHUNK_CHARS:
        cut = rest.rfind("，")
        if cut >= _MIN_CUT_CHARS:
            sentences.append(rest[: cut + 1])
            rest = rest[cut + 1 :]
        else:
            # 没有合适的逗号切点 → 整段强切（保证延迟有界）
            sentences.append(rest)
            rest = ""

    return sentences, rest


async def _synthesize_chunk(seq: int, text: str) -> dict | None:
    """合成一个句子的 (audio, viseme), TTS 失败返回 None（非致命, 只丢该句音频）。

    复用原有整段合成的逻辑: Edge TTS WordBoundary → 逐字时长 → G2P 口型
    序列 → 按真实音频时长缩放。逐句独立缩放, 时间轴各自从 0 开始。
    """
    try:
        audio_bytes, word_boundaries = await synthesize_with_word_boundary(text)
    except Exception as exc:
        _logger.warning("tts chunk synthesis failed", extra={"seq": seq, "error": str(exc)})
        return None

    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    has_boundaries = len(word_boundaries) > 0
    audio_fmt = "mp3" if has_boundaries else "wav"

    if has_boundaries:
        last = word_boundaries[-1]
        boundary_ms = int((last["offset"] + last["duration"]) / 10000)
        mp3_frame_ms = _mp3_duration(audio_bytes)
        audio_duration_ms = max(boundary_ms, mp3_frame_ms)
        char_durations = _boundaries_to_char_durations(word_boundaries)
    else:
        audio_duration_ms = _wav_duration(audio_bytes)
        char_durations = None

    # Fallback ms_per_char for pyttsx3 (no boundaries)
    cjk_count = sum(1 for ch in text if "一" <= ch <= "鿿")
    non_cjk_count = len(text) - cjk_count
    total_speak_ms = audio_duration_ms - non_cjk_count * 80
    ms_per_char = max(total_speak_ms / cjk_count, 20.0) if (cjk_count > 0 and total_speak_ms > 0) else 30.0

    viseme_seq = text_to_viseme_sequence(
        text,
        ms_per_char=ms_per_char,
        char_durations=char_durations,
    )
    if viseme_seq and audio_duration_ms > 0:
        raw_last_ms = viseme_seq[-1]["time_ms"]
        if raw_last_ms > 0:
            scale = audio_duration_ms / raw_last_ms
            for v in viseme_seq:
                v["time_ms"] = round(v["time_ms"] * scale, 1)

    return {
        "audio": {"base64": audio_b64, "format": audio_fmt, "duration_ms": audio_duration_ms},
        "viseme": viseme_seq,
    }


def _format_tts_chunk(chunk: dict) -> list[str]:
    """把单个句子的合成结果格式化为 SSE 行（audio + viseme 各带 seq）。

    chunk: {"seq": int, "result": {"audio": {...}, "viseme": [...]} | None}
    合成失败的句子（result=None）不产出行, 前端只少播一句, 不影响流程。
    """
    seq = chunk["seq"]
    result = chunk["result"]
    if result is None:
        return []
    audio = result["audio"]
    return [
        "event: audio\n",
        f"data: {json.dumps({**audio, 'seq': seq}, ensure_ascii=False)}\n",
        "\n",
        "event: viseme\n",
        f"data: {json.dumps({'frames': result['viseme'], 'seq': seq}, ensure_ascii=False)}\n",
        "\n",
    ]


async def _store_chroma_async(session_id: str, user_text: str, assistant_text: str) -> None:
    """Chroma 长期记忆写入 — 线程池执行, fire-and-forget, 不阻塞 done 发出。"""
    try:
        await asyncio.to_thread(chroma_memory.store_turn, session_id, user_text, assistant_text)
    except Exception as e:
        _logger.warning("chroma store_turn failed", extra={"error": str(e)})


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


class HitlConfirmRequest(BaseModel):
    """HITL 工具确认请求（对应 SSE tool_request 事件里的 request_id）。"""

    request_id: str = Field(..., min_length=1, description="SSE tool_request 事件的 request_id")
    approved: bool = Field(..., description="是否允许执行工具")


# --- Routes ---


@router.post("/api/chat")
async def chat(req: ChatRequest):
    """SSE streaming chat endpoint with sentence-chunked TTS + viseme events.

    token 流逐句切分: 每句文本一完整就入队后台合成（与后续 token 生成并行）,
    合成完推送一对带 seq 的 audio/viseme 事件, 前端按序排队播放——实现
    "边生成边说话"。done 在文本完成 + 记忆落库后立即发出, 不再等待最后
    一句的 TTS 合成。

    Events: emotion, token*, audio*, viseme*, done | error, tool_request
    """
    request_id = uuid.uuid4().hex[:12]
    history = memory.get_history(req.session_id)

    async def event_stream():
        full_reply = ""
        has_error = False
        sentence_buffer = ""
        seq_counter = 0

        # 句文本 → 后台 worker 串行合成 → (seq, result) 进 out 队列
        jobs: asyncio.Queue = asyncio.Queue()
        out: asyncio.Queue = asyncio.Queue()

        async def _tts_worker() -> None:
            while True:
                job = await jobs.get()
                if job is None:
                    out.put_nowait(None)  # worker 完成哨兵
                    return
                result = await _synthesize_chunk(job["seq"], job["text"])
                out.put_nowait({"seq": job["seq"], "result": result})

        worker = asyncio.create_task(_tts_worker())

        async def _produce() -> None:
            """代理 run_agent_stream: 过滤 token、切句入队合成, 其余事件直通。"""
            nonlocal full_reply, has_error, sentence_buffer, seq_counter
            try:
                async for sse_event in run_agent_stream(req.text, history, request_id=request_id, use_cache=True):
                    event = sse_event.event
                    data = sse_event.data
                    if event == "done":
                        continue  # 本层在文本完成后统一发 done
                    if event == "token":
                        if not isinstance(data, dict):
                            continue
                        text = data.get("text", "")
                        full_reply += text  # raw for memory
                        clean = _clean_for_tts(text)
                        if clean:
                            out.put_nowait(SSEEvent(event="token", data={"text": clean}))
                        # 句子分片: 完整句立即入队后台合成
                        sentence_buffer += text
                        sentences, sentence_buffer = _split_sentences(sentence_buffer)
                        for s in sentences:
                            clean_s = _clean_for_tts(s)
                            if clean_s:
                                jobs.put_nowait({"seq": seq_counter, "text": clean_s})
                                seq_counter += 1
                        continue
                    if event == "error":
                        has_error = True
                    out.put_nowait(sse_event)
            except Exception as exc:
                has_error = True
                out.put_nowait(SSEEvent(event="error", data={"message": str(exc), "code": 500}))
            finally:
                # 残句兜底: 无句末标点的回复整段作为最后一句
                if not has_error and sentence_buffer.strip():
                    clean_s = _clean_for_tts(sentence_buffer)
                    if clean_s:
                        jobs.put_nowait({"seq": seq_counter, "text": clean_s})
                jobs.put_nowait(None)  # 结束合成队列
                out.put_nowait(None)  # producer 完成哨兵

        producer = asyncio.create_task(_produce())

        # 双哨兵: producer 完成（文本流结束）+ worker 完成（所有句子合成完毕）
        sentinels = 0
        done_sent = False
        try:
            while sentinels < 2:
                item = await out.get()
                if item is None:
                    sentinels += 1
                    # 文本流完成: 落库 + 提前发 done（剩余 TTS 仍在后台合成）
                    if sentinels == 1 and not done_sent:
                        if not has_error:
                            memory.add_user_message(req.session_id, req.text)
                            if full_reply.strip():
                                memory.add_assistant_message(req.session_id, full_reply)
                                _ = asyncio.create_task(_store_chroma_async(req.session_id, req.text, full_reply))
                            yield "event: done\n"
                            yield "data: {}\n"
                            yield "\n"
                            done_sent = True
                    continue
                if isinstance(item, SSEEvent):
                    yield f"event: {item.event}\n"
                    yield f"data: {json.dumps(item.data, ensure_ascii=False)}\n"
                    yield "\n"
                else:
                    # TTS 分片结果 → audio + viseme
                    for line in _format_tts_chunk(item):
                        yield line
        finally:
            producer.cancel()
            worker.cancel()

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


@router.post("/api/hitl-confirm")
async def hitl_confirm(req: HitlConfirmRequest):
    """Human-in-the-loop 工具确认端点。

    SSE 流收到 tool_request 事件（含 request_id + 工具名）后, 前端调用本端点
    回复允许/拒绝; 后端恢复被 interrupt 挂起的 graph（超时未确认默认拒绝）。
    """
    from backend.agent.agent_graph import confirm_tool_call

    if not confirm_tool_call(req.request_id, req.approved):
        raise HTTPException(404, "No pending tool confirmation for this request_id")
    return {"status": "ok", "request_id": req.request_id, "approved": req.approved}


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
    """Health check endpoint — ASR 状态 + LLM 真实探测（60s 缓存）。"""
    return HealthResponse(
        status="ok",
        version="0.2.0",
        llm_available=await _check_llm_available(),
        asr_available=asr_service.is_loaded,
    )
