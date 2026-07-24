# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**Ruoxue** — 基于 React + Live2D + LangChain + FastAPI 构建的本地多模态 AI Agent 数字人助手。

- **当前阶段**：Phase 1（文字聊天）已完成。Phase 2（语音）、Phase 3（Live2D 数字人）、Phase 4（Agent 工具/LangGraph）待开发。
- **前端**：React 18 + TypeScript + Vite 6，端口 5173，通过 Vite proxy 将 `/api` 转发到 localhost:8000。
- **后端**：Python FastAPI + LangChain + langchain-openai，调用 DeepSeek API，端口 8000。
- **设计令牌**：紫色主色 `#7c5cbf`，定义在 `frontend/src/style.css` 的 `:root` 中，禁止硬编码颜色/间距。

## 常用命令

### 前端

```bash
cd frontend
npm install          # 安装依赖
npm run dev          # 启动开发服务器 → http://localhost:5173
npm run build        # 生产构建（tsc + vite build）
npm run preview      # 预览生产构建
```

### 后端

```bash
cd backend
pip install -r requirements.txt   # 安装 Python 依赖

# 必须从项目根目录启动（import 使用 backend.xxx 绝对路径）
cd ..
python -m backend.main            # 启动 FastAPI 服务 → http://localhost:8000
```

### 后端自测

```bash
# 测试 SSE 流式对话
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"text":"你好"}'

# 健康检查
curl http://localhost:8000/api/health

# Swagger 文档
open http://localhost:8000/docs
```

## 协作规范

修改代码前必须遵循三步流程：

1. **分析** — 理解问题，定位涉及的文件和影响范围
2. **给方案** — 提供 2-3 个可选方案（含优劣对比），或先提问确认需求细节
3. **等确认** — 用户明确说"改"或选择方案后再动手

例外（可直接执行）：语法错误修复、格式化、文档补充、`git commit` / `git status` 等查询操作。

## 架构

### 全栈分层（从上到下依赖）

```
Presentation     React App (ChatPanel, Live2D Canvas, VoiceButton)
    ↑
Transport        ChatClient (SSE), ASRClient, AudioManager, MicRecorder
    ↑
Service          FastAPI routes (/api/chat, /api/asr, /api/health)
    ↑
Agent            emotional_agent (LangChain + DeepSeek), memory, graph, tools
    ↑
Provider         DeepSeek API, Edge TTS, SenseVoice ASR, pypinyin G2P
```

### 后端模块结构

```
backend/
├── main.py              FastAPI 入口 + CORS + lifespan
├── routes.py            API 路由：POST /api/chat (SSE), GET /api/health
├── config.py            环境变量配置（LLM、会话、TTS、ASR 参数）
├── agent/
│   ├── emotional_agent.py   LangChain agent：LLM 流式生成 + [EMOTION:] 标签解析
│   └── memory.py            会话记忆（dict 滑动窗口，Phase 4 计划升级到 Chroma）
├── tts/                 TTS/G2P 模块（Phase 2 实现，当前为空壳 __init__.py）
└── asr/                 ASR 模块（Phase 2 实现，当前为空壳 __init__.py）
```

### 前端模块结构

```
frontend/src/
├── main.tsx               React 入口
├── App.tsx                根组件（Phase 1 仅包含 ChatPanel）
├── style.css              CSS 设计令牌 + 全站样式
├── components/
│   ├── ChatPanel.tsx      聊天面板：消息列表 + 快捷回复 + 输入栏
│   └── ChatBubble.tsx     单条消息气泡（用户/AI，情绪表情 emoji）
├── chat/
│   └── ChatClient.ts      SSE 客户端：fetch + ReadableStream 解析 event stream
└── hooks/
    └── useChat.ts         chat 状态管理 Hook（消息列表、send/abort/clear）
```

### 前端组件树（Phase 1）

```
App
└── ChatPanel
    ├── Header (logo + 连接状态)
    ├── ChatBubble[]  (用户右对齐紫色，AI 左对齐灰色 + 情绪 emoji 头像)
    ├── QuickReplies  (首次进入时显示 3 个快捷按钮)
    └── InputBar      (textarea + 发送/停止按钮)
```

### 状态管理

- `useChat` hook 管理全部聊天状态：`messages[]`、`isLoading`、`error`
- 每个 message 对象：`{id, role, content, emotion?, intensity?, isStreaming?, timestamp}`
- `sessionId` 使用 `useRef` 持久化，同一页面保持同一会话

## 核心数据流

### SSE 对话流

```
用户输入 → POST /api/chat (SSE)
  → emotional_agent.py:
    1. LLM 流式生成回复（含 [EMOTION: xxx|0.0] 前缀标签）
    2. 解析情绪标签 → SSE: event:emotion
    3. 逐 token 推送 → SSE: event:token*
    4. 完成 → SSE: event:done
  → 前端 ChatClient 解析 event stream → useChat 更新 messages[]
```

### SSE 事件协议

