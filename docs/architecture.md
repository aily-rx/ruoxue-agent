# Ruoxue — 2D AI Agent 数字人全栈架构设计

> 版本: v1.0 | 日期: 2026-07-24 | Phase 0: 方案设计完成

---

## 一、项目概述

基于 **React + Live2D + LangChain + FastAPI** 构建的本地多模态 AI Agent 数字人助手。

### 1.1 技术栈

| 层 | 技术 | 用途 |
|------|------|------|
| 前端框架 | React 18 + Vite + TypeScript | SPA 应用 |
| 2D 渲染 | Live2D Cubism SDK for Web 5 | 角色渲染、表情、动作 |
| 后端框架 | FastAPI + Uvicorn | API 服务、SSE/WebSocket |
| Agent | LangChain + LangGraph | LLM 编排、工具调用 |
| LLM 云端 | DeepSeek API | 主力对话模型 |
| LLM 本地 | Ollama + Qwen2.5 | 离线备选 |
| TTS | Edge TTS | 语音合成（免费） |
| ASR | SenseVoice (sherpa-onnx) | 离线语音识别 |
| 口型 | pypinyin G2P | 中文音素 -> 嘴型映射 |
| 记忆 | Chroma + SQLite | 长期/短期记忆 |
| 通信 | SSE + WebSocket | 流式推送 + 双向实时 |

---

## 二、架构总览

### 2.1 系统分层架构

```
+--------------------------------------------------+
|                  Presentation Layer               |
|  React App                                        |
|  +-----------+  +----------+  +----------------+  |
|  | Live2D    |  | ChatPanel|  | VoiceButton    |  |
|  | Canvas    |  | (bubbles)|  | (mic + status) |  |
|  +-----------+  +----------+  +----------------+  |
|       |               |               |           |
|  +----v----+    +----v----+    +----v----+       |
|  |Emotion  |    | Chat    |    | MicRec  |       |
|  |Driver   |    |Client   |    |order    |       |
|  +---------+    |(SSE)    |    +---------+       |
|                 +---------+                       |
+--------------------------------------------------+
        |               |               |
        v               v               v
+--------------------------------------------------+
|                  Transport Layer                  |
|  SSE (token + emotion + audio + viseme + done)    |
|  WebSocket (voice duplex mode)                    |
|  HTTP REST (ASR upload, health check)             |
+--------------------------------------------------+
        |
        v
+--------------------------------------------------+
|                   Service Layer                   |
|  FastAPI Application                             |
|  +-------------+  +----------+  +-----------+    |
|  | routes.py   |  | /api/chat|  | /api/asr  |    |
|  |             |  | /api/tts |  | /api/health|   |
|  +-------------+  +----------+  +-----------+    |
+--------------------------------------------------+
        |
        v
+--------------------------------------------------+
|                    Agent Layer                    |
|  LangChain + LangGraph                           |
|  +------------------+  +--------------------+    |
|  | emotional_agent  |  | graph.py           |    |
|  | (LLM + emotion)  |  | (LangGraph state)  |    |
|  +------------------+  +--------------------+    |
|  | tools.py         |  | memory.py          |    |
|  | (search/file)    |  | (Chroma + SQLite)  |    |
|  +------------------+  +--------------------+    |
+--------------------------------------------------+
        |
        v
+--------------------------------------------------+
|                  Provider Layer                   |
|  +----------+  +----------+  +-----------+       |
|  | DeepSeek |  | Ollama   |  | Edge TTS  |       |
|  | (cloud)  |  | (local)  |  | (free)    |       |
|  +----------+  +----------+  +-----------+       |
|  +----------+  +----------+                      |
|  | SenseVoice|  | pypinyin |                     |
|  | (ASR)     |  | (G2P)    |                     |
|  +----------+  +----------+                      |
+--------------------------------------------------+
```

### 2.2 各层职责

| 层 | 职责 | 依赖方向 |
|------|------|----------|
| **Presentation** | Live2D 渲染、聊天 UI、语音采集/播放、情绪展示 | 依赖 Transport |
| **Transport** | SSE 流管理、WebSocket 连接、HTTP 请求封装 | 依赖 Service |
| **Service** | API 路由、请求校验、SSE 事件编排 | 依赖 Agent |
| **Agent** | LLM 对话、工具调用、记忆管理、情绪识别 | 依赖 Provider |
| **Provider** | LLM API 对接、TTS 合成、ASR 识别、G2P 映射 | 仅依赖外部服务 |

