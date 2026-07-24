# 本地多模态 AI Agent 数字人助手 — 技术方案 v2.0

> 整合自：AstrBot 代码分析 + Lira Avatar 文档经验 + 原始学习笔记
> 日期: 2026-07-24

---

## 1. 项目定位

> 构建一个**本地部署的多模态 AI Agent 数字人助手**（个人版 Jarvis）。

核心能力矩阵：

| 能力 | 说明 |
|------|------|
| 语音输入 | 本地离线 ASR（SenseVoice），不依赖云端 |
| 语音输出 | TTS 合成 + 口型同步 |
| 2D 数字人 | Live2D 角色，带表情变化、嘴型同步 |
| AI Agent | LangChain + LangGraph，可调用工具完成任务 |
| 记忆系统 | 短期（SQLite）+ 长期（Chroma 向量库）|
| 知识库 | RAG 检索增强生成 |
| 本地运行 | Ollama 本地 LLM，数据不出设备 |

**与已有项目的关系：**

| 项目 | 定位 | 本项目的借鉴 |
|------|------|-------------|
| **AstrBot** | 多平台 IM 聊天机器人框架 | Provider 抽象层（LLM/TTS/STT）、Agent 工具调用、上下文压缩 |
| **Lira Avatar** | 3D 数字人 Web 应用 | SSE 流式架构、G2P 中文口型、MicRecorder 状态机、SenseVoice ASR |

---

## 2. 总体系统架构

```
                              用户
                                |
                  ------------------------------
                  |                            |
               麦克风                         文本输入
                  |                            |
          ┌───────┴───────┐                    |
          │  SenseVoice    │                    |
          │  离线 ASR       │                    |
          └───────┬───────┘                    |
                  |                            |
                  └──────────┬─────────────────┘
                             v
                ┌──────────────────────┐
                │     AI Agent 层      │
                │                      │
                │   LangChain+LangGraph │
                │         |            │
                │    LLM 模型           │
                │  DeepSeek/Ollama      │
                │         |            │
                │  ┌──────┴──────┐     │
                │  │             │     │
                │ Memory       Tools   │
                │ (Chroma)  (搜索/文件)  │
                └──────────────────────┘
                             |
                             v
                ┌──────────────────────┐
                │      输出层          │
                │                      │
                │  情绪标签 + 回复文本   │
                │         |            │
                │   Edge TTS（纯合成）   │
                │         |            │
                │   音频 + Viseme时间轴  │
                └──────────────────────┘
                             |
                             v
                ┌──────────────────────┐
                │    数字人前端         │
                │   React + Vite       │
                │         |            │
                │   Live2D Cubism      │
                │         |            │
                │  表情/嘴型/动作       │
                └──────────────────────┘
```

---

## 3. 核心技术栈（最终确定）

| 层级 | 技术 | 说明 | 决策理由 |
|------|------|------|---------|
| **前端框架** | React + Vite | SPA | Live2D 有成熟 React 封装；复杂 UI 更好管理 |
| **2D 引擎** | Live2D Cubism SDK for Web | 角色渲染 | 中文社区活跃，嘴型参数天然支持，表情系统完善 |
| **后端框架** | FastAPI + Uvicorn | API 服务 | 原生异步，与 LangChain 无缝集成 |
| **Agent** | LangChain + LangGraph | 智能体框架 | 生态最丰富（Memory/RAG/Tools），LangGraph 做复杂流程 |
| **LLM 云端** | DeepSeek | 主力模型 | 成本低、中文好 |
| **LLM 本地** | Ollama + Qwen2.5 | 本地备选 | 离线可用、数据不上传 |
| **TTS** | Edge TTS | 语音合成 | 免费、中文自然度高 |
| **ASR** | SenseVoice (sherpa-onnx) | 语音识别 | 完全离线、五语种+情绪检测、仅229MB |
| **口型同步** | pypinyin G2P → Live2D 参数 | 中文嘴型 | 借鉴 Lira 方案，2D简化到5级嘴型 |
| **情绪系统** | LLM Prompt 输出标签 → Live2D Expression | 表情变化 | 不依赖 TTS 情绪合成，纯面部表现 |
| **记忆** | Chroma + SQLite | 长期/短期 | Chroma 轻量易部署，SQLite 零配置 |
| **实时通信** | SSE（文字流）+ WebSocket（语音对话） | 双协议 | SSE 适合单向流式，WebSocket 适合双向实时 |
| **工具系统** | LangChain Tools + MCP 协议 | 能力扩展 | 搜索/文件/系统控制 |
| **安全** | Human-in-the-loop | 操作确认 | 危险操作需用户确认 |

