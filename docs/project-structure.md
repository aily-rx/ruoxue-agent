# Ruoxue — 项目结构树

> 项目：Ruoxue 2D AI Agent 数字人 | 日期: 2026-07-24

---

```
ruoxue_agent/
├── Agent.md                          # 共享知识库索引
├── CLAUDE.md                         # AI Agent 工作指南
├── AstrBot/                          # AstrBot 参考代码库
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
│   │   ├── graph.py                   # LangGraph
│   │   ├── emotional_agent.py         # 情绪 Agent
│   │   ├── tools.py                   # 工具注册
│   │   └── memory.py                  # 记忆管理
│   ├── tts/                           # TTS 模块
│   │   ├── tts_service.py             # Edge TTS
│   │   ├── g2p_service.py             # pypinyin G2P
│   │   └── viseme_mapper.py           # 嘴型映射
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
| `backend/agent/` | Agent 智能体 | LangChain + LangGraph |
| `backend/tts/` | 语音合成管线 | edge-tts + pypinyin |
| `backend/asr/` | 语音识别 | sherpa-onnx |
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
