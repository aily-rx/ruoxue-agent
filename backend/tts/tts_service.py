"""Edge TTS synthesis wrapper.

Free Microsoft Edge TTS service integration.
Phase 2: basic synthesis.
"""

from __future__ import annotations

from io import BytesIO

import edge_tts

from backend.config import TTS_VOICE


async def synthesize(
    text: str,
    voice: str = TTS_VOICE,
    proxy: str | None = None,
) -> bytes:
    """Synthesize text into MP3 audio bytes using Edge TTS.

    Args:
        text: Chinese text to synthesize (practical limit ~3000 chars).
        voice: Edge TTS voice name.
        proxy: Optional HTTP proxy.

    Returns:
        Complete MP3 audio as bytes.
    """
    communicate = edge_tts.Communicate(text, voice, proxy=proxy)
    buffer = BytesIO()

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])

    if buffer.tell() == 0:
        raise RuntimeError("Edge TTS returned no audio data")

    return buffer.getvalue()


async def synthesize_with_word_boundary(
    text: str,
    voice: str = TTS_VOICE,
    proxy: str | None = None,
) -> tuple[bytes, list[dict]]:
    """Synthesize text with word boundary timing for viseme alignment.

    Returns:
        Tuple of (mp3_bytes, word_boundaries).
    """
    communicate = edge_tts.Communicate(
        text, voice, proxy=proxy,
        boundary="--boundary-type=WordBoundary",
    )
    buffer = BytesIO()
    word_boundaries: list[dict] = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            word_boundaries.append({
                "offset": chunk["offset"],
                "duration": chunk["duration"],
                "text": chunk["text"],
            })

    return buffer.getvalue(), word_boundaries
