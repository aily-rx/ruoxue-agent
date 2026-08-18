# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 硬约束（始终生效，不需要关键词触发）

以下规则来自 `skills/CORE_RULES.md`，**每次对话自动执行，不可跳过**。

### 行为准则

1. **声称过关前先跑验证** — 说"没问题了""应该能过""ALL PASSED"之前，必须先实际执行项目的 CI 全部命令，亲眼看到全部 PASS。没跑过就是没跑过。
2. **修改前先读文件** — 改任何文件前，先 `Read` 目标文件确认当前内容。不凭记忆和猜测——代码的当前状态比你的记忆准确。
3. **批量操作后必须验证** — 批量替换（sed/正则/全局 Edit）之后，必须 `Read` 回文件内容确认修改正确。不依赖命令 exit code 作为唯一验证手段。
4. **违规直接承认** — 如果用户指出你违反了以上准则，直接承认并说明具体违反了哪条，不要辩解。修完后把教训写进对应的 skill 文件。

### 编码铁律

5. **先读后写** — 写任何代码前，先回答三个问题：①依赖的数据源在哪？②真实结构确认了吗？（不是臆测，是实际读出来的）③假设和实际一致吗？不凭文档/记忆编参数名，必须读实际文件。
6. **不凭猜测** — 不用"应该是""默认值是 0"之类的推断代替实际读取。Live2D 参数名不是 ParamMouthOpenY 而是 ParamA——除非你读过 `.exp3.json`。
7. **防御性输出** — LLM 输出进入 TTS/JSON解析/代码执行前，必须先经过显式过滤管道。生成给用户看的内容必须可追溯、无臆测值。
8. **依赖方向正确** — 上层依赖下层，核心层只依赖外部库。模块间通信走 EventBus，无直接跨层 import。不引入循环依赖。

### Skill 使用

9. 在 `skills/` 目录中搜索是否有对应的 skill 文件。skill 文件的 front matter 标注了 `name` 和 `trigger_keywords`。对于复杂或高风险任务，主动匹配并加载对应 skill。

---

## 项目信息

## 项目概述

**Ruoxue** — 基于 React + Live2D Cubism SDK 5 + LangChain + FastAPI 构建的本地多模态 AI Agent 数字人助手。

- **当前阶段**：Phase 1-4 已完成；Human-in-the-loop 已实现（2026-08-14，`HITL_ENABLED=true` 时工具调用前经 SSE `tool_request` 事件请求用户确认，`POST /api/hitl-confirm` 恢复，超时默认拒绝）。
- **前端**：React 18 + TypeScript（strict 模式）+ Vite 6，端口 5173，通过 Vite proxy 将 /api 转发到 localhost:8000。
- **后端**：Python FastAPI + LangChain + langchain-openai，调用 DeepSeek API，端口 8000。
- **设计令牌**：紫色主色 #7c5cbf，定义在 frontend/src/style.css 的 :root 中，禁止硬编码颜色/间距。关键变量：--primary / --primary-hover / --primary-light、--surface / --surface-alt / --bg、--text / --text-secondary / --text-muted、--border、--radius / --radius-sm、--shadow、--header-h: 56px、--bubble-max-w: 70%。

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

# 创建 .env 配置文件（填入 DeepSeek API Key）
cp .env.example .env

# 必须从项目根目录启动（import 使用 backend.xxx 绝对路径）
# 本地依赖已装在 backend/venv（Windows: backend/venv/Scripts/python.exe）
cd ..
python -m backend.main            # 启动 FastAPI 服务 → http://localhost:8000
```

> **注意**：`backend/agent/`、`backend/tts/`、`backend/asr/` 均包含 `__init__.py`，使其成为 Python 包以支持 `from backend.agent.memory import memory` 等绝对导入路径。

### 后端自测

```bash
# 测试 SSE 流式对话
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"text":"你好"}'

# 健康检查（含 LLM/ASR 状态）
curl http://localhost:8000/api/health