---

## 三、核心数据流

### 3.1 文字对话流程

```
用户输入文字
    |
    v
POST /api/chat (SSE)
    |
    v
emotional_agent.py
    |-- 1. LLM 生成回复 + 情绪标签
    |      .-- SSE: token* (流式打字)
    |
    |-- 2. 情绪标签
    |      .-- SSE: emotion {emotion, intensity}
    |
    |-- 3. Edge TTS 合成
    |      .-- SSE: audio {base64, duration_ms}
    |
    |-- 4. G2P -> Viseme 时间轴
    |      .-- SSE: viseme [{time_ms, level}]
    |
    .-- 5. SSE: done
```

### 3.2 语音对话流程

```
用户点击麦克风
    |
    v
MicRecorder.start() -> WAV 采集
    |
    v
MicRecorder.stop() -> WAV Blob
    |
    v
POST /api/asr (multipart)
    |
    v
SenseVoice -> 文字
    |
    v
自动填入输入框 -> sendMessage(text)
    |
    v
(走文字对话流程)
```

---

## 四、模块设计

### 4.1 前端模块

| 模块 | 文件 | 职责 |
|------|------|------|
| CubismManager | live2d/CubismManager.ts | Live2D SDK 初始化、模型加载、渲染循环 |
| EmotionDriver | live2d/EmotionDriver.ts | 情绪标签 -> Live2D Expression/Parameter 平滑过渡 |
| LipSyncDriver | live2d/LipSyncDriver.ts | Viseme 时间轴 -> Live2D 嘴型参数逐帧驱动 |
| AudioManager | audio/AudioManager.ts | Web Audio API: base64 -> 解码 -> 播放 |
| MicRecorder | audio/MicRecorder.ts | getUserMedia -> ScriptProcessor -> WAV 编码 |
| ChatClient | chat/ChatClient.ts | fetch + SSE 解析: emotion/token/audio/viseme/done |
| ASRClient | chat/ASRClient.ts | POST /api/asr, FormData, 超时处理 |

### 4.2 后端模块

| 模块 | 文件 | 职责 |
|------|------|------|
| routes | routes.py | API 路由: /api/chat /api/asr /api/health |
| emotional_agent | agent/emotional_agent.py | LLM Prompt + 情绪标签输出 + 回复生成 |
| graph | agent/graph.py | LangGraph StateGraph: agent_node -> tools_node |
| tools | agent/tools.py | 工具注册: 搜索/文件/天气/系统 |
| memory | agent/memory.py | Chroma 长期记忆 + SQLite 短期记忆 |
| tts_service | tts/tts_service.py | Edge TTS 合成封装 |
| g2p_service | tts/g2p_service.py | pypinyin 汉字 -> 声韵母拆分 |
| viseme_mapper | tts/viseme_mapper.py | 声韵母 -> 5级嘴型映射 |
| asr_service | asr/asr_service.py | SenseVoice sherpa-onnx 封装 |

---

## 五、SSE 事件协议

```
event: emotion
data: {"emotion":"happy","intensity":0.8}

event: token
data: {"text":"你好！"}

event: audio
data: {"base64":"...","format":"mp3","duration_ms":3200}

event: viseme
data: [{"time_ms":0,"level":3},{"time_ms":150,"level":2}]

event: done
data: {}
```

---

## 六、关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 2D vs 3D | 2D (Live2D) | 硬件友好、开发效率高、表情系统完善 |
| 前端框架 | React + Vite | Live2D 有 React 封装、复杂 UI 方便管理 |
| Agent 框架 | LangChain + LangGraph | 最丰富生态、LangGraph 状态图适合多步骤任务 |
| LLM 策略 | DeepSeek 云端 + Ollama 本地 | 日常本地低成本、复杂任务云端兜底 |
| 情绪 TTS | 暂不实现 | 硬件限制，仅保留 Live2D 表情变化 |
| 口型方案 | pypinyin G2P -> 5 级嘴型 | 2D 简化，5 级足够 |
| ASR | SenseVoice 离线 | 免费、五语种、带情绪检测 |
| 双协议 | SSE + WebSocket | SSE 适合 LLM 流，WebSocket 适合语音对话 |

---

*最后更新: 2026-07-24*
