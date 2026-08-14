"""RAG 检索评估数据集（短板①：效果评估体系）。

每个样本：question（用户问法）+ fragment（期望命中的知识库原文片段）。
gold chunk 判定：知识库中所有包含 fragment 的 chunk。
命中判定：top-k 检索结果中存在任一 gold chunk。

数据集基于 faiss_data/ 中真实索引的 26 份文档构造（docs/ 技术方案、PRD、experience 复盘）。
新增样本时请确保 fragment 能在 knowledge_meta.json 的 docs 中找到（测试会自动校验）。
"""

EVAL_CASES: list[dict[str, str]] = [
    {
        "question": "本地多模态 AI Agent 数字人的 2D 渲染层使用什么技术？",
        "fragment": "Live2D Cubism SDK for Web 5",
    },
    {
        "question": "Ruoxue 后端框架是什么？",
        "fragment": "FastAPI + Uvicorn",
    },
    {
        "question": "开发流程的核心原则是什么？",
        "fragment": "需求文档 -> 原型设计 -> 架构设计 -> 编码实现",
    },
    {
        "question": "Live2D 模型渲染出现白色矩形覆盖部件是什么原因？",
        "fragment": "NoPremultipliedAlpha is not allowed",
    },
    {
        "question": "Live2D 模型出现两个模型重叠的重影，根因是什么？",
        "fragment": "CubismUpdateScheduler",
    },
    {
        "question": "数字人处于思考状态时表情如何表现？",
        "fragment": "单眉微挑、眼珠向上看",
    },
    {
        "question": "口型同步的整体流程是怎样的？",
        "fragment": "pypinyin G2P",
    },
    {
        "question": "中文口型级别是如何从拼音映射出来的？",
        "fragment": "声韵母 -> 嘴型级别",
    },
    {
        "question": "前端录音 MicRecorder 的状态机是什么？",
        "fragment": "idle -> recording -> recognizing -> idle",
    },
    {
        "question": "SenseVoice Small 模型支持哪些语种？",
        "fragment": "zh/en/ja/ko/yue",
    },
    {
        "question": "Agent 中如何判断是否要调用工具？",
        "fragment": "should_continue",
    },
    {
        "question": "LLM 选型的推荐策略是什么？",
        "fragment": "DeepSeek-V3 (云端，低成本)",
    },
    {
        "question": "聊天接口 POST /api/chat 的流式响应有哪些事件？",
        "fragment": "event: emotion",
    },
    {
        "question": "Live2D 表情不生效的根因是什么？",
        "fragment": "ParamMouthOpenY, ParamAngleX",
    },
    {
        "question": "表情切换生硬跳变的根因是什么？",
        "fragment": "intensity 缩放陷阱",
    },
    {
        "question": "emotion=happy 且文本含认同关键词时播放哪个动作？",
        "fragment": "mtn_02",
    },
    {
        "question": "docs/frontend 目录下有哪些 PRD 文档？",
        "fragment": "prd-live2d.md",
    },
    {
        "question": "语音输入录音的音频编码格式是什么？",
        "fragment": "16-bit PCM, mono, 16kHz",
    },
    {
        "question": "Phase 1 的流式回复是如何实现的？",
        "fragment": "SSE streaming reply (token by token)",
    },
    {
        "question": "SenseVoice Small 模型大小是多少？",
        "fragment": "229MB",
    },
    # ---- 2026-08-14 扩充: 覆盖架构分层/记忆设计/PRD 细节/前端模块等新主题 ----
    {
        "question": "项目规划中 Human-in-the-loop 是用来做什么的？",
        "fragment": "危险操作需用户确认",
    },
    {
        "question": "Agent 短期记忆的滑动窗口是最近多少轮？",
        "fragment": "最近 20 轮对话",
    },
    {
        "question": "PRD 里 RAG 知识库的切片参数是多少？",
        "fragment": "chunk_size=500, overlap=50",
    },
    {
        "question": "网页搜索工具的实现方案是什么？",
        "fragment": "Tavily API / DuckDuckGo",
    },
    {
        "question": "天气查询工具用的什么服务？",
        "fragment": "wttr.in / OpenWeather",
    },
    {
        "question": "前端负责音频播放的模块是哪个？",
        "fragment": "AudioManager.ts",
    },
    {
        "question": "中文口型同步的映射链路是什么？",
        "fragment": "pypinyin G2P → Live2D 参数",
    },
    {
        "question": "Edge TTS 相比开源方案的优势是什么？",
        "fragment": "Free with no API key",
    },
    {
        "question": "语音识别用的推理框架是什么？",
        "fragment": "sherpa-onnx",
    },
    {
        "question": "技术选型里 Edge TTS 的优点是？",
        "fragment": "免费、中文自然度高",
    },
    {
        "question": "前端情绪驱动模块是哪个文件？",
        "fragment": "EmotionDriver.ts",
    },
    {
        "question": "Live2D SDK 初始化和模型加载由哪个类负责？",
        "fragment": "CubismManager.ts",
    },
    {
        "question": "WordBoundary 时间戳怎么换算成毫秒？",
        "fragment": "(offset+duration)/10000 -> ms",
    },
    {
        "question": "会话记忆按什么维度隔离？",
        "fragment": "Per-session history isolation",
    },
    {
        "question": "短期记忆模块的实现方式是什么？",
        "fragment": "短期记忆 (dict 滑动窗口)",
    },
    {
        "question": "LLM 服务不可用时 API 返回什么错误事件？",
        "fragment": "LLM 服务不可用",
    },
    {
        "question": "情绪系统设计决策是什么？",
        "fragment": "保留 LLM 驱动情绪标签",
    },
    {
        "question": "架构分层的最上层叫什么？",
        "fragment": "Presentation Layer",
    },
    {
        "question": "前端 SSE 流接收器是哪个文件？",
        "fragment": "ChatClient.ts",
    },
    {
        "question": "前端 ASR 上传请求在哪个文件？",
        "fragment": "ASRClient.ts",
    },
    {
        "question": "前端负责录音状态管理的 hook 是什么？",
        "fragment": "useVoice.ts",
    },
    {
        "question": "口型同步驱动模块是哪个文件？",
        "fragment": "LipSyncDriver.ts",
    },
    {
        "question": "Phase 3 待机动画用什么文件循环播放？",
        "fragment": "mtn_01 loop",
    },
    {
        "question": "Live2D 渲染的预乘 Alpha 配置叫什么？",
        "fragment": "premultipliedAlpha",
    },
    {
        "question": "ASR 模型的完整名称是什么？",
        "fragment": "SenseVoice Small int8 ONNX model",
    },
    {
        "question": "情绪标签支持哪几种情绪？",
        "fragment": "happy/sad/angry/surprised/neutral/thoughtful/worried/excited",
    },
    {
        "question": "短期记忆最初设计用什么存储？",
        "fragment": "SQLite 存储当前会话历史",
    },
    {
        "question": "情绪表情的验收标准要求几种情绪切换正确？",
        "fragment": "8 种情绪均能正确切换",
    },
    {
        "question": "技术栈笔记里数字人参考项目的架构特点是什么？",
        "fragment": "SSE 流式架构",
    },
    {
        "question": "LLM 本地部署的备选方案是什么？",
        "fragment": "Ollama + Qwen2.5",
    },
]