# Swagger 文档
open http://localhost:8000/docs
```

## Docker 部署（2026-08-18 配置）

`docker-compose.yml` 一键起全栈：**backend（8000）+ frontend（80）** 两个独立容器。frontend 是 nginx 静态托管 + 反向代理，`location /api` → `http://backend:8000`（**用 compose 服务名跨容器通信，禁止写 localhost/127.0.0.1**——容器内 localhost 是自己）。前端生产代码用相对路径 `/api`，`vite.config.ts` 里的 `localhost:8000` 仅本地 dev proxy。

```bash
docker compose up -d --build   # 构建 + 启动（日常改代码就这一条，增量重建秒级）
docker compose logs -f backend # 跟踪日志
docker compose down            # 停止（--volumes 才删数据，bind mount 目录始终保留）
docker compose config          # 校验配置（含 .env 插值结果）
```

### 镜像源与代理（本地构建无需任何代理）

- **backend Dockerfile**：pip 用清华源（`-i https://pypi.tuna.tsinghua.edu.cn/simple`）；**frontend Dockerfile**：npm 用 npmmirror（`--registry=https://registry.npmmirror.com`）。实测国内直连 1-2s vs 官方源 15s+ 超时。
- 本机 `~/.docker/config.json` 的 `proxies` **已移除**（备份：`config.json.bak-proxy`、`config.json.bak`）。若需恢复，**必须用 `http://host.docker.internal:7890`，不能用 `127.0.0.1:7890`**——后者在构建容器内是容器自己，pip/npm 会 `ProxyError: Connection refused` 直接失败。
- **运行期不需要代理**：DeepSeek / Tavily 直连（国内可直连），ASR/TTS 纯本地离线。

### 镜像固化 vs 卷挂载（代码死、数据活）

| 文件 | 方式 | 改后生效方式 |
|---|---|---|
| backend/frontend 代码 | 拷入镜像（COPY） | `docker compose up -d --build` 增量重建（秒级） |
| `requirements.txt` / `package*.json` | pip/npm 层 | 重下依赖（分钟级，需网络） |
| `model_assets/`（ASR 模型） | `:ro` 挂载 `/app/model_assets` | 直接替换宿主机文件，零操作 |
| `chroma_data/`、`faiss_data/` | 挂载 | 直接写，零操作 |
| `skills/` | `:ro` 挂载 `/app/skills` | 直接写，零操作 |

> 容器内 skills 路径是 `/app/skills`（`agent_graph.py` 从 `__file__` 三级 `parent` 计算：`/app/backend/agent/agent_graph.py → /app/skills`）。**build context 是 `backend/`，根目录的 `skills/` 拷不进镜像**，只能靠 compose 挂载——移除挂载后 skill 注入静默降级（不报错，skill 匹配直接返回 None）。

### 环境变量与健康检查

- `.env` 必须放**项目根目录**：`docker compose` 的 `${VAR:-}` 插值只读根目录 `.env`，backend 容器内 `config.py` 也找 `/app/.env`。根目录 `.env` 已被 `.gitignore` 忽略。
- `backend/.env` 仅本地运行用（config.py 二次加载 override），**含 `HTTP_PROXY=127.0.0.1:7890` 本地代理——不要把它带进 compose/容器**（容器内该地址不可达，会让 httpx 全部请求失败）。
- 验证：`curl http://localhost:8000/api/health` → `{"status":"ok","llm_available":true,"asr_available":true}`（llm_available 依赖根目录 .env 的 key）；`curl -o /dev/null -w "%{http_code}" http://localhost/` 应为 200。
- CI（`.github/workflows/ci-cd.yml`）lint+test 通过后推镜像到 **GHCR**（`ghcr.io/<repo>/ruoxue-backend|frontend`），与本地 compose 构建互不影响。

## 协作规范

