# Live2D Emotion 表情驱动修复

> Source: Ruoxue Agent | Date: 2026-07-24
> Tags: live2d, emotion, expression, per-parameter, transition

---

## 症状

1. **表情不生效** — 用户发送消息后数字人无 thinking 表情，且 8 种情绪切换无明显变化
2. **Reset 按钮无效** — 点击后不能恢复模型初始状态
3. **Thinking 表情无法展示** — 看似代码执行了，实际无可见效果

## 根因

### 1. 参数名完全不匹配模型

编写 `EmotionDriver` 时假设模型使用标准 Cubism 参数名：
```
ParamMouthOpenY, ParamAngleX, ParamAngleY, ParamAngleZ
```

但实际 `mao_pro` 模型使用的是：
```
ParamA（张嘴）、ParamMouthUp（微笑）、ParamMouthDown（抿嘴）、ParamMouthAngry（怒嘴）
ParamBrowLY/RY（眉毛上下）、ParamBrowLAngle/RAngle（眉毛角度）
ParamEyeLOpen/ROpen（眼睛开合）、ParamEyeLSmile/RSmile（笑眼）
```

**教训**：不能假设参数名。必须读 `.exp3.json` 或 `.cdi3.json` 查看模型真实参数。

### 2. 表情 index 映射错误

`EmotionDriver` 的 MAP 将 emotion label 映射到 `.exp3.json` 文件索引，但这个映射是**凭空猜测的**，未验证每个表情文件的实际内容。正确做法是逐一读取 `.exp3.json` 找出非零参数来判断该文件的视觉效果。

| 文件 | 猜测映射 | 实际效果 | 正确映射 |
|------|---------|---------|---------|
| exp_01 | neutral | 睁眼（默认） | neutral ✅ |
| exp_02 | happy | 笑眼 | happy ✅ |
| exp_05 | sad | 眉毛下压+嘴角向下 | **angry** |
| exp_06 | — | 脸红+皱眉 | **thoughtful** |
| exp_08 | angry | 怒嘴+锐利眼 | **sad/worried** |

### 3. 两段式过渡驱动了不该驱动的参数

过渡逻辑最初用 `for (var p in allParams)` 把所有已知参数强行归零作为 Phase 1（回到 neutral），再进入 Phase 2（新表情）。这导致：
- 无关参数（如眼睛、眉毛）被归零，破坏了模型默认状态
- Reset 后用 `loadParameters()` 恢复的默认值，下次点表情时又被全部归零

**修复**：Phase 1 只迭代 `tgtParams`（当前表情专属参数），无关参数保持原值不变。

### 4. Reset 设参数为 0 而非默认值

最初 `reset()` 把所有参数硬编码为 `0`，但模型默认值**不是 0**。如 `ParamEyeLOpen` 默认为 `1.0`（睁眼），设为 `0` 会闭眼。

**修复**：调用 `model.loadParameters()` 恢复模型加载时 `saveParameters()` 保存的原始快照。

### 5. Ref 直连绕过 React state，导致自动 reset 误触发

`Live2DCanvas` 有 `useEffect` 在 `emotion` prop 为 undefined 时 2 秒后自动 `reset()`。但 `ChatPanel` 通过 `ref.setEmotion()` 直连调用，不更新 `emotion` prop。reset 效果不知道已有表情，超时后覆盖了 thinking。

**修复**：移除自动 reset，情绪完全由 ChatPanel 显式控制。

---

## 排查过程

### 第一步：参数名验证

逐文件读取 8 个 `.exp3.json`，Python 脚本提取非零参数，发现模型实际参数名与代码中完全不同。

### 第二步：表情映射纠正

根据 `.exp3.json` 中非零参数的视觉效果，重新映射 emotion → expression index：

```
exp_01(睁眼) → neutral
exp_02(笑眼) → happy
exp_04(大眼星光) → excited
exp_05(压眉抿嘴) → angry
exp_06(脸红皱眉) → thoughtful
exp_07(瞪眼惊讶) → surprised
exp_08(怒嘴锐眼) → sad/worried
```

### 第三步：添加调试面板

在 `App.tsx` 添加浮动调试面板，8 个按钮 + intensity slider + Reset 按钮，直接调用 `live2dRef.setEmotion()`，绕过 React 渲染周期验证表情效果。

### 第四步：精确定位 Reset 失败

Console 加日志追踪 `setEmotion → transitionTo → setParameterValueById` 完整调用链。发现 `transitionTo` 被调用但之后 `reset()` 覆盖——因为自动 reset effect 没有被 `setEmotion`（ref 直连）通知到。

### 第五步：两段式过渡范围修正

`for (p in allParams)` → `for (p in tgtParams)`，只驱动当前表情关心的参数。

---

## 关键经验

- **永远先读模型数据再写代码**：参数名、表情文件内容必须从模型文件中确认，不能臆测
- **ref 直连 + React state 双路径要小心**：ref 调用不会触发状态更新，任何依赖 state 的 effect 都会被 bypass
- **"设为 0" ≠ "恢复默认"**：3D/2D 模型的参数默认值由设计师定义，不在代码层面
- **两段式过渡能直观展示表情差异**：先退 neutral(100ms) → 进目标(可配时长)，比直接切换更自然
- **调试面板是表情调试的关键工具**：绕过 React 周期，直接确认渲染是否正确

## 相关文件

- `frontend/src/live2d/EmotionDriver.ts` — 表情配置 + 两段式过渡 + reset
- `frontend/src/components/Live2DCanvas.tsx` — `forwardRef` + `useImperativeHandle` 暴露 `setEmotion`/`resetEmotion`
- `frontend/src/components/ChatPanel.tsx` — `handleSend` 同步调用 `setEmotion('thoughtful')`
- `frontend/src/App.tsx` — `live2dRef` 桥接 + 调试面板
- `frontend/public/live2d/mao_zh_Hans/expressions/exp_0*.exp3.json` — 模型表情数据源

## See Also

- `live2d-white-rectangle-fix.md` — 白块问题（premultiplied alpha）
- `live2d-ghosting-fix.md` — 重影问题（Physics + Pose + Scheduler）
