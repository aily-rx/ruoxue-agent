"""Chinese G2P (Grapheme-to-Phoneme) using pypinyin.

Splits Chinese characters into initials and finals for viseme mapping.
"""

from __future__ import annotations

import re

from pypinyin import Style, pinyin

# Regex to match a single Chinese character
_CJK_RE = re.compile(r"[一-鿿]")

# Regex to split pinyin into initial + final
# Examples: zhong -> (zh, ong), chang -> (ch, ang), a -> ("", a)
_PINYIN_SPLIT_RE = re.compile(r"^(b|p|m|f|d|t|n|l|g|k|h|j|q|x|zh|ch|sh|r|z|c|s|y|w)?(.*)$")


def text_to_phonemes(text: str) -> list[dict]:
    """Convert Chinese text into a sequence of phoneme segments.

    Non-Chinese characters (punctuation, spaces, etc.) are preserved as
    pause markers.

    Args:
        text: Input text containing Chinese characters.

    Returns:
        List of dicts with keys:
            - char: original character
            - initial: initial consonant (empty string if none)
            - final: final/vowel part
            - is_cjk: whether this is a Chinese character
    """
    results: list[dict] = []

    for ch in text:
        if _CJK_RE.match(ch):
            py_list = pinyin(ch, style=Style.NORMAL, heteronym=False)
            syllable = py_list[0][0] if py_list else ""

            match = _PINYIN_SPLIT_RE.match(syllable)
            if match:
                initial, final = match.group(1) or "", match.group(2) or ""
            else:
                initial, final = "", syllable

            results.append(
                {
                    "char": ch,
                    "initial": initial,
                    "final": final,
                    "is_cjk": True,
                }
            )
        else:
            # Non-CJK character: treat as short pause
            results.append(
                {
                    "char": ch,
                    "initial": "",
                    "final": "",
                    "is_cjk": False,
                }
            )

    return results