修改代码前必须遵循三步流程：
1. 分析 — 理解问题，定位涉及的文件和影响范围
2. 给方案 — 提供 2-3 个可选方案（含优劣对比），或先提问确认需求细节
3. 等确认 — 用户明确说"改"或选择方案后再动手
例外（可直接执行）：语法错误修复、格式化、文档补充、git commit / git status 等查询操作。

## 架构

### 全栈分层（从上到下依赖）

```
Presentation     React App (ChatPanel, Live2DCanvas, VoiceButton)
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
├── main.py              FastAPI 入口 + CORS + lifespan（启动时预加载 ASR 模型）
├── routes.py            API 路由：POST /api/chat (SSE: token/emotion/audio/viseme/done),
│                        POST /api/asr (WAV 上传), GET /api/health
├── config.py            环境变量配置（LLM、会话、TTS、ASR 参数）
├── agent/
│   ├── emotional_agent.py   [Legacy] 提供 EMOTION_SYSTEM_PROMPT 常量
│   ├── agent_graph.py       Phase 4: LangGraph StateGraph + 三层 prompt
│   ├── tools.py             Phase 4: 5 个工具 (search/read/weather/list/knowledge)
│   ├── memory.py            短期记忆（dict 滑动窗口）
│   ├── chroma_memory.py     Phase 4: Chroma 长期记忆（语义检索）
│   └── rag_service.py       Phase 4: FAISS 知识库（文档索引 + 语义搜索）
├── tts/
│   ├── tts_service.py       Edge TTS 合成（基础 + WordBoundary 模式）
│   ├── g2p_service.py       中文 G2P（pypinyin：汉字→声母/韵母）
│   └── viseme_mapper.py     韵母→5 参数口型序列（支持复合韵母多帧）
└── asr/
    └── asr_service.py       SenseVoice ONNX 离线语音识别（含情绪检测）
```

### 前端模块结构

```
frontend/src/
├── main.tsx                   React 入口
├── App.tsx                    根组件：左右分栏（ChatPanel + Live2DCanvas）
├── style.css                  CSS 设计令牌 + 全站样式 + 响应式
├── components/
│   ├── ChatPanel.tsx          聊天面板：消息列表 + 快捷回复 + 输入栏 + 语音按钮
│   ├── ChatBubble.tsx         单条消息气泡（用户/AI，情绪表情 emoji）
│   ├── Live2DCanvas.tsx       Live2D WebGL canvas 封装 + ref API 暴露
│   └── VoiceButton.tsx        按住说话按钮（录音状态动画）
├── chat/
│   ├── ChatClient.ts          SSE 客户端（fetch + ReadableStream）
│   └── ASRClient.ts           ASR HTTP 客户端（WAV 上传）
├── hooks/
│   ├── useChat.ts             chat 状态管理（消息列表、send/abort/clear、SSE 回调）
│   ├── useLive2D.ts           Live2D 模型生命周期（创建/销毁 CubismManager）
│   └── useVoice.ts            录音 + ASR 状态管理（按压、识别、错误）
├── audio/
│   ├── AudioManager.ts        MP3 base64 播放（带 onended 回调）
│   └── MicRecorder.ts         Web Audio API 麦克风录制（16kHz PCM WAV）
└── live2d/
    ├── index.ts               统一导出
    ├── CubismManager.ts       Live2D 模型生命周期编排器（加载/渲染/销毁）
    ├── EmotionDriver.ts       情绪→Live2D 表情映射 + 两阶段渐变过渡
    ├── LipSyncDriver.ts       Viseme 时间线→5 参数口型驱动（EMA 平滑）
    ├── IdleMotionDriver.ts    随机小幅自然微动（随机游走 + lerp）
    └── sdk/                   Live2D Cubism SDK for Web 5（TypeScript 封装）
```

### 前端组件树（当前）

```
App
├── ChatPanel
│   ├── Header (logo + 连接状态)
│   ├── ChatBubble[]  (用户右对齐紫色，AI 左对齐灰色 + 情绪 emoji 头像)
│   ├── QuickReplies  (首次进入时显示 3 个快捷按钮)
│   └── InputBar      (VoiceButton + textarea + 发送/停止按钮)
└── Live2DCanvas
    └── <canvas> WebGL 渲染 (通过 useLive2D hook 管理 CubismManager)
```