```
event: emotion    data: {"emotion":"happy","intensity":0.8}
event: token      data: {"text":"你好！"}
event: audio      data: {"base64":"...","format":"mp3","duration_ms":3200}   (Phase 2+)
event: viseme     data: [{"time_ms":0,"level":3}...]                         (Phase 3+)
event: done       data: {}
event: error      data: {"message":"...","code":500}
```

## 关键技术细节

### 情绪标签机制

LLM 在回复文本开头嵌入 `[EMOTION: happy|0.5]` 格式的标签。`emotional_agent.py` 使用正则 `EMOTION_TAG_RE` 从流式文本中提取，提取后移除标签，剩余文本作为 token 流推送。支持 8 种情绪：happy/sad/angry/surprised/neutral/thoughtful/worried/excited，intensity 0.0-1.0。若 LLM 未输出情绪标签，默认使用 `neutral/0.3`。

### 前端情绪展示

`ChatBubble.tsx` 将情绪映射为 emoji 图标显示在 AI 头像位置（如 happy→😊、sad→😢），目前仅做视觉展示，Phase 3 将驱动 Live2D 表情参数。

### 会话记忆

`ConversationMemory` 是全局单例，按 `session_id` 存储对话历史。使用滑动窗口（默认 `MAX_HISTORY_TURNS=20`，即 40 条消息）。消息格式兼容 LangChain 的 `MessagesPlaceholder`。Phase 4 计划升级为 Chroma 向量存储。

### 配置管理

所有配置通过 `backend/config.py` 的环境变量读取，带默认值。关键配置项：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | `your-api-key-here` | DeepSeek API 密钥 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名称 |
| `LLM_TEMPERATURE` | `0.7` | 生成温度 |
| `LLM_MAX_TOKENS` | `2048` | 最大 token 数 |
| `MAX_HISTORY_TURNS` | `20` | 对话历史窗口大小 |
| `RUOXUE_PORT` | `8000` | 后端端口 |

## 阶段规划

| 阶段 | 状态 | 内容 |
|---|---|---|
| Phase 1 | ✅ 完成 | 文字聊天：SSE 流式对话 + 情绪标签 + 会话记忆 |
| Phase 2 | ⏳ 待开发 | 语音交互：SenseVoice ASR + Edge TTS + 麦克风 |
| Phase 3 | ⏳ 待开发 | Live2D 数字人：模型加载 + 情绪驱动 + 口型同步 |
| Phase 4 | ⏳ 待开发 | Agent 智能体：LangGraph + 工具调用 + Chroma 记忆 + RAG |

## 开发顺序约定

按依赖方向从下往上编码，保证每个模块写完就能独立测试：

- **后端顺序**：`config → agent/emotional_agent → agent/memory → routes → main`
- **前端顺序**：`App → ChatPanel → ChatBubble → ChatClient → useChat`

每个 Phase 启动前必须先完成：PRD 文档 → API 接口定义 → 原型/布局 → 依赖清单 → 前后端数据协议对齐。详见 `docs/development-workflow.md`。

## AstrBot 目录

`AstrBot/` 是一个独立的开源项目（v4.26.7，AGPL-3.0），作为多平台 LLM 聊天机器人框架的参考模板。它有自己的 `AGENTS.md` 和开发规范，不应与本项目代码混淆。

## 文档索引

| 文档 | 内容 |
|---|---|
| `docs/architecture.md` | 全栈架构设计（五层分层、数据流、SSE 协议、模块设计） |
| `docs/development-workflow.md` | 开发流程规范（前后端编码顺序、原型设计、联调、Git 规范） |
| `docs/project-structure.md` | 完整目录树 + 依赖方向 + 各目录职责 |
| `docs/AI_Agent_数字人助手技术栈学习笔记.md` | 总方案：技术栈选型、情绪系统、口型方案、分阶段计划 |
| `docs/backend/api.md` | API 文档（SSE 事件格式、请求/响应 schema） |
| `docs/backend/architecture.md` | 后端架构（路由层、Agent 层、TTS 管线、ASR 模块） |
| `docs/backend/prd-agent.md` | Agent 智能体 PRD（LangGraph、工具、记忆、RAG） |
| `docs/backend/prd-lipsync.md` | 2D 口型同步 PRD（pypinyin G2P、5 级嘴型） |
| `docs/backend/prd-voice.md` | 语音交互 PRD（SenseVoice ASR、Edge TTS、WebSocket） |
| `docs/frontend/prd-live2d.md` | Live2D 集成方案（SDK、组件架构、React 封装） |
| `docs/frontend/prd-emotion-expression.md` | 情绪表情 PRD（8 种情绪、Live2D 参数映射） |
| `docs/frontend/prototype-phase1-chat.md` | Phase 1 聊天界面 ASCII 原型（组件树、PC/移动端、全部状态） |
| `docs/frontend/dependencies.md` | 各 Phase 依赖清单（前端 npm + 后端 pip） |
| `Agent.md` | 共享知识库索引（经验文档触发机制、命名规范、架构规则） |
