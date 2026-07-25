"""Viseme mapper for Chinese phonemes → 5-parameter mouth shapes.

Generates multi-frame sequences for compound finals (diphthongs, triphthongs)
to capture the dynamic mouth movement within each syllable.

Model mouth parameters:
  ParamA: mouth openness (wide "ah")
  ParamI: mouth spread (smile "ee")
  ParamU: mouth round (pursed "oo")
  ParamE: half-open spread ("eh")
  ParamO: round-open ("oh")
"""

from __future__ import annotations

from backend.tts.g2p_service import text_to_phonemes

# ── Shape helpers ──

def _s(a=0.0, i=0.0, u=0.0, e=0.0, o=0.0) -> dict[str, float]:
    return dict(A=a, I=i, U=u, E=e, O=o)

# ── Simple vowel shapes ──
VOWEL = {
    "a": _s(a=0.95, o=0.25),                    # wide open
    "o": _s(a=0.5, u=0.5, o=0.95),              # round open
    "e": _s(a=0.45, i=0.2, e=0.95),             # half-open spread
    "i": _s(a=0.18, i=0.95),                    # spread/smile
    "u": _s(a=0.22, u=0.95, o=0.3),             # pursed round
    "v": _s(a=0.18, i=0.7, u=0.5),              # ü — pursed-spread
    "n": _s(a=0.15, i=0.1),                     # nasal coda — mouth closing
    "ng":_s(a=0.15, u=0.1, o=0.1),              # velar nasal — back closing
}

def _v(name: str) -> dict[str, float]:
    return dict(VOWEL.get(name, _s()))

def _blend(*shapes: dict[str, float]) -> dict[str, float]:
    """Average multiple shapes."""
    result = _s()
    for s in shapes:
        for k in result:
            result[k] += s.get(k, 0)
    n = len(shapes)
    for k in result:
        result[k] = round(result[k] / n, 2)
    return result

def _mix(s1: dict, s2: dict, w1: float = 0.7) -> dict:
    """Weighted mix of two shapes."""
    w2 = 1.0 - w1
    return {
        k: round(s1.get(k, 0) * w1 + s2.get(k, 0) * w2, 2)
        for k in ("A", "I", "U", "E", "O")
    }

# ── Initial consonant mouth-prep ──
INIT = {
    "b": _s(u=0.35, o=0.15),
    "p": _s(u=0.35, o=0.15),
    "m": _s(u=0.35, o=0.15),
    "f": _s(a=0.1, i=0.25, e=0.15),
    "d": _s(a=0.12, e=0.08),
    "t": _s(a=0.12, e=0.08),
    "n": _s(a=0.12, e=0.08),
    "l": _s(a=0.12, e=0.08),
    "j": _s(i=0.6),
    "q": _s(i=0.6),
    "x": _s(i=0.6),
    "g": _s(a=0.18, e=0.25, o=0.08),
    "k": _s(a=0.18, e=0.25, o=0.08),
    "h": _s(a=0.18, e=0.25, o=0.08),
    "zh": _s(a=0.12, u=0.25, e=0.08, o=0.15),
    "ch": _s(a=0.12, u=0.25, e=0.08, o=0.15),
    "sh": _s(a=0.12, u=0.25, e=0.08, o=0.15),
    "r":  _s(a=0.12, u=0.25, e=0.08, o=0.15),
    "z":  _s(i=0.45),
    "c":  _s(i=0.45),
    "s":  _s(i=0.45),
    "y":  _s(i=0.65, u=0.08),
    "w":  _s(u=0.65),
}