### 状态管理

- `useChat` hook 管理聊天状态：`messages[]`、`isLoading`、`error`、SSE 回调（onEmotion/onToken/onAudio/onViseme/onDone）
- `useVoice` hook 管理语音状态：`isRecording`、`isRecognizing`、`audioLevel`、`voiceError`
- `useLive2D` hook 管理模型状态：`Live2DState { loaded, error }`
- App 通过 `useState<Live2DData>` 桥接 chat ↔ live2d（emotion/intensity/visemes 单向数据流 props）
- Live2DCanvas 通过 `useImperativeHandle` 暴露同步 ref API（`setEmotion`/`resetEmotion`/`playMotion`/`stopAllMotions`/`startIdleMotion`），绕过 React 渲染周期延迟
- `sessionId` 使用 `useRef` 持久化，同一页面保持同一会话

## 核心数据流

### SSE 对话流（当前完整协议）

```
用户输入 → POST /api/chat (SSE)
  → agent_graph.run_agent_stream:
    1. LLM 流式生成回复（含 [EMOTION: xxx|0.0] 前缀标签）
    2. 解析情绪标签 → SSE: event:emotion
    3. 逐 token 推送 → SSE: event:token*（routes.py 做 emoji/动作标签/符号过滤）
  → routes.py 逐句切分（句末标点; 残句>40字在逗号处兜底强切）→ 后台串行合成
    每句: Edge TTS(WordBoundary) → audio(seq) + viseme(seq) 逐片推送,
    与后续 token 生成并行 —— 首句音频距首字 ~1.5s
    4. 文本完成 + 记忆落库 → SSE: event:done（不等最后一句 TTS）
```

### SSE 事件协议

```
event: emotion    data: {"emotion":"happy","intensity":0.8}
event: token      data: {"text":"你好！"}
event: audio      data: {"base64":"...","format":"mp3","duration_ms":3200,"seq":0}
event: viseme     data: {"frames":[{"time_ms":0,"A":0.95,...}, ...],"seq":0}
event: done       data: {}          # 文本完成即发, 音频可能在其后继续流
event: tool_request data: {"request_id":"...","tool_calls":[...],"timeout_s":60}  # HITL 开启时
event: error      data: {"message":"...","code":500}
```

### Live2D 渲染循环顺序（每帧）

```
1. _motionManager.updateMotion()     ← motion 驱动身体+头部 (基准层, 优先级 0/1)
2. emotionDriver.update()             ← 面部表情覆盖 motion
3. lipSyncDriver.update()             ← 口型覆盖 motion
4. _updateScheduler.onLateUpdate()    ← 物理/姿态/眨眼
5. _model.update()                    ← 最终化
6. WebGL 绘制
```

> 此顺序确保 motion 不会覆盖表情和口型参数。

### Motion 语境绑定流程

```
用户发送消息 → ChatPanel.handleSend():
  1. 停止所有 motion → setEmotion('thoughtful') → 等待 LLM 回复
  2. 每收到 token → detectMotion(): 累计文本 + 情绪匹配触发 motion
  3. 收到 audio → AudioManager.playBase64()
  4. 音频结束 → scheduleEmotionReset():
     1.5s 后 → setEmotion('neutral') → startIdleMotion() (mtn_01 循环)

Motion 触发规则:
  - 待机：mtn_01 循环（优先级 0）
  - emotion=happy + 认同关键词 → mtn_02（优先级 1）
  - 魔法关键词 → special_01（优先级 1）
  - 每轮回答只触发一次（motionTriggeredRef 防重复）
```

## 关键技术细节

### 情绪标签机制