---

## 4. 情绪系统设计

> 决策：保留 LLM 驱动情绪标签 → Live2D 表情变化。情绪化 TTS 暂不实现（硬件限制），TTS 仅做纯合成。

### 4.1 数据流

```
用户消息 → LLM 生成回复
              │
              ├──→ 情绪标签（happy/sad/angry/surprised/neutral/thoughtful/worried/excited）
              │         │
              │         └──→ SSE: emotion 事件 → Live2D Expression 驱动
              │
              ├──→ 回复文本 → Edge TTS（纯合成）→ SSE: audio + viseme
              │
              └──→ SSE: token* → 文字流式显示
```

### 4.2 LLM 情绪识别（Prompt 工程）

```python
# backend/agent/emotional_agent.py
from enum import Enum
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser

class Emotion(str, Enum):
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    NEUTRAL = "neutral"
    THOUGHTFUL = "thoughtful"
    WORRIED = "worried"
    EXCITED = "excited"

class EmotionalResponse(BaseModel):
    emotion: Emotion = Field(description="情绪")
    text: str = Field(description="回复文本")
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)

EMOTION_SYSTEM_PROMPT = """你是 Ruoxue，一个有情感的数字人助手。

请根据对话语境选择合适的情绪，按 JSON 格式回复：
{"emotion": "...", "text": "...", "intensity": 0.5}

情绪选择指南：
- happy: 好消息、赞美、轻松愉快的聊天
- sad: 安慰用户、表达遗憾、共情
- angry: 表达不满、严肃警告（极少使用）
- surprised: 惊讶的信息、意外的事情
- neutral: 一般信息查询、中性回复
- thoughtful: 需要思考的问题、给出建议
- worried: 用户遇到困难、表达担忧
- excited: 分享激动人心的信息

注意：intensity 越高，表情越夸张。日常对话使用 0.3-0.6。"""

parser = JsonOutputParser(pydantic_object=EmotionalResponse)
```

### 4.3 Live2D 情绪映射表

```typescript
// frontend/src/live2d/EmotionDriver.ts

const EMOTION_CONFIG: Record<string, {
  expression: string | null;
  params: Record<string, number>;
  transitionMs: number;
}> = {
  happy: {
    expression: "happy",
    params: {
      ParamMouthOpenY: 0.2,    // 嘴微张微笑
      ParamEyeLOpen: 1.0,
      ParamBrowLY: 0.15,       // 眉毛微扬
    },
    transitionMs: 300,
  },
  sad: {
    expression: "sad",
    params: {
      ParamMouthOpenY: 0.0,    // 闭嘴
      ParamEyeLOpen: 0.7,      // 眼睛半闭
      ParamBrowLY: -0.5,       // 眉毛下压
      ParamAngleZ: 5,          // 头微低
    },
    transitionMs: 500,
  },
  surprised: {
    expression: null,          // 纯参数组合
    params: {
      ParamMouthOpenY: 0.6,   // 嘴巴张大
      ParamEyeLOpen: 1.5,     // 眼睛瞪大
      ParamBrowLY: 1.0,       // 眉毛高扬
    },
    transitionMs: 150,
  },
  neutral: {
    expression: "neutral",
    params: {},
    transitionMs: 400,
  },
  thoughtful: {
    params: {
      ParamMouthOpenY: 0.0,
      ParamEyeLOpen: 0.8,
      ParamBrowLY: 0.3,       // 单眉微挑
      ParamEyeBallY: 0.3,     // 眼珠微向上看
      ParamAngleZ: 3,          // 头微歪
    },
    transitionMs: 500,
  },
};

class EmotionDriver {
  private model: any;
  private currentEmotion = 'neutral';

  constructor(live2dModel: any) {
    this.model = live2dModel;
  }

  async transitionTo(emotion: string, intensity = 0.5): void {
    const config = EMOTION_CONFIG[emotion] || EMOTION_CONFIG.neutral;
    const duration = config.transitionMs || 400;

    if (config.expression) {
      this.model.setExpression(config.expression);
    }

    for (const [paramId, targetValue] of Object.entries(config.params)) {
      const currentValue = this.model.getParameterValueById(paramId);
      const scaledTarget = targetValue * intensity;
      this.lerpParameter(paramId, currentValue, scaledTarget, duration);
    }

    this.currentEmotion = emotion;
  }

  reset(duration = 600): void {
    this.transitionTo('neutral', 0.0);
  }

  private lerpParameter(id: string, from: number, to: number, ms: number): void {
    const start = performance.now();
    const tick = () => {
      const t = Math.min((performance.now() - start) / ms, 1.0);
      const eased = t < 0.5 ? 4*t*t*t : 1 - (-2*t+2)**3/2;
      this.model.setParameterValueById(id, from + (to-from)*eased);
      if (t < 1.0) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
}
```