def _frames_for_final(final: str) -> list[dict[str, float]]:
    """Generate 1-3 frames for a final, capturing diphthong/triphthong movement.

    Simple vowels (a,o,e,i,u,v) → 1 frame
    Diphthongs (ai,ao,ou,ia,ua,uo,ie,ve,ei) → 2 frames (start → peak)
    Triphthongs (iao,iou,uai,uei) → 2 frames (peak1 → peak2)
    Nasals (an,ang,en,eng,ong,ian,in,ing,uan,un,uang) → 2 frames (vowel → closure)
    """
    # Simple vowels — single frame
    if final in ("a", "o", "e", "i", "u", "v"):
        return [_v(final)]

    # Diphthongs: two clear vowel targets
    if final == "ai":
        return [_v("a"), _blend(_v("a"), _v("i"))]
    if final == "ei":
        return [_v("e"), _blend(_v("e"), _v("i"))]
    if final == "ao":
        return [_v("a"), _v("o")]
    if final == "ou":
        return [_v("o"), _v("u")]

    # Nasals: vowel → nasal closure
    if final == "an":
        return [_v("a"), _mix(_v("a"), _v("n"), 0.4)]
    if final == "en":
        return [_v("e"), _mix(_v("e"), _v("n"), 0.4)]
    if final == "ang":
        return [_v("a"), _mix(_v("a"), _v("ng"), 0.4)]
    if final == "eng":
        return [_v("e"), _mix(_v("e"), _v("ng"), 0.4)]
    if final == "ong":
        return [_v("o"), _mix(_v("o"), _v("ng"), 0.3)]
    if final == "er":
        return [_v("e")]

    # i- medial: glide i→vowel
    if final == "ia":
        return [_mix(_v("i"), _v("a"), 0.4), _v("a")]
    if final == "ie":
        return [_mix(_v("i"), _v("e"), 0.4), _v("e")]
    if final == "iao":
        return [_mix(_v("i"), _v("a"), 0.3), _v("o")]
    if final == "iu":
        return [_mix(_v("i"), _v("o"), 0.3), _v("u")]
    if final == "ian":
        return [_mix(_v("i"), _v("a"), 0.3), _mix(_v("a"), _v("n"), 0.4)]
    if final == "in":
        return [_v("i"), _mix(_v("i"), _v("n"), 0.4)]
    if final == "iang":
        return [_mix(_v("i"), _v("a"), 0.3), _mix(_v("a"), _v("ng"), 0.4)]
    if final == "ing":
        return [_v("i"), _mix(_v("i"), _v("ng"), 0.4)]
    if final == "iong":
        return [_mix(_v("i"), _v("o"), 0.3), _mix(_v("o"), _v("ng"), 0.3)]

    # u- medial: glide u→vowel
    if final == "ua":
        return [_mix(_v("u"), _v("a"), 0.4), _v("a")]
    if final == "uo":
        return [_mix(_v("u"), _v("o"), 0.4), _v("o")]
    if final == "uai":
        return [_mix(_v("u"), _v("a"), 0.3), _blend(_v("a"), _v("i"))]
    if final == "ui":
        return [_mix(_v("u"), _v("e"), 0.3), _v("i")]
    if final == "uan":
        return [_mix(_v("u"), _v("a"), 0.3), _mix(_v("a"), _v("n"), 0.4)]
    if final == "un":
        return [_mix(_v("u"), _v("e"), 0.3), _mix(_v("e"), _v("n"), 0.4)]
    if final == "uang":
        return [_mix(_v("u"), _v("a"), 0.3), _mix(_v("a"), _v("ng"), 0.4)]
    if final == "ueng":
        return [_mix(_v("u"), _v("e"), 0.3), _mix(_v("e"), _v("ng"), 0.4)]

    # ü- medial
    if final in ("ve", "ue", "yue"):
        return [_mix(_v("v"), _v("e"), 0.4), _v("e")]
    if final == "yuan":
        return [_mix(_v("v"), _v("a"), 0.3), _mix(_v("a"), _v("n"), 0.4)]
    if final in ("yun", "vn"):
        return [_v("v"), _mix(_v("v"), _v("n"), 0.3)]
    if final == "io":
        return [_mix(_v("i"), _v("o"), 0.4), _v("o")]

    # Fallback: treat as unknown
    return [_s(a=0.2, i=0.15, u=0.1, e=0.15, o=0.1)]


def phoneme_to_viseme_frames(initial: str, final: str) -> list[dict[str, float]]:
    """Generate 1-3 viseme frames for a phoneme, with initial influence on first frame."""

    if not final:
        return [_s()]  # closed mouth for punctuation

    frames = _frames_for_final(final)
    init_shape = INIT.get(initial)

    if init_shape and len(frames) > 0:
        # Blend initial shape into the first frame
        frames[0] = _mix(init_shape, frames[0], 0.3)

    return frames


def text_to_viseme_sequence(
    text: str,
    ms_per_char: float = 30.0,
    char_durations: list[float] | None = None,
) -> list[dict]:
    """Convert Chinese text to a 5-parameter viseme timeline with multi-frame phonemes.

    Each Chinese character produces 1-3 frames at ~30ms spacing for compound finals,
    capturing the internal mouth movement of diphthongs and triphthongs.

    When char_durations is provided, each CJK character uses its actual duration
    from WordBoundary data instead of the uniform ms_per_char.

    Returns:
        List of {"time_ms": float, "A": float, "I": float, "U": float, "E": float, "O": float}
    """
    phonemes = text_to_phonemes(text)
    sequence: list[dict] = []
    time_ms = 0.0
    cjk_idx = 0  # index into char_durations for CJK characters only

    for ph in phonemes:
        if ph["is_cjk"]:
            frames = phoneme_to_viseme_frames(ph["initial"], ph["final"])
            # Use per-character duration from WordBoundary data if available
            char_dur = char_durations[cjk_idx] if char_durations and cjk_idx < len(char_durations) else ms_per_char
            cjk_idx += 1
        else:
            # Punctuation → close mouth briefly, short fixed duration
            frames = [_s()]
            char_dur = 80.0  # 80ms pause for punctuation

        for shape in frames:
            frame: dict = {"time_ms": round(time_ms, 1)}
            frame.update(shape)
            sequence.append(frame)
            time_ms += char_dur / max(len(frames), 1)

    return sequence
