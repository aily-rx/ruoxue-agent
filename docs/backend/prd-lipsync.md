# Ruoxue — 2D 口型同步 PRD

> 版本: v1.0 | 日期: 2026-07-24 | 状态: Phase 3 设计

---

## 一、需求概述

数字人说话时，Live2D 角色嘴巴需要与语音同步开合。

**与 Lira (3D) 的区别:** Lira 用 11 维 BlendShape 驱动 3D 头部网格。Ruoxue 用 5 级嘴型驱动 Live2D Parameter。

---

## 二、技术方案

### 2.1 整体流程

```
LLM 回复文本
    |
    v
pypinyin G2P (汉字 -> 声母 + 韵母)
    |
    v
viseme_mapper.py (声韵母 -> 嘴型级别 0-4)
    |
    v
Viseme 时间轴 [{time_ms, level}, ...]
    |
    v
SSE viseme 事件
    |
    v
前端 LipSyncDriver (时间轴 -> Live2D ParamMouthOpenY)
```

### 2.2 嘴型级别定义

| Level | 描述 | 典型音素 | Live2D 参数 |
|-------|------|---------|-------------|
| 0 | 闭嘴 | b/p/m | ParamMouthOpenY: 0.0 |
| 1 | 齿合微张 | d/t/n/l/j/q/x/z/c/s/i | ParamMouthOpenY: 0.15 |
| 2 | 半开 | g/k/h/zh/ch/sh/r/e/an/en | ParamMouthOpenY: 0.35 |
| 3 | 全开 | a/ao/ang/ong | ParamMouthOpenY: 0.7, ParamMouthForm: 0.1 |
| 4 | 圆唇 | o/u/w/y/ou | ParamMouthOpenY: 0.4, ParamMouthForm: 0.8 |

### 2.3 G2P 映射逻辑

```python
def word_to_mouth_level(word: str) -> int:
    from pypinyin import pinyin, Style
    initials = pinyin(word, style=Style.INITIALS, strict=False)[0][0]
    finals = pinyin(word, style=Style.FINALS, strict=False)[0][0]

    level = FINAL_MAP.get(finals, 2)  # 韵母决定主嘴型
    if not initials:
        return level
    return max(level, INITIAL_MAP.get(initials, level))  # 取较大值
```

### 2.4 时间轴生成

由于 2D 不使用 Edge TTS 的 WordBoundary (字词级时间戳)，采用**均匀分配**策略:

```python
def build_viseme_timeline(text: str, duration_ms: int) -> list[dict]:
    words = list(text)  # 逐字
    chars_per_second = len(words) / (duration_ms / 1000)
    ms_per_char = duration_ms / len(words)

    timeline = []
    for i, word in enumerate(words):
        level = word_to_mouth_level(word)
        timeline.append({
            "time_ms": int(i * ms_per_char),
            "level": level
        })
    return timeline
```

> Phase 4 可升级为基于音频 RMS 音量的动态嘴型（更精准但更复杂）。

---

## 三、验收标准

- [ ] 中文输入 -> 5 级嘴型正确映射
- [ ] 嘴型切换与音频播放同步 (偏差 < 200ms)
- [ ] Live2D ParamMouthOpenY 平滑过渡 (无跳变)
- [ ] 音频结束 -> 嘴型自动归零
- [ ] 生僻字兜底 (无映射 -> 默认为 level 2)

---

*最后更新: 2026-07-24*