### 4.4 SSE 通信协议（含情绪事件）

```
event: emotion
data: {"emotion": "surprised", "intensity": 0.8}

event: token
data: {"text": "哇..."}

event: audio
data: {"base64": "...", "format": "mp3", "duration_ms": 3200}

event: viseme
data: [{"time_ms": 0, "level": 3}, {"time_ms": 150, "level": 2}]

event: done
data: {}
```

前端接收：

```typescript
source.addEventListener('emotion', (e) => {
  const { emotion, intensity } = JSON.parse(e.data);
  emotionDriver.transitionTo(emotion, intensity);
});

source.addEventListener('audio', (e) => {
  audioManager.play(JSON.parse(e.data).base64);
  visemePlayer.start();
});

source.addEventListener('viseme', (e) => {
  visemePlayer.load(JSON.parse(e.data));
});
```

---

## 5. 口型同步方案

### 5.1 中文 G2P → Viseme 映射

借鉴 Lira 项目，2D 从 11 维 BlendShape 简化到 5 级嘴型。

```python
# backend/tts/viseme_mapper.py

MOUTH_LEVELS = {
    0: "闭嘴",      # b/p/m 等闭口音
    1: "齿合微张",   # d/t/n/l/j/q/x/z/c/s/i
    2: "半开",       # g/k/h/zh/ch/sh/r/e/an/en
    3: "全开",       # a/ao/ang/ong
    4: "圆唇",       # o/u/w/y/ou
}

INITIAL_MAP = {
    "b": 0, "p": 0, "m": 0, "f": 1,
    "d": 1, "t": 1, "n": 1, "l": 1,
    "g": 2, "k": 2, "h": 2,
    "j": 1, "q": 1, "x": 1,
    "zh": 2, "ch": 2, "sh": 2, "r": 2,
    "z": 1, "c": 1, "s": 1,
}

FINAL_MAP = {
    "a": 3, "o": 4, "e": 2,
    "i": 1, "u": 4, "v": 4,
    "ai": 3, "ei": 2, "ao": 3, "ou": 4,
    "an": 2, "en": 2, "ang": 3, "eng": 2, "ong": 3,
    "ia": 2, "ie": 2, "iao": 3, "iu": 2,
    "ian": 2, "in": 1, "iang": 3, "ing": 1, "iong": 3,
    "ua": 3, "uo": 4, "uai": 3, "ui": 2,
    "uan": 2, "un": 2, "uang": 3,
    "ve": 2, "vn": 2,
}

def word_to_mouth_level(word: str) -> int:
    """汉字 → 嘴型级别(0-4)"""
    from pypinyin import pinyin, Style
    initials = pinyin(word, style=Style.INITIALS, strict=False)[0][0]
    finals = pinyin(word, style=Style.FINALS, strict=False)[0][0]

    level = FINAL_MAP.get(finals, 2)
    if not initials:
        return level
    return max(level, INITIAL_MAP.get(initials, level))
```

### 5.2 Live2D 嘴型参数驱动

```typescript
// frontend/src/live2d/LipSyncDriver.ts

const MOUTH_PARAM_MAP: Record<number, Record<string, number>> = {
  0: { ParamMouthOpenY: 0.0 },                               // 闭嘴
  1: { ParamMouthOpenY: 0.15 },                              // 齿合
  2: { ParamMouthOpenY: 0.35 },                              // 半开
  3: { ParamMouthOpenY: 0.7, ParamMouthForm: 0.1 },          // 全开
  4: { ParamMouthOpenY: 0.4, ParamMouthForm: 0.8 },          // 圆唇
};

class LipSyncDriver {
  private timeline: {time_ms: number, level: number}[] = [];
  private index = 0;

  constructor(private model: any, private audio: any) {}

  load(timeline: {time_ms: number, level: number}[]): void {
    this.timeline = timeline;
    this.index = 0;
  }

  start(): void { this.tick(); }

  private tick = (): void => {
    const ms = this.audio.getCurrentTime() * 1000;
    while (
      this.index + 1 < this.timeline.length &&
      this.timeline[this.index + 1].time_ms <= ms
    ) {
      this.index++;
    }
    const params = MOUTH_PARAM_MAP[this.timeline[this.index]?.level ?? 0];
    for (const [id, v] of Object.entries(params)) {
      this.model.setParameterValueById(id, v);
    }
    if (this.audio.isPlaying()) {
      requestAnimationFrame(this.tick);
    } else {
      this.reset();
    }
  };

  reset(): void {
    this.model.setParameterValueById('ParamMouthOpenY', 0.0);
    this.timeline = [];
    this.index = 0;
  }
}
```

