# Ruoxue — Live2D 前端集成方案

> 版本: v1.0 | 日期: 2026-07-24 | 状态: Phase 3 设计

---

## 一、需求概述

在 React 应用中集成 Live2D Cubism SDK for Web，实现 2D 角色的加载、渲染、表情切换、口型同步。

---

## 二、技术选型

| 方案 | 说明 |
|------|------|
| Live2D Cubism SDK for Web 5 | 官方 SDK，WebGL 渲染 |
| React 封装 | 自定义 Canvas 组件 + Hooks |
| 模型格式 | .moc3 + .model3.json + 纹理 + 动作 + 表情 |

---

## 三、组件架构

```
Live2DCanvas.tsx          React Canvas 组件
    |
    v
CubismManager.ts          SDK 初始化 + 模型生命周期
    |
    +-> EmotionDriver.ts   情绪 -> Expression/Parameter
    +-> LipSyncDriver.ts   Viseme -> ParamMouthOpenY
```

### 3.1 CubismManager

```
职责: Live2D SDK 单例管理

方法:
  init(canvas)             初始化 Framework + 创建渲染循环
  loadModel(modelPath)     加载 .model3.json -> 返回 CubismModel
  startMotion(group, name) 播放动作
  setExpression(name)      切换表情
  dispose()                释放资源

渲染循环:
  requestAnimationFrame 驱动:
    1. CubismFramework.update()
    2. 更新模型参数 (Emotion/LipSync)
    3. CubismRenderer.draw()
```

### 3.2 EmotionDriver

```
职责: 情绪标签 -> Live2D 参数平滑过渡

方法:
  transitionTo(emotion, intensity)  平滑切换到目标情绪
  reset()                           重置到 neutral

实现:
  1. 查找 EMOTION_CONFIG[emotion]
  2. 如果模型有 preset expression -> setExpression()
  3. 遍历 params -> lerpParameter() (easeInOutCubic)
  4. intensity 缩放参数幅度
```

### 3.3 LipSyncDriver

```
职责: Viseme 时间轴 -> Live2D 嘴型参数逐帧驱动

方法:
  load(timeline)   加载 [{time_ms, level}, ...]
  start()          开始与音频同步
  reset()          归零嘴型

实现:
  1. 每帧获取 audioManager.getCurrentTime()
  2. 二分查找当前 time_ms 对应的 level
  3. 查 MOUTH_PARAM_MAP[level] -> setParameterValueById()
  4. 音频结束 -> reset()
```

---

## 四、Live2D 模型准备

需要的模型文件:
```
model_assets/live2d/ruoxue/
  ruoxue.model3.json    模型描述文件
  ruoxue.moc3           模型数据
  textures/             贴图
  motions/              动作文件 (.motion3.json)
  expressions/          表情文件 (.exp3.json)
```

> 可使用 Live2D Cubism Editor 创建，或使用社区免费模型。

---

## 五、React 集成

```tsx
// Live2DCanvas.tsx
const Live2DCanvas: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { model, emotionDriver, lipSyncDriver } = useLive2D(canvasRef);

  // 从 ChatClient 接收情绪事件
  useEffect(() => {
    chatClient.onEmotion(({ emotion, intensity }) => {
      emotionDriver?.transitionTo(emotion, intensity);
    });
  }, [emotionDriver]);

  return <canvas ref={canvasRef} />;
};
```

---

## 六、待机动画

- 呼吸: ParamBreath 正弦波 (周期 3-5s)
- 眨眼: ParamEyeLOpen/ParamEyeROpen 周期性归零 (间隔 2-5s 随机)
- 微动: ParamBodyAngleX/Y/Z 小幅随机扰动

---

*最后更新: 2026-07-24*
