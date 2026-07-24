# Ruoxue — 情绪表情 PRD

> 版本: v1.0 | 日期: 2026-07-24 | 状态: Phase 3 设计

---

## 一、需求概述

数字人根据对话语境自动切换面部表情，让交互更自然。

> 注意：情绪化 TTS (语音语调) 暂不实现，仅做面部表情变化。

---

## 二、情绪枚举

| 情绪 | 触发场景 | Live2D 表现 |
|------|---------|-------------|
| happy | 好消息、赞美、轻松聊天 | 微笑、眉毛微扬、眼微眯 |
| sad | 安慰、遗憾、共情 | 嘴角下垂、半闭眼、头微低 |
| angry | 不满、警告 (极少用) | 皱眉、瞪眼 |
| surprised | 意外信息 | 张嘴、瞪大眼睛、眉毛高扬 |
| neutral | 信息查询、中性回复 | 默认表情 |
| thoughtful | 思考问题、给建议 | 单眉微挑、眼珠向上看、头微歪 |
| worried | 用户遇困难 | 微皱眉、表情关切 |
| excited | 激动人心的信息 | 大笑、眼睛发光 |

---

## 三、Live2D 参数映射

```
EMOTION_CONFIG = {
  happy: {
    expression: "happy",
    params: { ParamMouthOpenY: 0.2, ParamEyeLOpen: 1.0, ParamBrowLY: 0.15 },
    transitionMs: 300
  },
  sad: {
    expression: "sad",
    params: { ParamMouthOpenY: 0.0, ParamEyeLOpen: 0.7, ParamBrowLY: -0.5, ParamAngleZ: 5 },
    transitionMs: 500  // 悲伤过渡慢一些
  },
  surprised: {
    params: { ParamMouthOpenY: 0.6, ParamEyeLOpen: 1.5, ParamBrowLY: 1.0 },
    transitionMs: 150  // 惊讶要快
  },
  ...
}
```

---

## 四、情绪强度

`intensity` 参数 (0.0-1.0) 缩放表情幅度:

- 0.0: 中性表情
- 0.3-0.6: 日常对话
- 0.7-1.0: 强烈情绪

```typescript
const scaledTarget = config.params[paramId] * intensity;
```

---

## 五、过渡动画

使用 easeInOutCubic 缓动函数平滑过渡:

```typescript
// 0 -> 1 的缓动
const eased = t < 0.5 ? 4*t*t*t : 1 - (-2*t+2)**3/2;
```

不同情绪的过渡时长:
- surprised/excited/angry: 150-200ms (快速)
- happy/neutral: 300-400ms (正常)
- sad/thoughtful: 500ms (慢速，更自然)

---

## 六、SSE 事件流程

```
服务端 -> SSE emotion 事件 -> 前端 EmotionDriver

{
  "emotion": "surprised",
  "intensity": 0.8
}

前端接收:
  1. emotionDriver.transitionTo("surprised", 0.8)
  2. 开始表情过渡动画
  3. 同时 token 流式文字开始显示
  4. 接着 audio + viseme 开始播放
```

---

## 七、验收标准

- [ ] 8 种情绪均能正确切换到对应表情
- [ ] 表情过渡平滑，无跳变
- [ ] 情绪与对话内容匹配率 > 80%
- [ ] intensity 参数有效缩放表情幅度
- [ ] 回复结束后表情回归 neutral (可延迟 2-3s)

---

*最后更新: 2026-07-24*