LLM 在回复文本开头嵌入 `[EMOTION: happy|0.5]` 格式的标签。`emotional_agent.py` 使用正则 `EMOTION_TAG_RE` 从流式文本中提取，提取后移除标签，剩余文本作为 token 流推送。支持 8 种情绪：happy/sad/angry/surprised/neutral/thoughtful/worried/excited，intensity 0.0-1.0。若 LLM 未输出情绪标签，默认使用 `neutral/0.3`。

### EmotionDriver 两阶段过渡

非 neutral 情绪切换采用两阶段过渡，避免旧表情预设残留：
1. **Phase 1**（200ms）：所有 22 个参数快照→neutral 全量值（眼形/眉角等 expression preset 效果归零）
2. **Phase 2**（按情绪配置 transitionMs）：neutral→目标情绪的参数值
3. Expression preset 延迟到 Phase 2 结束后才应用

neutral 切换为单阶段直接 lerp。

### TTS + Viseme 管线

1. LLM 回复完成 → `routes.py` 做 emoji/动作标签/符号三重过滤得到 `tts_text`
2. Edge TTS WordBoundary 模式合成 → 得到 MP3 + 词边界时间戳
3. 从词边界计算真实音频时长 `audioDurationMs`
4. `text_to_viseme_sequence()` → G2P（pypinyin 声韵母拆分）→ `viseme_mapper` 多帧映射 → 初始序列
5. 用 `audioDurationMs / viseme_last_time_ms` 缩放系数校正整条序列时间轴
6. 前端 `LipSyncDriver` 接收缩放后的序列，渲染时做帧间 lerp + EMA 平滑（SMOOTH=0.2）

### Viseme 多帧机制

`viseme_mapper.py` 对复合韵母生成 1-3 帧（简单单元音 1 帧，双元音/鼻韵母 2 帧），每帧 ~30ms 间距。驱动 5 个口型参数：`ParamA`（开口）、`ParamI`（展唇）、`ParamU`（圆唇）、`ParamE`（半开）、`ParamO`（圆开）。

### 会话记忆

`ConversationMemory` 是全局单例，按 `session_id` 存储对话历史。使用滑动窗口（默认 `MAX_HISTORY_TURNS=20`，即 40 条消息）。消息格式兼容 LangChain 的 `MessagesPlaceholder`。

### 配置管理

所有配置通过 `backend/config.py` 的环境变量读取，带默认值。关键配置项：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | `your-api-key-here` | DeepSeek API 密钥 |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | 模型名称 |
| `LLM_TEMPERATURE` | `0.7` | 生成温度 |
| `LLM_MAX_TOKENS` | `8192` | 最大 token 数 |
| `MAX_HISTORY_TURNS` | `20` | 对话历史窗口大小 |
| `RUOXUE_PORT` | `8000` | 后端端口 |
| `TTS_VOICE` | `zh-CN-XiaoxiaoNeural` | Edge TTS 语音 |
| `TTS_PROXY` | 空 | HTTP 代理（用于 Edge TTS） |
| `ASR_MODEL_DIR` | `model_assets/asr/sensevoice-small-int8` | SenseVoice 模型路径 |

### ASR 服务

SenseVoice Small int8 ONNX 模型（sherpa-onnx），在 FastAPI lifespan 启动时预加载。返回含情绪标签的识别结果（文本/语种/情绪）。前端通过按住说话→MicRecorder 录制 16kHz PCM WAV→POST /api/asr 上传。

### CubismManager 模型加载流程

```
1. CubismFramework.startUp() + initialize()
2. model3.json → CubismModelSettingJson
3. moc3 → CubismUserModel.loadModel()
4. Renderer → createRenderer() + startUp() + loadShaders()
5. 纹理上传（UNPACK_PREMULTIPLY_ALPHA_WEBGL + RGBA）
6. Physics + Pose → 注册 CubismUpdateScheduler
7. EyeBlink → 自动眨眼（使用 model setting 参数）
8. IdleMotionDriver.attach()
9. Expressions (.exp3.json) → EmotionDriver.attach()
10. Motions (.motion3.json) + setEffectIds + _isLoop
11. LipSyncDriver.attach()
12. startIdleMotion() (mtn_01 循环)
```

