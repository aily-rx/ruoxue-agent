"""Viseme mapper 单元测试 — 音素 → 5 参数口型映射。

覆盖: 单元音 1 帧 / 复合韵母 2 帧 / 鼻韵母收口 / 空韵母闭口 /
声母对首帧的混合影响 / 未知韵母兜底 / text_to_viseme_sequence 时间轴。
纯函数测试, 无外部依赖。
"""

from __future__ import annotations

from backend.tts.viseme_mapper import (
    phoneme_to_viseme_frames,
    text_to_viseme_sequence,
)

_PARAM_KEYS = ("A", "I", "U", "E", "O")


# --- phoneme_to_viseme_frames ---


def test_simple_vowel_single_frame() -> None:
    frames = phoneme_to_viseme_frames("", "a")
    assert len(frames) == 1
    # 单元音 a: 开口 0.95
    assert frames[0]["A"] > 0.8


def test_diphthong_two_frames() -> None:
    frames = phoneme_to_viseme_frames("", "ai")
    assert len(frames) == 2
    # 第一帧以 a 为主, 第二帧向 i 过渡
    assert frames[0]["A"] > frames[1]["A"]


def test_nasal_final_ends_with_closure() -> None:
    frames = phoneme_to_viseme_frames("", "an")
    assert len(frames) == 2
    # 鼻韵母: 最后一帧向鼻音收口, 开口度应小于首帧
    assert frames[1]["A"] < frames[0]["A"]


def test_triphthong_stays_two_frames() -> None:
    frames = phoneme_to_viseme_frames("", "iao")
    assert len(frames) == 2


def test_empty_final_closed_mouth() -> None:
    """空韵母（标点）→ 全 0 闭口帧。"""
    frames = phoneme_to_viseme_frames("", "")
    assert len(frames) == 1
    assert all(frames[0][k] == 0.0 for k in _PARAM_KEYS)


def test_initial_blends_into_first_frame() -> None:
    """声母对第一帧有口型预备影响（b → u=0.35 圆唇）。"""
    frames = phoneme_to_viseme_frames("b", "a")
    assert frames[0]["U"] > 0


def test_unknown_final_fallback() -> None:
    frames = phoneme_to_viseme_frames("", "xyz")
    assert len(frames) == 1
    assert frames[0]["A"] == 0.2  # 兜底帧


def test_all_frames_have_five_params() -> None:
    frames = phoneme_to_viseme_frames("sh", "uang")
    for frame in frames:
        assert set(frame.keys()) == set(_PARAM_KEYS)


# --- text_to_viseme_sequence ---


def test_sequence_timeline_ascending() -> None:
    seq = text_to_viseme_sequence("你好")
    assert len(seq) >= 2
    times = [f["time_ms"] for f in seq]
    assert times == sorted(times)
    assert times[0] == 0.0


def test_sequence_frame_keys_complete() -> None:
    for frame in text_to_viseme_sequence("世界"):
        assert {"time_ms", *(_PARAM_KEYS)} <= set(frame.keys())


def test_punctuation_closes_mouth_and_pauses() -> None:
    seq = text_to_viseme_sequence("你好。")
    # 最后一个字符是标点 → 闭口帧 + 80ms 停顿
    last = seq[-1]
    assert last["A"] == 0.0
    assert last["time_ms"] > seq[-2]["time_ms"]


def test_char_durations_override_uniform() -> None:
    """提供 WordBoundary 时长时按实际每字时长推进时间轴。

    你(ni): 韵母 i 单元音 1 帧 × 100ms; 好(hao): 韵母 ao 双元音 2 帧 × 200/2ms。
    帧时间轴: [0, 100, 200] → 终点 200ms(总时长 300ms)。
    """
    seq = text_to_viseme_sequence("你好", char_durations=[100.0, 200.0])
    assert [f["time_ms"] for f in seq] == [0.0, 100.0, 200.0]


def test_empty_text_returns_empty() -> None:
    assert text_to_viseme_sequence("") == []
