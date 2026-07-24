# Live2D Cubism SDK 白色矩形渲染问题修复

> Source: Ruoxue Agent | Date: 2026-07-24
> Tags: live2d, cubism, webgl, premultiplied-alpha, rendering

---

## 症状

Live2D 模型渲染时出现**白色矩形区域**，覆盖在模型部件（头发、衣服、身体）之上。模型本身可见，但被白色矩形部分遮挡或覆盖。

Console 可能伴随日志：
```
NoPremultipliedAlpha is not allowed
```

## 根因

**Premultiplied Alpha 不匹配**。这是三层不一致导致的：

| 层级 | 错误状态 | 正确状态 |
|------|---------|---------|
| WebGL Context | `premultipliedAlpha: false` | `premultipliedAlpha: true` |
| Cubism Renderer | `isPremultipliedAlpha() = false`（默认值） | `isPremultipliedAlpha() = true` |
| 纹理上传 | 未启用 `UNPACK_PREMULTIPLY_ALPHA_WEBGL` | 上传前开启，上传后关闭 |

Cubism SDK for Web 5 的 shader 内部使用**预乘 alpha 混合模式**（`blendFuncSeparate(ONE, ONE_MINUS_SRC_ALPHA, ONE, ONE_MINUS_SRC_ALPHA)`），且 shader 选择逻辑明确要求 `isPremultipliedAlpha()` 返回 `true`。

当这三层不一致时：
- Shader 按预乘 alpha 处理颜色，但纹理数据是非预乘的 → 颜色计算错误
- Canvas compositing 按非预乘模式合成，但 framebuffer 内是预乘数据 → 合成异常
- 最终表现为模型部件上的白色矩形/泛白区域

## 修复方案

需要在**三个位置**同时修改，缺一不可：

### 1. WebGL Context 属性

```typescript
// ❌ 错误
canvas.getContext('webgl2', {
  alpha: true, premultipliedAlpha: false, antialias: true, stencil: true,
})

// ✅ 正确
canvas.getContext('webgl2', {
  alpha: true, premultipliedAlpha: true, antialias: true, stencil: true,
})
```

### 2. Renderer 初始化后设置标志

```typescript
this.createRenderer(cw, ch);
var rr = this.getRenderer() as CubismRenderer_WebGL;
rr.setIsPremultipliedAlpha(true);  // ← 必须调用，默认值为 false
```

### 3. 纹理上传时预乘 Alpha

```typescript
gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, 1);
gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, 0);  // 恢复默认
```

## 排查过程

### 方法论：变量隔离 + 对照 Sample + 回退验证

面对"模型渲染异常"这类涉及多层管线（WebGL → SDK → 模型数据）的 bug，采用**系统化变量隔离法**，每次只改变一个变量，观察结果，逐步缩小范围。

---

### 第一轮：假设 Stencil Buffer 是根因

**假设**：官方 SDK Sample 清除了 Stencil buffer，我们的代码没清，导致遮罩数据帧间残留。

**测试**：在 `_startLoop()` 的 `gl.clear()` 中加入 `gl.STENCIL_BUFFER_BIT`。

**结果**：❌ 白块仍在。

**结论**：Stencil 清除不是主因（但它本身是正确的修复，保留作为 Bug #1）。

---

### 第二轮：假设双实例渲染

**假设**：React Strict Mode 或组件重挂导致两个 `CubismManager` 实例同时渲染到同一 canvas。

**测试**：添加实例计数器和帧计数器日志。

```typescript
private static _instanceCounter = 0;
// 在 _startLoop 中：
var instanceId = ++CubismManager._instanceCounter;
console.log('[Cubism] Render loop #' + instanceId + ' started');
```

**结果**：❌ 只有一个 `Loop #1`，没有双实例。

**结论**：不是多实例问题。

---

### 第三轮：对照官方 SDK Sample

**方法**：逐行对比 `CubismSdkForWeb-5-r.5/Samples/TypeScript/Demo/src/` 中三个关键文件与我们的代码：

| 对比项 | 官方 Sample | 我们的代码 | 差异 |
|--------|------------|-----------|------|
| Canvas context `premultipliedAlpha` | `true`（默认值） | `false`（显式设置） | 🔴 |
| `renderer.setIsPremultipliedAlpha()` | 调用，参数 `true` | 未调用 | 🔴 |
| 纹理上传 `UNPACK_PREMULTIPLY_ALPHA_WEBGL` | 设为 `1` | 未设置 | 🔴 |
| `gl.clearColor` alpha | `1.0`（不透明黑） | `0.0`（全透明） | 🟡 |
| `gl.clear` buffer bits | `COLOR \| DEPTH` | `COLOR \| DEPTH \| STENCIL` | 🟢 |
| `gl.enable(DEPTH_TEST)` | ✅ | ✅ | ✅ |
| MVP matrix 设置流程 | `modelMatrix * proj` | 相同 | ✅ |

