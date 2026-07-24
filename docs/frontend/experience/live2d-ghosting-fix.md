# Live2D 模型重影问题修复

> Source: Ruoxue Agent | Date: 2026-07-24
> Tags: live2d, cubism, ghosting, physics, pose, update-scheduler

---

## 症状

Live2D 模型渲染正常（纹理完整、无白块），但出现**"两个模型重叠"的视觉重影**——静态、无运动、无模糊，仿佛模型被渲染了两遍。

## 根因

**缺少 Physics + Pose 数据加载，以及 `CubismUpdateScheduler` 参数更新管线。**

Cubism SDK 的参数系统依赖以下组件共同维护模型参数的正确值：

| 组件 | 数据文件 | 作用 | 是否加载 |
|------|---------|------|---------|
| Expression | `.exp3.json` | 表情参数 | ✅ 已加载 |
| Pose | `.pose3.json` | 默认姿态参数 | ❌ 未加载 |
| Physics | `.physics3.json` | 物理参数（头发/衣服） | ❌ 未加载 |
| `CubismUpdateScheduler` | — | 统一调度所有 updater | ❌ 未创建 |

**缺失后果**：
- 模型参数停留在 `.moc3` 的原始默认值，而非 `.pose3.json` 定义的修正值
- 物理参数未被初始化，physics 相关部件（头发、衣服）的位置偏移
- 这些偏移导致 mask 裁切几何体与主模型错位，产生"重叠"视觉效果

## 修复方案

### 1. 引入 Update Scheduler 及相关 Updater

```typescript
import { CubismUpdateScheduler } from './sdk/motion/cubismupdatescheduler';
import { CubismPhysicsUpdater } from './sdk/motion/cubismphysicsupdater';
import { CubismPoseUpdater } from './sdk/motion/cubismposeupdater';
```

### 2. 在模型加载时初始化 Scheduler 并注册 Updater

```typescript
// 加载 Physics 数据
const physicsResp = await fetch(physicsPath);
const physicsBuf = await physicsResp.arrayBuffer();
this.loadPhysics(physicsBuf, physicsBuf.byteLength);
if (this._physics) {
  this._updateScheduler.addUpdatableList(
    new CubismPhysicsUpdater(this._physics)
  );
}

// 加载 Pose 数据
const poseResp = await fetch(posePath);
const poseBuf = await poseResp.arrayBuffer();
this.loadPose(poseBuf, poseBuf.byteLength);
if (this._pose) {
  this._updateScheduler.addUpdatableList(
    new CubismPoseUpdater(this._pose)
  );
}
```

### 3. 在渲染循环中调用 Scheduler

```typescript
// 每帧渲染流程（顺序很重要）
var n = performance.now();
var dt = (n - lastFrameTime) / 1000;  // delta time in seconds

self.lipSyncDriver.update(n);         // 口型驱动
self.emotionDriver.update(n);         // 表情驱动
self._updateScheduler.onLateUpdate(   // SDK 参数更新管线
  self._model, dt                     // ← Physics + Pose updaters
);
self._model.update();                 // 计算顶点
```

---

## 排查过程

### 第一轮：排除外因

| 测试 | 操作 | 结果 |
|------|------|------|
| 双实例 | 实例计数器日志 | ❌ 只有 Loop #1 |
| 清除方式 | `clearColor(0,0,0,1)` 不透明黑 | ❌ 重影仍在 |
| 驱动代码 | 禁用 emotion/lipSync driver | ❌ 重影仍在 |
| Alpha 模式 | 回退 premultipliedAlpha 改动 | ❌ 重影仍在（白块回来） |

**结论**：重影不由外部渲染设置引起，问题在 SDK 内部管线。

### 第二轮：对照官方 Sample 更新管线

对比 `LAppModel.update()` 与我们的 `_startLoop()`：

| 步骤 | 官方 Sample | 我们的代码 |
|------|------------|-----------|
| loadParameters/saveParameters | ✅ | ❌ |
| Motion 管理 | ✅ Idle 随机播放 | ❌ |
| **`CubismUpdateScheduler.onLateUpdate()`** | ✅ | ❌ |
| `_model.update()` | ✅ | ✅ |

**发现**：官方 Sample 的 `CubismUpdateScheduler` 统一管理 Physics、Pose、EyeBlink、Breath 等 updater，在 `_model.update()` 之前调用。我们完全没有这个管线。

### 第三轮：补全管线 → 验证

1. 加载 `mao_pro.physics3.json` + 创建 `CubismPhysicsUpdater`
2. 加载 `mao_pro.pose3.json` + 创建 `CubismPoseUpdater`
3. 创建 `CubismUpdateScheduler`，注册两个 updater
4. 渲染循环中在 `_model.update()` 之前调用 `scheduler.onLateUpdate()`

**结果**：✅ 重影消失，模型渲染正常。

---

## 关键经验

- **Cubism SDK 的参数系统是分层管线的**：模型参数由 Expression、Pose、Physics、EyeBlink、Breath、Motion 等多个系统共同维护。只加载 Expression 是不够的。
- **`CubismUpdateScheduler` 是必须的中间层**：即使不需要动画效果（EyeBlink、Breath、Motion），Pose 和 Physics 也需要通过 Scheduler 每帧更新参数到正确值。
- **对照官方 Sample 要对照完整流程**：不仅看初始化代码，还要看每帧的 `update()` 调用链。Sample 的 `update()` 比 `draw()` 更重要——参数错误在渲染之前就已产生。
- **模型数据文件有具体作用**：`model3.json` 的 `FileReferences` 中列出的 Physics、Pose 等文件不是可选的装饰——它们直接影响静态渲染结果。

## 相关文件

- `frontend/src/live2d/CubismManager.ts` — `_updateScheduler` + Physics/Pose 加载 + 渲染循环调用
- `frontend/src/live2d/sdk/motion/cubismupdatescheduler.ts` — Scheduler API（`addUpdatableList`、`onLateUpdate`）
- `frontend/src/live2d/sdk/motion/cubismphysicsupdater.ts` — Physics updater
- `frontend/src/live2d/sdk/motion/cubismposeupdater.ts` — Pose updater
- SDK Sample: `CubismSdkForWeb-5-r.5/Samples/TypeScript/Demo/src/lappmodel.ts:594-624` — 完整 `update()` 实现

## See Also

- `live2d-white-rectangle-fix.md` — 白块问题（premultiplied alpha 不匹配）