---

## 6. 项目目录结构

```
ruoxue_agent/
├── Agent.md                          # 共享知识库索引
├── CLAUDE.md                         # AI Agent 工作指南
├── AstrBot/                          # 现有 AstrBot 代码（作为参考库）
│
├── docs/                             # 项目文档
│   ├── AI_Agent_数字人助手技术栈学习笔记.md  # 本文档
│   ├── architecture.md               # Lira Avatar 架构参考
│   ├── project-structure.md          # Lira 项目结构参考
│   ├── frontend/
│   │   ├── prototype-layout.md       # Lira 原型布局
│   │   └── experience/               # Lira 前端经验
│   └── backend/
│       ├── api.md                    # Lira API 文档
│       ├── prd-lipsync.md            # Lira 口型同步 PRD
│       └── experience/               # Lira 后端经验
│
├── frontend/                          # React 前端工程
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx                   # React 入口
│       ├── App.tsx                    # 应用根组件
│       │
│       ├── components/                # React 组件
│       │   ├── ChatPanel.tsx          # 聊天面板（气泡+输入框）
│       │   ├── Live2DCanvas.tsx       # Live2D 渲染画布
│       │   ├── VoiceButton.tsx        # 语音输入按钮
│       │   └── EmotionIndicator.tsx   # 情绪指示器
│       │
│       ├── live2d/                    # Live2D 封装
│       │   ├── CubismManager.ts       # SDK 初始化 + 模型加载
│       │   ├── EmotionDriver.ts       # 情绪 → Expression 驱动
│       │   └── LipSyncDriver.ts       # Viseme → 嘴型参数驱动
│       │
│       ├── audio/                     # 音频模块
│       │   ├── AudioManager.ts        # Web Audio API 播放
│       │   └── MicRecorder.ts         # 麦克风录音 + WAV 编码
│       │
│       ├── chat/                      # 对话模块
│       │   ├── ChatClient.ts          # SSE 流接收器
│       │   └── ASRClient.ts           # ASR HTTP 请求
│       │
│       └── hooks/
│           ├── useChat.ts
│           ├── useLive2D.ts
│           └── useVoice.ts
│
├── backend/                           # Python 后端
│   ├── requirements.txt
│   ├── main.py                        # FastAPI 入口
│   ├── config.py                      # 配置管理
│   ├── routes.py                      # API 路由
│   │
│   ├── agent/                         # Agent 模块
│   │   ├── graph.py                   # LangGraph StateGraph
│   │   ├── emotional_agent.py         # 带情绪的 Agent
│   │   ├── tools.py                   # 工具注册
│   │   └── memory.py                  # 会话记忆管理
│   │
│   ├── tts/                           # TTS 模块
│   │   ├── tts_service.py             # Edge TTS 合成
│   │   ├── g2p_service.py             # pypinyin G2P
│   │   └── viseme_mapper.py           # 音素 → 嘴型映射
│   │
│   └── asr/                           # ASR 模块
│       └── asr_service.py             # SenseVoice 离线识别
│
└── model_assets/                      # 模型资源
    ├── live2d/                        # Live2D 模型文件
    │   ├── ruoxue.model3.json
    │   ├── ruoxue.moc3
    │   ├── textures/
    │   ├── motions/
    │   └── expressions/
    └── asr/                           # ASR 模型
        └── sensevoice-small-int8/
```

---

## 7. 分阶段实施计划

### Phase 1：文字聊天机器人  [基础对话]

> 目标：能打字的 AI 助手 | 时间：1-2 周

**交付物：**
- React 聊天界面（气泡 + 输入框 + 流式打字）
- FastAPI + LangChain LLM 对接 DeepSeek
- 多轮对话记忆
- SSE 流式推送

**文件清单：**
- `frontend/` 脚手架（Vite + React + TypeScript）
- `frontend/src/components/ChatPanel.tsx`
- `frontend/src/chat/ChatClient.ts`（SSE）
- `frontend/src/hooks/useChat.ts`
- `backend/main.py` + `backend/routes.py`
- `backend/agent/emotional_agent.py` + `memory.py`
- `backend/requirements.txt`

---

### Phase 2：语音助手  [会听会说]