## 已知陷阱

### SSE 跨 chunk 事件类型丢失

**症状**：流式对话中部分或全部 token 被静默丢弃，回复显示不完整。

**根因**：FastAPI `StreamingResponse` 可能将一个 SSE 事件的 `event:` 行和 `data:` 行分到不同的网络 chunk 发送。`ChatClient.ts` 逐 chunk 读取，如果 `currentEvent` 变量在 `while(true)` 循环内声明，每次迭代都会被重置，导致跨 chunk 时事件类型丢失。

**修复**：将 `currentEvent` 声明提升到 `while(true)` 循环之前：

```typescript
let currentEvent = "";  // ← 必须在 while 循环外部
while (true) {
  const { done, value } = await reader.read();
  // ...
}
```

### Live2D 白色矩形

**根因**：预乘 Alpha 不匹配。需要 Canvas context `premultipliedAlpha: true`，Renderer `setIsPremultipliedAlpha(true)`，纹理上传时 `UNPACK_PREMULTIPLY_ALPHA_WEBGL`。

### Live2D 模型重影

**根因**：缺少 Physics + Pose 数据加载和 `CubismUpdateScheduler` 管线。必须加载 physics3.json + pose3.json，创建 updater 并注册到 scheduler，在 `_model.update()` 前调用 `onLateUpdate()`。

### Motion 多并存冲突

**根因**：`startMotion()` 不清旧队列，多个 motion 同时驱动同一参数。`playMotion()` 内部必须先 `stopAllMotions()`。循环 motion 不触发 `onFinishedMotion` 回调，不能靠回调切换，需手动计时。

### Emotion 过渡同帧竞态

**根因**：两阶段过渡的 Phase 1 完成检查和 Phase 2 触发检查在同一帧内先后执行，Phase 2 先触发清空 `_phaseTwo`，Phase 1 结束逻辑立即清空 `_paramTarget`。修复：调整检查顺序，先检查 expression cleanup，再检查 Phase 2 触发。

### Canvas resize 导致 WebGL 上下文丢失

**根因**：设置 canvas.width/height 到相同值也会销毁 WebGL 上下文。`_resizeCanvas` 必须在赋值前做相等性检查：`if (this._canvas.width === w && this._canvas.height === h) return;`

## 阶段规划

| 阶段 | 状态 | 内容 |
|---|---|---|
| Phase 1 | ✅ 完成 | 文字聊天：SSE 流式对话 + 情绪标签 + 会话记忆 |
| Phase 2 | ✅ 完成 | 语音交互：SenseVoice ASR + Edge TTS + Viseme 收口 + 麦克风 |
| Phase 3 | ✅ 完成 | Live2D 数字人：模型渲染 + 情绪驱动 + 口型同步 + Motion 语境绑定 |
| Phase 4 | ✅ 完成 | Agent 智能体：LangGraph + 5 工具 + Chroma 记忆 + FAISS RAG |

> **测试与质量现状（2026-08-18 更新）**：后端 143 个测试（unit + integration + eval，2026-08-18 收集），行覆盖率 **82%**；
> 前端 vitest + ESLint 已配置；ruff + mypy + pre-commit/pre-push hooks 全量生效。
> 测试命令：`python -m pytest backend/tests/ -q --asyncio-mode=auto`（后端，项目根目录执行）、
> `cd frontend && npm run test`（前端）、`cd backend && ruff check .`（lint）。
> RAG 检索评估（`backend/tests/eval/`）依赖真实 `faiss_data/` 索引 + `DEEPSEEK_API_KEY`，CI 上自动跳过、本地手动跑。

## 开发顺序约定

按依赖方向从下往上编码，保证每个模块写完就能独立测试：

- **后端顺序**：`config → agent/emotional_agent → agent/agent_graph → agent/tools → agent/memory → agent/chroma_memory → agent/rag_service → tts/asr → routes → main`
- **前端顺序**：`App → ChatPanel → ChatBubble → ChatClient → useChat → Live2D 层`

