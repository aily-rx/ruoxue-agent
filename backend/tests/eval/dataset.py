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
]
