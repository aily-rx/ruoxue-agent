# Ruoxue — API 文档

> 版本: v1.0 | 日期: 2026-07-24
> 协议: HTTP/1.1 | 格式: JSON / SSE (text/event-stream) / multipart/form-data
> Base URL: http://localhost:8000

---

## 1. POST /api/chat — 智能对话 (SSE 流式)

发送用户消息，返回 SSE 流式响应（文字 + 情绪 + 语音 + 口型）。

**请求:**
```
POST /api/chat
Content-Type: application/json

{
  "text": "你好，今天天气怎么样？",
  "session_id": "user_abc_123"
}
```

**响应 (text/event-stream):**

```
event: emotion
data: {"emotion":"happy","intensity":0.6}

event: token
data: {"text":"今天"}

event: token
data: {"text":"天气"}

event: token
data: {"text":"不错！"}

event: audio
data: {"base64":"//uQxAAAA...","format":"mp3","duration_ms":2800}

event: viseme
data: [{"time_ms":0,"level":2},{"time_ms":120,"level":3},{"time_ms":300,"level":2},{"time_ms":450,"level":0}]

event: done
data: {}
```

**事件说明:**

| 事件 | 数据 | 说明 |
|------|------|------|
| emotion | {emotion, intensity} | 情绪标签 + 强度 (0.0-1.0) |
| token | {text} | 逐字文本 |
| audio | {base64, format, duration_ms} | MP3 音频 (base64) |
| viseme | [{time_ms, level}] | 嘴型时间轴 (level: 0-4) |
| done | {} | 流结束 |

**情绪枚举值:** happy / sad / angry / surprised / neutral / thoughtful / worried / excited

**错误响应:**
```
event: error
data: {"message":"LLM 服务不可用","code":503}
```

---

## 2. POST /api/asr — 语音识别

上传 WAV 录音文件，返回识别文本。

**请求:**
```
POST /api/asr
Content-Type: multipart/form-data

file: audio.wav (16-bit PCM, mono, 16kHz)
```

**响应:**
```json
{
  "text": "你好今天天气怎么样",
  "language": "zh",
  "emotion": "neutral"
}
```

**错误响应:**
```json
{
  "text": "",
  "language": "unknown",
  "emotion": "neutral",
  "error": "识别失败：音频过短 (< 0.5s)"
}
```

---

## 3. GET /api/health — 健康检查

**响应:**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "llm_available": true,
  "asr_available": true
}
```

---

## 4. POST /api/chat/stream (WebSocket) — Phase 2 语音对话

> Phase 2 实现，用于双向实时语音对话。

**连接:** `ws://localhost:8000/api/chat/stream?session_id=xxx`

**客户端 -> 服务端:**
```json
{"type": "audio", "data": "<base64 WAV chunk>"}
{"type": "stop", "data": null}
```

**服务端 -> 客户端:**
```json
{"type": "token", "data": {"text": "今天"}}
{"type": "emotion", "data": {"emotion": "happy", "intensity": 0.6}}
{"type": "audio", "data": {"base64": "...", "format": "mp3"}}
{"type": "viseme", "data": [{"time_ms": 0, "level": 3}]}
{"type": "done", "data": null}
```

---

*最后更新: 2026-07-24*