**发现**：前三项差异都在 premultiplied alpha 链路上，且 SDK 源码中明确要求：

```typescript
// cubismshader_webgl.ts:235-237
if (!renderer.isPremultipliedAlpha()) {
    CubismLogError('NoPremultipliedAlpha is not allowed');
}
```

---

### 第四轮：回退验证（确认根因）

**方法**：在应用了 premultiplied alpha 三件套后，模型完整（白块消失），但有重影。为确认白块修复的确是 premultiplied alpha 带来的，尝试回退。

**回退操作**：
1. `premultipliedAlpha: true` → `false`
2. 删除 `setIsPremultipliedAlpha(true)`
3. 删除 `UNPACK_PREMULTIPLY_ALPHA_WEBGL`

**结果**：✅ 白块重现，证实这三项是白块根因。

---

### 第五轮：验证重影是否独立问题

在白块修复后，重影仍然存在。进一步测试确认重影与 premultiplied alpha 无关：

| 测试 | 操作 | 结果 |
|------|------|------|
| 清除方式 | `clearColor(0,0,0,1)` 不透明黑 | 重影仍在 |
| 驱动代码 | 禁用 emotion/lipSync driver | 重影仍在 |
| 遮罩系统 | `maskBufferCount=0` | 白块回来，重影仍在 |

**结论**：重影是独立于白块的另一个 bug，根因待查。

---

### 最终确认

`premultipliedAlpha: true` + `setIsPremultipliedAlpha(true)` + `UNPACK_PREMULTIPLY_ALPHA_WEBGL` → 白块彻底消失。

---

### 排查方法论总结

```
问题出现
    │
    ├─ 1. 日志诊断：加计数器/状态日志，排除多实例、多循环
    │
    ├─ 2. 对照权威参考：找到官方 Sample/Demo，逐行对比初始化代码
    │     ├─ Context 属性
    │     ├─ 初始化调用顺序
    │     ├─ 纹理加载方式
    │     └─ 渲染循环 GL 状态设置
    │
    ├─ 3. 变量隔离测试：每次只改一个变量
    │     ├─ 改前截图/记录
    │     ├─ 改后对比
    │     └─ 回退确认（改回去 bug 重现）
    │
    └─ 4. 锁定根因 → 记录文档
```

**核心原则**：
- **先对照官方**，不要凭空猜测。Cubism SDK 的 Sample 就是"正确答案"
- **每次只改一个变量**，避免多个改动纠缠导致无法定位
- **回退验证**：修复生效后故意回退一项，确认 bug 重现，才算真正锁定了根因
- **日志先行**：加诊断日志比反复 build 效率高得多

## 关键经验

- **Cubism SDK 强制要求 premultiplied alpha**。官方 Sample 使用默认上下文属性（`premultipliedAlpha: true`），如果显式传参容易误设为 `false`
- **三层缺一不可**：Context 属性、Renderer 标志、纹理预乘必须全部对齐，只改其中一项白块仍会出现
- **先看官方 Sample 怎么初始化**：对照 `lappsubdelegate.ts`（context）、`lappmodel.ts`（renderer + setIsPremultipliedAlpha）、`lapptexturemanager.ts`（纹理上传）
- **Stencil buffer 清除**（`gl.clear(STENCIL_BUFFER_BIT)`）是另一个独立的白块修复点，但它是次要因素，premultiplied alpha 才是主因

## 相关文件

- `frontend/src/live2d/CubismManager.ts` — 构造函数（Context）、loadModelFromUrl（Renderer + 纹理）
- `frontend/src/live2d/sdk/rendering/cubismshader_webgl.ts:235-237` — SDK 内部检查 `isPremultipliedAlpha()`
- SDK Sample: `CubismSdkForWeb-5-r.5/Samples/TypeScript/Demo/src/lappsubdelegate.ts`
- SDK Sample: `CubismSdkForWeb-5-r.5/Samples/TypeScript/Demo/src/lappmodel.ts:534,572`
- SDK Sample: `CubismSdkForWeb-5-r.5/Samples/TypeScript/Demo/src/lapptexturemanager.ts:96-103`

## See Also

- `Live2D_Cubism_白色矩形问题修复方案.md` — 初版排查文档
- `Live2D_数字人问题解决方案.md` — 模型渲染问题总览
