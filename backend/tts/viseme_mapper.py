"""Viseme (mouth shape) mapper for Chinese phonemes.

Maps initial consonants and finals to 5-level viseme levels (0–4) for
2D lip-sync animation.
"""

from __future__ import annotations

from backend.tts.g2p_service import text_to_phonemes

# Viseme levels:
#   0 = closed mouth (b/p/m)
#   1 = teeth together, slightly open (d/t/n/l/j/q/x)
#   2 = half open (g/k/h/zh/ch/sh/z/c/s)
#   3 = fully open (a/ao/ang/an/ai)
#   4 = rounded lips (o/u/w/yu/yue/yuan)

# Initial consonant → viseme level
INITIAL_MAP: dict[str, int] = {
    "b": 0, "p": 0, "m": 0,
    "f": 1,
    "d": 1, "t": 1, "n": 1, "l": 1,
    "j": 1, "q": 1, "x": 1,
    "g": 2, "k": 2, "h": 2,
    "zh": 2, "ch": 2, "sh": 2, "r": 2,
    "z": 2, "c": 2, "s": 2,
    "y": 4, "w": 4,
}

# Final/vowel → viseme level (by leading vowel)
FINAL_MAP: dict[str, int] = {
    "a": 3, "ai": 3, "an": 3, "ang": 3, "ao": 2,
    "e": 2, "ei": 2, "en": 2, "eng": 2, "er": 2,
    "i": 1, "ia": 3, "ian": 3, "iang": 3, "iao": 2,
    "ie": 2, "in": 1, "ing": 1, "io": 4, "iu": 4,
    "o": 4, "ong": 4, "ou": 4,
    "u": 4, "ua": 3, "uai": 3, "uan": 3, "uang": 3,
    "uei": 4, "uen": 4, "ueng": 4, "ui": 4, "un": 4, "uo": 4,
    "v": 4, "ve": 4,
    "yue": 4, "yuan": 4,
}


def phoneme_to_viseme(initial: str, final: str) -> int:
    """Convert a single phoneme (initial + final) to viseme level 0–4.

    Strategy: take max(initial_viseme, final_viseme) since the mouth
    shape is dominated by the most open component.

    Args:
        initial: Initial consonant (may be empty string).
        final: Final/vowel (may be empty string).

    Returns:
        Viseme level 0–4. Defaults to 2 (half open) for unknown sounds.
    """
    init_level = INITIAL_MAP.get(initial, 2)
    final_level = FINAL_MAP.get(final, 2)
    return max(init_level, final_level)


def text_to_viseme_sequence(
    text: str,
    ms_per_char: float = 80.0,
) -> list[dict]:
    """Convert Chinese text to a viseme timeline.

    Args:
        text: Chinese text to analyze.
        ms_per_char: Approximate duration per character in milliseconds.

    Returns:
        List of {"time_ms": float, "level": int} dicts.
        Non-CJK chars (punctuation) are mapped to level 0 (mouth closed).
    """
    phonemes = text_to_phonemes(text)
    sequence: list[dict] = []

    for i, ph in enumerate(phonemes):
        time_ms = i * ms_per_char
        if ph["is_cjk"]:
            level = phoneme_to_viseme(ph["initial"], ph["final"])
        else:
            # Punctuation / space: close mouth
            level = 0
        sequence.append({"time_ms": round(time_ms, 1), "level": level})

    return sequence
