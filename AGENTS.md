# AGENTS.md — Ruoxue 工作区指引

**Ruoxue**：基于 React 18 + Live2D Cubism SDK 5 + LangGraph + FastAPI 的本地多模态 AI 数字人助手（能聊、能听、能说、能动、能用工具、有记忆）。

> **动手前必读**：`CLAUDE.md`（硬约束 + 完整架构/数据流/已知陷阱，本仓库的权威参考）和 `Agent.md`（跨端经验知识库索引）。改 RAG/检索相关代码前先读 `text/rag/rag-eval.md` 与 `text/retrospective/短板*.md` 复盘文档。

## 常用命令

后端必须从**项目根目录**启动（绝对导入 `backend.xxx`，各子包均有 `__init__.py`）：

```bash
cd backend && pip install -r requirements.txt -r requirements-dev.txt
python -m backend.main            # 启动 API → http://localhost:8000 (从根目录)
python -m pytest backend/tests/ -v --asyncio-mode=auto   # 后端测试
cd backend && ruff check .        # 后端 lint
```

前端（`cd frontend`）：

```bash
npm install && npm run dev        # → http://localhost:5173 (/api 代理到 8000)
npm run build                     # 生产构建 (tsc + vite build)
npm run lint && npm run test      # eslint + vitest
```

也支持 `make lint / make test / make dev / make build`。pre-commit / pre-push hooks 已配置（lint + test + build 校验，tdd 只检查新增文件）。

## 架构分层（上层依赖下层，禁止循环依赖）

```
Presentation  frontend/src/components (ChatPanel, Live2DCanvas, VoiceButton)
Transport     chat/ChatClient (SSE), chat/ASRClient, audio/AudioManager, audio/MicRecorder
Service       backend/routes.py, backend/main.py, backend/config.py
Agent         backend/agent/ (agent_graph, tools, memory, chroma_memory, rag_service)
Provider      DeepSeek API, Edge TTS, SenseVoice ASR (sherpa-onnx), pypinyin G2P, FAISS/Chroma
```

- `backend/agent/emotional_agent.py` 是 **Legacy**（只提供 `EMOTION_SYSTEM_PROMPT` 常量），别往里加逻辑。
- 前端 hook：`useChat`（聊天状态 + SSE 回调）、`useVoice`（录音/ASR）、`useLive2D`；Live2DCanvas 通过 `useImperativeHandle` 暴露同步 ref API。
- 记忆：`agent/memory.py` 短期（滑动窗口，`MAX_HISTORY_TURNS=20`）+ `agent/chroma_memory.py` 长期（语义检索）+ `agent/rag_service.py`（FAISS + 混合检索 BM25/jieba，见 `text/rag/rag-eval.md`）。

## 编码约定

- **先读后写、不凭猜测**：改文件前先 Read；Live2D 参数名必须从 `.exp3.json` 确认（不是 `ParamMouthOpenY`，是 `ParamA` 等 5 口型参数）。声称验证通过前必须真跑 CI 命令（见 CLAUDE.md 硬约束）。
- **CSS 设计令牌**：颜色/间距/圆角定义在 `frontend/src/style.css` 的 `:root`（主色 `#7c5cbf`），禁止硬编码。
- **TTS 文本必须过滤**：LLM 输出进 TTS 前由 `routes.py` 做 emoji/动作标签/符号三重过滤，防注入。
- **SSE 协议**（`POST /api/chat`）：`event: emotion → token* → audio → viseme → done`，错误为 `error`。`ChatClient.ts` 解析时 `currentEvent` 必须声明在 `while(true)` 循环外，否则跨 chunk 丢事件。
- **Skill 系统**：`skills/` 下 11 个可复用 skill（CORE_RULES + 关键词触发），复杂/高风险任务先查 `skills/` 匹配；`skills-kit/` 是套装源码。
- 项目文档多为中文，新文档请保持中文。

## 已知陷阱（详见 CLAUDE.md「已知陷阱」）

- SSE 跨 chunk 事件类型丢失（`currentEvent` 作用域）；Live2D 白色矩形（预乘 Alpha 三处必须一致）；模型重影（缺 Physics/Pose + `CubismUpdateScheduler`）；motion 冲突（`playMotion` 前先 `stopAllMotions`）；canvas resize 会销毁 WebGL 上下文（赋值前先做相等性检查）。
- LLM 输出情绪标签格式 `[EMOTION: happy|0.5]`，由正则提取并移除，默认 `neutral/0.3`。

## 数据与运行时

- `backend/venv/`、`frontend/node_modules/`、`chroma_data/`、`faiss_data/`、`model_assets/` 是运行时产物，勿提交/勿清理语义数据。
- 环境配置走 `backend/config.py` 读 `.env`（`DEEPSEEK_API_KEY` 必填）；`docker-compose.yml` 可一键起全栈。
- Windows 平台：用 Git Bash；`.env.example` 复制为 `.env`。

## 文档索引（改对应区域前先读）

`CLAUDE.md`（硬约束/架构/数据流/陷阱）· `Agent.md`（经验索引）· `docs/architecture.md` · `docs/development-workflow.md` · `docs/backend/api.md`（SSE 协议）· `docs/backend/prd-agent.md`

## 文档归属约定（重要）

- `docs/` 只放**正式设计文档**（PRD、架构、API 协议、阶段总结）。
- **过程性/准备性/复盘类文档一律放 `text/`，并按分类放**（详见 `text/README.md`）：
  - `text/interview/` — 面试准备、知识图谱、问答记录
  - `text/rag/` — RAG 评估基线、实验数据、优化记录
  - `text/retrospective/` — 短板补全过程复盘
- 生成新文档时先判断类型再归类，并在 `text/README.md` 索引登记。
