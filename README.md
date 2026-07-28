# 🌸 Ruoxue — 多模态 AI Agent 数字人助手

> 基于 React + Live2D + LangGraph + FastAPI 的本地 AI Agent 数字人。
> 能看、能听、能说、能动、能用工具、能记事情。

---

## 功能总览

| 阶段 | 功能 | 状态 |
|------|------|:--:|
| Phase 1 | 文字聊天 — SSE 流式对话 + 情绪标签 + 会话记忆 | ✅ |
| Phase 2 | 语音交互 — ASR 语音识别 + TTS 语音合成 + 口型同步 | ✅ |
| Phase 3 | 数字人 — Live2D 模型渲染 + 表情驱动 + Motion 语境动画 | ✅ |
| Phase 4 | Agent — LangGraph + 5 个工具 + Chroma 记忆 + FAISS 知识库 | ✅ |

### Agent 工具

| 工具 | 功能 |
|------|------|
| `search_web` | DuckDuckGo 网页搜索 |
| `read_file` | 读取本地文件（文本 + PDF） |
| `get_weather` | 实时天气查询 |
| `list_dir` | 浏览目录 |
| `search_knowledge` | 搜索本地 FAISS 知识库 |

---

## 技术栈

```
前端：React 18 + TypeScript + Vite 6 + Live2D Cubism SDK 5 + WebGL
后端：Python 3.12 + FastAPI + LangGraph + LangChain + ChromaDB + FAISS
模型：DeepSeek-V4 + SenseVoice Small + Edge TTS + all-MiniLM-L6-v2
```

---

## 架构

```
┌─────────────────────────────────────────┐
│  React App (ChatPanel + Live2DCanvas)   │  前端 :5173
├─────────────────────────────────────────┤
│  SSE Stream / HTTP Upload / ASR         │  传输层
├─────────────────────────────────────────┤
│  FastAPI routes (/api/chat, /api/asr)   │  后端 :8000
├─────────────────────────────────────────┤
│  LangGraph Agent                        │
│  ┌─────────────────────────────────┐    │
│  │ agent_node → should_continue    │    │
│  │     │              │            │    │
│  │     └── tools ←────┘            │    │
│  │         (5 tools)               │    │
│  └─────────────────────────────────┘    │
├─────────────────────────────────────────┤
│  Memory: Chroma (long-term) + dict     │
│  Knowledge: FAISS (12k+ chunks)        │
├─────────────────────────────────────────┤
│  DeepSeek API / Edge TTS / SenseVoice   │  外部服务
└─────────────────────────────────────────┘
```

---

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/你的用户名/ruoxue-agent.git
cd ruoxue-agent
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key
```

### 3. 安装后端依赖

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

### 4. 下载模型（可选）

- **ASR 模型**：下载 [SenseVoice Small ONNX](https://github.com/k2-fsa/sherpa-onnx/releases) 放到 `model_assets/asr/sensevoice-small-int8/`
- **Live2D 模型**：下载 mao_pro 模型放到 `model_assets/live2d/mao_zh_Hans/`

> 没有模型也能跑——文字聊天和 Agent 功能不受影响。

### 5. 安装前端依赖

```bash
cd ../frontend
npm install
```

### 6. 启动

```bash
# 终端 1：启动后端
cd backend
python -m backend.main          # → http://localhost:8000

# 终端 2：启动前端
cd frontend
npm run dev                     # → http://localhost:5173
```

打开浏览器访问 `http://localhost:5173`

---

## 项目结构

```
ruoxue-agent/
├── backend/
│   ├── main.py                  FastAPI 入口
│   ├── routes.py                API 路由（chat / asr / upload / health）
│   ├── config.py                配置管理
│   ├── agent/
│   │   ├── agent_graph.py       LangGraph Agent 图
│   │   ├── tools.py             5 个工具定义
│   │   ├── memory.py            短期记忆
│   │   ├── chroma_memory.py     Chroma 长期记忆
│   │   ├── rag_service.py       FAISS 知识库
│   │   └── emotional_agent.py   [Legacy] 情绪系统常量
│   ├── tts/                     Edge TTS + G2P + Viseme
│   └── asr/                     SenseVoice 语音识别
├── frontend/
│   └── src/
│       ├── components/          ChatPanel / Live2DCanvas / VoiceButton
│       ├── hooks/               useChat / useLive2D / useVoice
│       ├── live2d/              Cubism SDK 封装 (Emotion/LipSync/Motion)
│       └── audio/               AudioManager / MicRecorder
├── docs/                        项目文档 + PRD + 阶段总结
├── .env.example                 环境变量模板
└── README.md
```

---

## 配置项

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_API_KEY` | — | **必填**，DeepSeek API Key |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | 模型名 |
| `RUOXUE_PORT` | `8000` | 后端端口 |
| `MAX_HISTORY_TURNS` | `20` | 对话历史轮数 |
| `TTS_VOICE` | `zh-CN-XiaoxiaoNeural` | Edge TTS 语音 |
| `WEATHER_PROXY` | — | 天气查询代理（国内用户建议设置） |

---

## License

MIT
