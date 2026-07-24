# Motion 语境绑定 PRD

> 版本: v1.0 | 日期: 2026-07-24 | 状态: Phase 3 设计

---

## 一、需求

将 7 个 motion 文件按"情绪+关键词"规则绑定到特定对话语境，语音结束后恢复待机动作。

### 绑定规则

| 条件 | 动作 | 优先级 |
|------|------|--------|
| 待机（无对话） | mtn_01 / mtn_03 随机，5~8s 切换 | 0 |
| emotion=happy + 文本含认同关键词 | mtn_02 | 1 |
| emotion=happy + 文本含"魔法/变个魔法/施法" | special_01 | 1 |

---

## 二、架构调整

### 2.1 砍掉代码驱动待机

`IdleMotionDriver` 不再在 render loop 中调用。改用 `CubismMotionManager` 播放 motion 文件作待机。

### 2.2 渲染循环顺序

motion 先跑，emotion/lip-sync 后覆盖，保证表情和口型不被 motion 干扰：

```
每帧:
  1. _motionManager.updateMotion()     ← motion 驱动身体+头部 (基准层)
  2. emotionDriver.update()             ← 面部表情覆盖 motion
  3. lipSyncDriver.update()             ← 口型覆盖 motion
  4. _updateScheduler.onLateUpdate()    ← 物理/姿态/眨眼
  5. _model.update()                    ← 最终化
```

### 2.3 优先级体系

| 优先级 | 场景 |
|--------|------|
| 0 | 待机动作 |
| 1 | 语境动作 |
| 2 | 调试面板（预留） |

---

## 三、模块设计

### 3.1 CubismManager 新增

```
状态:
  _idleTimer: number         待机切换倒计时 (秒)
  _idleActive: boolean       待机是否播放中
  _contextMotion: string     当前语境动作名 (空=无)

方法:
  startIdleMotion()          停止所有 motion → 随机选 mtn_01/mtn_03 → playMotion(pri=0)
  stopAllMotions()           清除 motion 队列 (已有 SDK 方法)
  playMotion(name, pri)      扩展：调用前先 stopAllMotions()
```

### 3.2 ChatPanel 新增

```
状态:
  replyBufferRef: string     累积的回答文本
  emotionRef: string         当前回答的情绪
  motionTriggeredRef: bool   本轮回答是否已触发过动作

检测逻辑 (每次 token 到达):
  if emotionRef=='happy' && !motionTriggeredRef:
    if replyBuffer 含 认同关键词:
      live2dRef.playMotion('mtn_02', 1)
      motionTriggeredRef = true
    elif replyBuffer 含 魔法关键词:
      live2dRef.playMotion('special_01', 1)
      motionTriggeredRef = true

重置 (新消息发送时/回答结束时):
  motionTriggeredRef = false
  replyBufferRef = ''
  emotionRef = ''
```

### 3.3 语音结束恢复

```
scheduleEmotionReset() (已有, 扩展):
  clearTimeout(上次)
  setTimeout 1.5s:
    setEmotion('neutral', 1.0)
    live2dRef.startIdleMotion()    ← 新增

handleSend() (已有, 扩展):
  clearTimeout(resetTimer)
  live2dRef.stopAllMotions()       ← 新增
  live2dRef.startIdleMotion()      ← 新增 (等待回答期间也保持待机)
```

---

## 四、注意事项（吸取历史经验）

| # | 过去踩过的坑 | 本次对策 |
|---|-------------|---------|
| 1 | **多 motion 并存冲突** — `startMotion()` 不清旧队列，多个 motion 同时驱动同参数 → 抖动/撕裂 | `playMotion()` 内部先 `stopAllMotions()` 再 `startMotionPriority()` |
| 2 | **Loop=True 无回调** — 循环 motion 不触发 `onFinishedMotion`，无法靠回调切动作 | 用 `_idleTimer` 手动计时，到期 `startIdleMotion()` 换另一个 |
| 3 | **渲染顺序错误** — motion 在 emotion 之后更新 → 表情参数被 motion 覆盖 | motion 提到 emotion/lip-sync 之前（见 2.2） |
| 4 | **ref 绕过 React state** — `useImperativeHandle` 的调用不触发 React re-render | motion 状态全在 `CubismManager` 内部管理，不依赖 React state 驱动 |
| 5 | **重复触发** — token 流中同一关键词在多 chunk 中反复出现 | `motionTriggeredRef` 标志，每轮回答只触发一次 |
| 6 | **旧回答的 reset timeout 竞态** — 音频结束 1.5s 后触发 reset，但用户已发新消息 | `handleSend` 主动 `clearTimeout` + `stopAllMotions` + `startIdleMotion` |
| 7 | **两阶段过渡同帧竞态** — Phase 1 完成和 Phase 2 触发在同一帧导致 `_paramTarget` 误清 | EmotionDriver v2.2 已修复（检查顺序：表达式→Phase 2 触发） |
| 8 | **表达式预设残留** — 情绪切换后旧的 Add 模式参数（眼形/眉角）不归零 | neutral config 已覆盖 22 参数，Phase 1 驱动全部 `neutralParams` |

---

## 五、关键词定义

### 认同类（触发 mtn_02）
```
对|没错|是的|确实|没错|说得对|同意|赞成|认同|当然|正是|有道理|我也觉得|我也是|好啊|好的呀|没问题|可以的|行|可以|OK|ok
```

### 魔法类（触发 special_01）
```
魔法|变个魔法|变魔法|施法|魔术|变个魔术|变魔术|咒语|法术|变戏法
```

---

## 六、改动文件清单

| 文件 | 改动 |
|------|------|
| `CubismManager.ts` | `startIdleMotion()`、`stopAllMotions()` 封装、`playMotion()` 加 stopAll、render loop 重排 + idle timer、移除 `idleMotionDriver.update()` |
| `ChatPanel.tsx` | 新增 `replyBufferRef`/`emotionRef`/`motionTriggeredRef`、token 检测逻辑、`scheduleEmotionReset`/`handleSend` 扩展 |
| `Live2DCanvas.tsx` | ref 暴露 `startIdleMotion` / `stopAllMotions` |
| `App.tsx` | 传递 token 文本给 ChatPanel（当前未传）或 ChatPanel 自行捕获 |

---

*最后更新: 2026-07-24*