> 目标：语音输入 + 语音输出 | 时间：1-2 周

**交付物：**
- SenseVoice 离线 ASR（借鉴 Lira `asr_service.py`）
- 麦克风录音 + WAV 编码（借鉴 Lira `MicRecorder.js`）
- Edge TTS 语音合成
- Web Audio API 播放
- WebSocket 双向实时（语音对话模式）

**文件清单：**
- `backend/asr/asr_service.py`
- `backend/tts/tts_service.py`
- `frontend/src/audio/MicRecorder.ts` + `AudioManager.ts`
- `frontend/src/chat/ASRClient.ts`
- `frontend/src/components/VoiceButton.tsx`
- `frontend/src/hooks/useVoice.ts`

---

### Phase 3：2D 数字人  [有形象]

> 目标：Live2D 角色 + 口型同步 + 情绪表情 | 时间：2 周

**交付物：**
- Live2D Cubism SDK for Web 集成
- 预置 Live2D 角色模型（加载+渲染）
- 中文 G2P 口型同步（5 级嘴型 → Live2D 参数）
- **情绪系统**：LLM 情绪标签 → Live2D Expression 变化
- 待机动画（呼吸、眨眼、微动）
- TTS 情绪化暂不实现（硬件限制）

```
LLM 回复 → {emotion, text, intensity}
              │          │
              v          v
   Live2D Expression   Edge TTS + Viseme → 口型
```

**文件清单：**
- `frontend/src/live2d/CubismManager.ts`
- `frontend/src/live2d/EmotionDriver.ts`
- `frontend/src/live2d/LipSyncDriver.ts`
- `frontend/src/components/Live2DCanvas.tsx`
- `backend/tts/g2p_service.py`
- `backend/tts/viseme_mapper.py`
- `model_assets/live2d/ruoxue.*`
- SSE 协议增加 `emotion` 和 `viseme` 事件

---

### Phase 4：Agent 智能体  [能帮忙]

> 目标：工具调用 + 知识库 + 长期记忆 | 时间：2-3 周

**交付物：**
- LangChain Tools：网页搜索、文件读取、天气查询
- LangGraph StateGraph 复杂任务编排
- Chroma 向量长期记忆
- RAG 个人知识库（PDF/Markdown）
- Ollama 本地 LLM 集成
- Human-in-the-loop 安全确认

```
LangGraph StateGraph:
  agent_node → should_continue?
       |            ├── yes → tools_node → agent_node
       |            └── no → END
       v
  Memory (Chroma) + RAG (FAISS)
```

**文件清单：**
- `backend/agent/graph.py`（LangGraph）
- `backend/agent/tools.py`
- `backend/agent/memory.py`（Chroma 升级）
- `backend/knowledge_base/`（RAG）
- `frontend/src/components/ToolCallBubble.tsx`

---

### Phase 5：产品化  [打磨]

> 目标：完善体验 + 多端部署 | 时间：按需

**交付物：**
- 桌面应用封装（Electron/Tauri）
- Docker 一键部署
- 性能优化
- 可选：接入 AstrBot IM 多平台能力

---

## 8. 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 前端框架 | React + Vite | Live2D 有 React 封装，复杂 UI 易管理 |
| 2D引擎 | Live2D | 中文社区活跃，嘴型/表情系统完善 |
| TTS 情绪化 | 暂不实现 | 主机硬件不支持，仅保留 Live2D 表情变化 |
| LLM | DeepSeek 云端 + Ollama 本地 | 混合模式，日常本地、复杂云端 |
| 口型方案 | pypinyin G2P → 5级嘴型 | 借鉴 Lira，2D 简化 |
| 实时通信 | SSE + WebSocket | SSE 用于文字流，WebSocket 用于语音 |
| ASR | SenseVoice (sherpa-onnx) | 完全离线，229MB，五语种+情绪检测 |
| 安全 | Human-in-the-loop | 危险操作需用户确认 |
| 情绪标签 | Prompt 工程输出 | Phase 3 用 Prompt，Phase 4 加分类器兜底 |

---

## 9. 参考资源

- [Live2D Cubism SDK for Web](https://www.live2d.com/en/download/cubism-sdk/)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [AstrBot GitHub](https://github.com/AstrBotDevs/AstrBot)
- [SenseVoice (sherpa-onnx)](https://github.com/k2-fsa/sherpa-onnx)
- [pypinyin](https://github.com/mozillazg/python-pinyin)
- [edge-tts](https://github.com/rany2/edge-tts)
- [Ollama](https://ollama.com/)

---

*最后更新: 2026-07-24*
