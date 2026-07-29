"""Offline TTS synthesis via pyttsx3 (Windows SAPI5).

Uses the system's built-in Chinese TTS voice (Microsoft Huihui).
Fully offline — zero network, zero proxy, zero API key.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

# Lazy-initialized engine singleton
_engine = None
_load_error: str | None = None


def _get_engine():
    """Create and configure pyttsx3 engine (once, with Chinese voice)."""
    global _engine, _load_error
    if _engine is not None:
        return _engine
    if _load_error is not None:
        raise RuntimeError(_load_error)

    try:
        import pyttsx3

        e = pyttsx3.init()
        # Auto-select Chinese voice
        for voice in e.getProperty("voices"):
            if any(lang.startswith("zh") for lang in (voice.languages or [])):
                e.setProperty("voice", voice.id)
                print(f"[TTS] Using voice: {voice.name}")
                break
        else:
            print("[TTS] No Chinese voice found, using default")
        e.setProperty("rate", 200)  # speaking speed
        e.setProperty("volume", 1.0)
        _engine = e
        return e
    except Exception as exc:
        _load_error = str(exc)
        raise RuntimeError(f"pyttsx3 init failed: {exc}") from exc


def _synthesize_sync(text: str) -> bytes:
    """Blocking synthesis — called via thread pool to avoid blocking event loop."""
    engine = _get_engine()
    # pyttsx3 save_to_file writes to a file path; use temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        temp_path = f.name
    try:
        engine.save_to_file(text, temp_path)
        engine.runAndWait()
        with open(temp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


async def synthesize(text: str) -> bytes:
    """Synthesize Chinese text into WAV audio bytes.

    Args:
        text: Chinese text to synthesize.

    Returns:
        WAV audio bytes (system default sample rate, mono).
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _synthesize_sync, text)


async def synthesize_with_word_boundary(
    text: str,
    voice: str = "",
    proxy: str | None = None,
) -> tuple[bytes, list[dict]]:
    """Synthesize with word boundaries (not supported by pyttsx3/SAPI5).

    pyttsx3 does not provide word-level timing. This function returns
    empty boundaries, so the viseme pipeline falls back to fixed-timing
    estimation (ms_per_char). The voice and proxy parameters are
    accepted for API compatibility but ignored.

    Returns:
        Tuple of (wav_bytes, []) — always empty boundaries.
    """
    audio = await synthesize(text)
    return audio, []
