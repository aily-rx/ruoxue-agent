# Ruoxue — 项目结构树

> 项目：Ruoxue 2D AI Agent 数字人 | 日期: 2026-07-30

---

```
ruoxue_agent/
├── README.md                          # 项目说明
├── CHANGELOG.md                       # 变更日志
├── Agent.md                          # 共享知识库索引 (Bug 记录/经验/规范)
├── CLAUDE.md                         # AI 协作指南 + 硬约束 (自动生效)
├── .env.example                      # 环境变量模板
├── docker-compose.yml                # Docker 编排
├── skills/                           # 部署的 Skill 文件 (11 个)
│   ├── CORE_RULES.md                 # 行为准则
│   ├── engineering/                  # 工程类 skill (8 个)
│   └── productivity/                 # 效率类 skill (3 个)
├── skills-kit/                       # Skill 套装源码 (可分发)
│   ├── init.sh / init.bat            # 一键安装到任意项目
│   ├── CLAUDE.md                     # 模板
│   └── skills/                       # Skill 源文件
├── scripts/                          # CI 辅助脚本
│   ├── verify.sh                     # 全量 CI 验证
│   └── check-*.sh                    # 各 skill 硬约束检查
│
├── docs/                             # 项目文档
│   ├── AI_Agent_数字人助手技术栈学习笔记.md  # 总方案
│   ├── architecture.md               # 全栈架构设计
│   ├── project-structure.md          # 本文档
│   ├── frontend/
│   │   ├── prd-live2d.md            # Live2D 集成方案
│   │   ├── prd-emotion-expression.md # 情绪表情 PRD
│   │   └── experience/               # 前端通用经验
│   └── backend/
│       ├── architecture.md           # 后端架构
│       ├── api.md                    # API 文档
│       ├── prd-agent.md             # Agent 智能体 PRD
│       ├── prd-lipsync.md           # 口型同步 PRD
│       ├── prd-voice.md             # 语音交互 PRD
│       └── experience/               # 后端通用经验
│
├── frontend/                          # React 前端工程
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx                   # React 入口
│       ├── App.tsx                    # 应用根组件
│       ├── style.css                  # 全局样式
│       ├── components/                # React 组件
│       │   ├── ChatPanel.tsx          # 聊天面板
│       │   ├── ChatBubble.tsx         # 消息气泡
│       │   ├── Live2DCanvas.tsx       # Live2D 画布
│       │   ├── VoiceButton.tsx        # 语音按钮
│       │   └── EmotionIndicator.tsx   # 情绪指示器
│       ├── live2d/                    # Live2D 封装
│       │   ├── CubismManager.ts       # SDK + 模型加载
│       │   ├── EmotionDriver.ts       # 情绪驱动
│       │   └── LipSyncDriver.ts       # 口型驱动
│       ├── audio/                     # 音频模块
│       │   ├── AudioManager.ts        # Web Audio 播放
│       │   └── MicRecorder.ts         # 麦克风录音
│       ├── chat/                      # 对话模块
│       │   ├── ChatClient.ts          # SSE 流接收
│       │   └── ASRClient.ts           # ASR 请求
│       └── hooks/                     # React Hooks
│           ├── useChat.ts
│           ├── useLive2D.ts
│           └── useVoice.ts
│
├── backend/                           # Python 后端
│   ├── requirements.txt
│   ├── main.py                        # FastAPI 入口
│   ├── config.py                      # 配置管理
│   ├── routes.py                      # API 路由
│   ├── agent/                         # Agent 模块
│   │   ├── agent_graph.py             # LangGraph StateGraph + 三层 prompt
│   │   ├── skill_loader.py            # 关键词匹配 → 动态 Skill 注入
│   │   ├── emotional_agent.py         # [Legacy] 情绪系统常量
│   │   ├── tools.py                   # 5 个工具 (search/read/weather/list/knowledge)
│   │   ├── memory.py                  # 短期记忆 (dict 滑动窗口)
│   │   ├── chroma_memory.py           # ChromaDB 长期记忆 (语义检索)
│   │   └── rag_service.py            # FAISS 知识库 (文档索引 + 搜索)
│   ├── tts/                           # TTS 模块
│   │   ├── tts_service.py             # Edge TTS (主) + pyttsx3 (兜底)
│   │   ├── g2p_service.py             # pypinyin G2P (声韵母拆分)
│   │   └── viseme_mapper.py           # 5 参数口型序列 (多帧机制)
│   └── asr/                           # ASR 模块
│       └── asr_service.py             # SenseVoice
│
└── model_assets/                      # 模型资源
    ├── live2d/                        # Live2D 模型
    │   ├── ruoxue.model3.json
    │   ├── ruoxue.moc3
    │   ├── textures/
    │   ├── motions/
    │   └── expressions/
    └── asr/                           # ASR 模型
        └── sensevoice-small-int8/     # ~229MB
```

---

## 各目录职责速查

| 目录 | 定位 | 依赖关系 |
|------|------|----------|
| `docs/` | 项目文档 | 无 |
| `frontend/` | React 前端工程 | Vite + Live2D SDK |
| `frontend/src/live2d/` | Live2D 封装层 | Live2D Cubism SDK |
| `frontend/src/audio/` | 音频采集/播放 | Web Audio API |
| `frontend/src/chat/` | 后端通信 | fetch + EventSource |
| `backend/` | FastAPI 服务 | Python 依赖 |
| `skills/` | 可复用 Skill 文件 | `skill_loader.py` 动态加载 |
| `skills-kit/` | Skill 套装源码 | 一键安装到任意项目 |
| `scripts/` | CI 辅助脚本 | Shell 脚本工具集 |
| `backend/agent/` | Agent 智能体 | LangChain + LangGraph + Skill |
| `backend/tts/` | 语音合成管线 | Edge TTS + pyttsx3 + pypinyin |
| `backend/asr/` | 语音识别 | sherpa-onnx SenseVoice |
| `model_assets/` | 模型资源 | 独立管理 |

---

## 依赖方向

```
React App  ---> Live2D Drivers ---> Live2D SDK
    |
    v
ChatClient/ASRClient ---> SSE/HTTP ---> FastAPI routes
                                            |
                                            v
                                    emotional_agent.py
                                            |
                                    +-------+-------+
                                    |               |
                               LangChain LLM    LangGraph
                                    |               |
                              DeepSeek/Ollama   tools.py
                                    |
                              tts_service.py
                              g2p_service.py
                              viseme_mapper.py
```

---

*更新于 2026-07-24*
