"""TTS synthesis — Edge TTS (neural, online) + pyttsx3 (SAPI5, offline fallback).

Primary: Microsoft Edge TTS — 30+ neural Chinese voices, near-human quality.
Fallback: pyttsx3 / Windows SAPI5 — offline, lower quality, auto-selected
          when Edge TTS is unreachable (network down / firewall).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import tempfile
from io import BytesIO

import edge_tts
from backend.config import TTS_PROXY, TTS_VOICE

_logger = logging.getLogger("tts.service")

# ── Edge TTS (primary) ──────────────────────────────────────────────


async def _synthesize_edge(text: str, voice: str = TTS_VOICE) -> bytes:
    """Synthesize via Edge TTS → MP3 bytes."""
    communicate = edge_tts.Communicate(text, voice, proxy=TTS_PROXY)
    buffer = BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    if buffer.tell() == 0:
        raise RuntimeError("Edge TTS returned no audio data")
    return buffer.getvalue()


async def _synthesize_edge_with_boundaries(
    text: str,
    voice: str = TTS_VOICE,
) -> tuple[bytes, list[dict]]:
    """Synthesize via Edge TTS → (MP3 bytes, word_boundaries).

    Word boundaries provide per-character duration data for precise
    viseme lip-sync timing.
    """
    communicate = edge_tts.Communicate(
        text,
        voice,
        proxy=TTS_PROXY,
        boundary="WordBoundary",
    )
    buffer = BytesIO()
    word_boundaries: list[dict] = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            word_boundaries.append(
                {
                    "offset": chunk["offset"],  # 100ns units
                    "duration": chunk["duration"],  # 100ns units
                    "text": chunk["text"],
                }
            )

    if buffer.tell() == 0:
        raise RuntimeError("Edge TTS returned no audio data")
    return buffer.getvalue(), word_boundaries


# ── pyttsx3 / SAPI5 (offline fallback) ──────────────────────────────

_MAX_TTS_SECONDS = 30  # safety timeout for offline engine


def _com_init():
    """Initialize COM on current thread (required by SAPI5)."""
    try:
        import pythoncom

        pythoncom.CoInitialize()
    except ImportError:
        pass


def _com_uninit():
    try:
        import pythoncom

        pythoncom.CoUninitialize()
    except ImportError:
        pass


def _synthesize_sapi5(text: str) -> bytes:
    """Blocking SAPI5 synthesis via pyttsx3 → WAV bytes."""
    _com_init()
    try:
        import pyttsx3

        e = pyttsx3.init()
        for voice in e.getProperty("voices"):
            if any(lang.startswith("zh") for lang in (voice.languages or [])):
                e.setProperty("voice", voice.id)
                break
        e.setProperty("rate", 200)
        e.setProperty("volume", 1.0)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
        try:
            e.save_to_file(text, temp_path)
            e.runAndWait()
            with open(temp_path, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    finally:
        _com_uninit()


async def _synthesize_sapi5_async(text: str) -> bytes:
    """SAPI5 synthesis with timeout protection."""
    loop = asyncio.get_running_loop()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(executor, _synthesize_sapi5, text),
            timeout=_MAX_TTS_SECONDS,
        )
    except TimeoutError:
        raise TimeoutError(f"Offline TTS timed out after {_MAX_TTS_SECONDS}s") from None
    finally:
        executor.shutdown(wait=False)


# ── Public API ──────────────────────────────────────────────────────


async def synthesize(
    text: str,
    voice: str = TTS_VOICE,
    proxy: str | None = None,
) -> bytes:
    """Synthesize text → audio bytes (MP3 from Edge TTS).

    Automatically falls back to pyttsx3 SAPI5 if Edge TTS is unreachable.
    """
    try:
        audio = await _synthesize_edge(text, voice=voice)
        _logger.info("edge tts ok", extra={"bytes": len(audio)})
        return audio
    except Exception as edge_err:
        _logger.warning("edge tts failed, falling back to offline SAPI5", extra={"error": str(edge_err)})
        audio = await _synthesize_sapi5_async(text)
        _logger.info("offline SAPI5 ok", extra={"bytes": len(audio)})
        return audio


async def synthesize_with_word_boundary(
    text: str,
    voice: str = TTS_VOICE,
    proxy: str | None = None,
) -> tuple[bytes, list[dict]]:
    """Synthesize text → (audio_bytes, word_boundaries).

    Returns word-level timing data from Edge TTS for precise viseme sync.
    Falls back to pyttsx3 (empty boundaries) when offline.

    Each boundary dict: {"offset": int, "duration": int, "text": str}
    offset/duration are in 100-nanosecond units (Edge TTS convention).
    """
    try:
        audio, boundaries = await _synthesize_edge_with_boundaries(
            text,
            voice=voice,
        )
        _logger.info("edge tts ok", extra={"bytes": len(audio), "boundaries": len(boundaries)})
        return audio, boundaries
    except Exception as edge_err:
        _logger.warning("edge tts failed, falling back to offline SAPI5", extra={"error": str(edge_err)})
        audio = await _synthesize_sapi5_async(text)
        _logger.info("offline SAPI5 ok", extra={"bytes": len(audio), "boundaries": 0})
        return audio, []
