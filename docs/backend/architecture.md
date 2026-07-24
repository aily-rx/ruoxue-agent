# Ruoxue — 后端架构设计

> 版本: v1.0 | 日期: 2026-07-24

---

## 一、架构总览

```
FastAPI Application
|
+-- lifespan: 启动时预加载 ASR 模型
|
+-- routes.py (API 路由层)
|   |
|   +-- POST /api/chat      (SSE)  智能对话
|   +-- POST /api/asr       (HTTP) 语音识别
|   +-- GET  /api/health    (HTTP) 健康检查
|
+-- agent/ (Agent 层)
|   |
|   +-- emotional_agent.py   LLM 对话 + 情绪标签
|   |       |
|   |       +-- LangChain ChatOpenAI -> DeepSeek
|   |       +-- JsonOutputParser -> EmotionalResponse
|   |
|   +-- graph.py             LangGraph StateGraph (Phase 4)
|   +-- tools.py             LangChain Tools (Phase 4)
|   +-- memory.py            Chroma + SQLite (Phase 4)
|
+-- tts/ (语音合成管线)
|   |
|   +-- tts_service.py       Edge TTS 合成
|   +-- g2p_service.py       pypinyin G2P
|   +-- viseme_mapper.py     音素 -> 嘴型级别
|
+-- asr/ (语音识别)
    |
    +-- asr_service.py       SenseVoice sherpa-onnx
```

---

## 二、请求生命周期

```
1. 用户发送消息 (文字或语音)
2. routes.py 接收请求，提取参数
3. emotional_agent.py 调用 LLM 生成回复
4. LLM 流式返回 token + 情绪标签
5. routes.py 通过 SSE 推送 token (逐字)
6. routes.py 通过 SSE 推送 emotion (表情)
7. tts_service.py 合成语音 (后台异步)
8. viseme_mapper.py 生成嘴型时间轴
9. routes.py 通过 SSE 推送 audio
10. routes.py 通过 SSE 推送 viseme
11. routes.py 通过 SSE 推送 done
```

---

## 三、模块详细设计

### 3.1 routes.py

```
职责: API 路由定义 + SSE 事件编排

POST /api/chat (SSE):
  请求体: {"text": "你好", "session_id": "xxx"}
  响应: text/event-stream
  事件序列: emotion -> token* -> audio -> viseme -> done

POST /api/asr:
  请求体: multipart/form-data (WAV file)
  响应: {"text": "...", "language": "zh", "emotion": "neutral"}

GET /api/health:
  响应: {"status": "ok", "llm_available": true, "asr_available": true}
```

### 3.2 emotional_agent.py

```
职责: LLM 对话编排 + 情绪识别

类:
  Emotion (Enum): HAPPY/SAD/ANGRY/SURPRISED/NEUTRAL/THOUGHTFUL/WORRIED/EXCITED
  EmotionalResponse (Pydantic): {emotion, text, intensity}

函数:
  generate_reply(text, history) -> AsyncGenerator[SSEEvent]
    1. 构建 System Prompt (含情绪指南)
    2. LLM 流式生成
    3. 每个 chunk 判断: token 或 完整 JSON
    4. 解析 JSON -> emotion + text
    5. yield SSE 事件
```

### 3.3 tts_service.py

```
职责: Edge TTS 合成封装

函数:
  synthesize(text, voice="zh-CN-XiaoxiaoNeural") -> bytes
    1. edge_tts.Communicate(text, voice)
    2. 收集所有 audio chunk
    3. 返回完整 MP3 bytes

注意:
  - 不启用 WordBoundary (2D 不需要字词级时间戳)
  - 异步执行，不阻塞 SSE 流
```

### 3.4 viseme_mapper.py

```
职责: 中文 G2P -> 嘴型级别映射

映射逻辑:
  1. pypinyin 拆分汉字 -> 声母 + 韵母
  2. 声母查 INITIAL_MAP -> 嘴型级别
  3. 韵母查 FINAL_MAP -> 嘴型级别
  4. 取 max(声母级别, 韵母级别)
  5. 输出: [{time_ms, level}] (level: 0-4)

嘴型级别:
  0 = 闭嘴 (b/p/m)
  1 = 齿合微张 (d/t/n/l/j/q/x)
  2 = 半开 (g/k/h/zh/ch/sh)
  3 = 全开 (a/ao/ang)
  4 = 圆唇 (o/u/w/y)
```

### 3.5 asr_service.py

```
职责: SenseVoice 离线 ASR 封装

类:
  ASRService (单例模式)

方法:
  load_model()        -> 加载 ONNX 模型 (启动时调用)
  recognize(wav_bytes) -> {text, language, emotion}

模型:
  SenseVoice Small int8 量化版 (~229MB)
  支持: zh/en/ja/ko/yue
  输出: 文字 + 语种 + 情绪标签
```

---

## 四、依赖清单

```
# requirements.txt
fastapi>=0.110
uvicorn>=0.30
edge-tts
pypinyin>=0.50
sherpa-onnx
langchain>=0.3
langchain-core
langgraph
langchain-openai
httpx
pydantic>=2.0
python-multipart
```

---

*最后更新: 2026-07-24*
