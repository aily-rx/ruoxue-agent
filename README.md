# 🌸 Ruoxue — 多模态 AI Agent 数字人助手

> 基于 React + Live2D + LangGraph + FastAPI 的本地 AI Agent 数字人。
> 能看、能听、能说、能动、能用工具、能记事情。

---

## 功能总览

| 阶段 | 功能 | 状态 |
|------|------|:--:|
| Phase 1 | 文字聊天 — SSE 流式对话 + 情绪标签 + 会话记忆 | ✅ |
| Phase 2 | 语音交互 — ASR 语音识别 + Edge TTS 神经语音 + 口型同步 (Viseme) | ✅ |
| Phase 3 | 数字人 — Live2D 模型渲染 + 5 参数口型 + 表情驱动 + Motion 语境动画 | ✅ |
| Phase 4 | Agent — LangGraph + 5 个工具 + Chroma 记忆 + FAISS 知识库 | ✅ |

### Agent 工具

| 工具 | 实现 | 功能 |
|------|------|------|
| `search_web` | Tavily Search API | 结构化网页搜索 |
| `read_file` | Python stdlib + pypdf | 读取本地文件（文本 + PDF） |
| `get_weather` | wttr.in（零 API Key） | 实时天气查询 |
| `list_dir` | Python stdlib | 浏览目录 |
| `search_knowledge` | FAISS + all-MiniLM-L6-v2 | 搜索本地知识库 |

---

## 技术栈

```
前端：React 18 + TypeScript (strict) + Vite 6 + Live2D Cubism SDK 5 (WebGL 2)
后端：Python 3.12 + FastAPI + LangGraph + LangChain + ChromaDB + FAISS
TTS：  Edge TTS (29 个神经语音, 主引擎) + pyttsx3/SAPI5 (离线兜底)
ASR：  SenseVoice Small ONNX (sherpa-onnx)，情绪检测
LLM：  DeepSeek API (deepseek-v4-flash)
```

---

## 快速开始

### 前提条件

- Python 3.12+
- Node.js 22+
- DeepSeek API Key（注册即送免费额度）

### 1. 克隆并配置

```bash
git clone https://github.com/你的用户名/ruoxue-agent.git
cd ruoxue-agent
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
```

### 2. 安装后端

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate    macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

### 3. 安装前端

```bash
cd ../frontend
npm install
```

### 4. 启动

```bash
# 终端 1：后端（从项目根目录启动）
python -m backend.main          # → http://localhost:8000

# 终端 2：前端
cd frontend && npm run dev      # → http://localhost:5173
```

### 5. 可选：下载离线模型

| 模型 | 用途 | 说明 |
|------|------|------|
| SenseVoice Small | 离线语音识别 | 不装也能用（按钮隐藏） |
| Live2D mao_pro | 数字人模型 | 不装只显示文字聊天 |

> 两个模型都不装也能跑——文字聊天 + Agent + TTS 功能完整可用。

---

## 🐳 Docker 启动

```bash
cp .env.example .env && vim .env     # 填入 DEEPSEEK_API_KEY
docker compose up -d --build         # → http://localhost
docker compose logs -f               # 查看日志
docker compose down                  # 停止
```

---

## 项目结构

```
ruoxue-agent/
├── CLAUDE.md                    ← AI 协作指南 + 硬约束 (自动生效)
├── skills/                      ← 11 个可复用 Skill (skills-kit 部署)
│   └── CORE_RULES.md
├── skills-kit/                  ← Skill 套装源码 + 一键安装脚本
│   ├── init.sh / init.bat
│   └── skills/
├── backend/
│   ├── main.py                  FastAPI 入口 + CORS + lifespan
│   ├── routes.py                API 路由 (chat SSE / asr / upload / health)
│   ├── config.py                环境变量配置
│   ├── agent/
│   │   ├── agent_graph.py       LangGraph StateGraph + 三层 prompt + skill 注入
│   │   ├── skill_loader.py      关键词匹配 → 动态 skill 加载
│   │   ├── tools.py             5 个工具 (search/read/weather/list/knowledge)
│   │   ├── memory.py            短期记忆 (dict 滑动窗口)
│   │   ├── chroma_memory.py     Chroma 长期记忆 (语义检索)
│   │   ├── rag_service.py       FAISS 知识库 (文档索引 + 搜索)
│   │   └── emotional_agent.py   [Legacy] EMOTION_SYSTEM_PROMPT 常量
│   ├── tts/
│   │   ├── tts_service.py       Edge TTS (主) + pyttsx3 (兜底)
│   │   ├── g2p_service.py       中文 G2P (pypinyin 声韵母拆分)
│   │   └── viseme_mapper.py     韵母→5 参数口型序列 (多帧机制)
│   └── asr/
│       └── asr_service.py       SenseVoice ONNX 离线语音识别
├── frontend/
│   └── src/
│       ├── components/          ChatPanel / ChatBubble / Live2DCanvas / VoiceButton
│       ├── hooks/               useChat / useLive2D / useVoice
│       ├── live2d/              Cubism SDK 封装 (Emotion / LipSync / Motion)
│       ├── audio/               AudioManager / MicRecorder
│       └── chat/                ChatClient (SSE) / ASRClient
├── scripts/                     CI 辅助脚本 + 技能硬约束检查
├── docs/                        项目文档 + PRD + 阶段总结 + 经验记录
├── .env.example                 环境变量模板
└── docker-compose.yml
```

---

## Skill 系统

项目内置 **11 个可复用 Skill**（从 `skills-kit/` 一键安装），分层触发：

| 层级 | 触发方式 | 内容 |
|------|----------|------|
| 硬约束 | `CLAUDE.md` 自动加载，100% 生效 | 9 条铁律（先验证再过、改前读文件、批量后校验...） |
| 关键词匹配 | `agent_graph.py` + `skill_loader.py` 自动匹配用户意图 | 11 个场景 skill（TDD、Bug诊断、模块设计...） |
| 机器校验 | pre-commit / pre-push hook | lint / test / build |

```bash
# 安装到任意项目
cd skills-kit && bash init.sh /path/to/any-project
```

---

## 配置项

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_API_KEY` | — | **必填** |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | LLM 模型 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 地址 |
| `LLM_TEMPERATURE` | `0.7` | 生成温度 |
| `LLM_MAX_TOKENS` | `8192` | 最大 token |
| `RUOXUE_HOST` | `0.0.0.0` | 绑定地址 |
| `RUOXUE_PORT` | `8000` | 后端端口 |
| `MAX_HISTORY_TURNS` | `20` | 对话轮数窗口 |
| `TTS_VOICE` | `zh-CN-XiaoxiaoNeural` | Edge TTS 语音 (29 个可选) |
| `TTS_PROXY` | — | Edge TTS HTTP 代理 |
| `TAVILY_API_KEY` | — | Tavily 搜索 API Key（无 Key 则搜索不可用） |
| `ASR_MODEL_DIR` | `model_assets/asr/...` | SenseVoice 模型路径 |

---

## License

MIT