每个 Phase 启动前必须先完成：PRD 文档 → API 接口定义 → 原型/布局 → 依赖清单 → 前后端数据协议对齐。详见 `docs/development-workflow.md`。

## AstrBot 目录

`AstrBot/` 是一个独立的开源项目（v4.26.7，AGPL-3.0），作为多平台 LLM 聊天机器人框架的参考模板。**它不是 Ruoxue 源码的一部分**，不应被修改。

## CubismSdkForWeb-5-r.5 目录

Live2D Cubism SDK for Web 5 官方源码（TypeScript），`frontend/src/live2d/sdk/` 为其复制/适配版本。原始 SDK 目录仅供参考，实际开发修改在 `frontend/src/live2d/sdk/` 中进行。

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
| `docs/backend/prd-lipsync.md` | 口型同步 PRD（pypinyin G2P、5 级嘴型、多帧机制） |
| `docs/backend/prd-voice.md` | 语音交互 PRD（SenseVoice ASR、Edge TTS） |
| `docs/frontend/prd-live2d.md` | Live2D 集成方案（SDK、组件架构、React 封装） |
| `docs/frontend/prd-emotion-expression.md` | 情绪表情 PRD（8 种情绪、Live2D 参数映射） |
| `docs/frontend/prd-motion-context.md` | Motion 语境绑定 PRD（待机/关键词触发/恢复、优先级体系） |
| `docs/frontend/prototype-phase1-chat.md` | Phase 1 聊天界面 ASCII 原型 |
| `docs/frontend/dependencies.md` | 各 Phase 依赖清单 |
| `docs/phase3-summary.md` | Phase 3 完成总结（交付清单、架构决策、Bug 记录、遗留问题） |
| `docs/phase2-summary.md` | Phase 2 完成总结（ASR/TTS/G2P/Viseme 管线、录放音、音画同步） |
| `docs/phase1-summary.md` | Phase 1 完成总结（SSE 流式、情绪标签、会话记忆、聊天 UI） |
| `Agent.md` | 共享知识库索引（经验文档触发机制、命名规范、架构规则） |
| `text/README.md` | **过程性文档索引**（面试准备/评估数据/短板复盘——一律归 `text/` 分类，不进 `docs/`） |
| `text/rag/rag-eval.md` | RAG 检索评估基线（Recall@5 0.95 / MRR 0.749） |
| `text/rag/rag-generation-eval.md` | RAG 生成评估基线（RAGAS：faithfulness 0.905 / relevancy 0.595 / precision 0.781） |
| `text/rag/rag-real-chain-claim-audit.md` | 真实链路 claim 级抽检（faithfulness 0.176 低分构成拆解、三类归因） |
<!-- SKILLS:START -->

| Skill | 触发关键词 | 位置 |
|-------|-----------|------|
| codebase-design | 模块设计 (设计模块...) | `skills/engineering/codebase-design/` |
| code-review | 代码审查 (审查...) | `skills/engineering/code-review/` |
| defensive-output | LLM输出防护 (过滤...) | `skills/engineering/defensive-output/` |
| diagnose-bugs | Bug诊断 (bug...) | `skills/engineering/diagnose-bugs/` |
| implement | 实现 (按依赖方向...) | `skills/engineering/implement/` |
| prototype-first | 原型先行 (页面布局...) | `skills/engineering/prototype-first/` |
| read-before-code | 先读后写 (对接...) | `skills/engineering/read-before-code/` |
| tdd | TDD测试驱动 (写测试...) | `skills/engineering/tdd/` |
| grill-me | 方案追问 (分析一下...) | `skills/productivity/grill-me/` |
| handoff | 会话交接 (总结一下...) | `skills/productivity/handoff/` |
| verify | 提交前验证 (提交...) | `skills/productivity/verify/` |

<!-- SKILLS:END -->
