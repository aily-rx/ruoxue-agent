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

# —— 分片 TTS: 每句文本完成后即合成推送（与后续 token 生成并行）——
event: audio
data: {"base64":"//uQxAAAA...","format":"mp3","duration_ms":2800,"seq":0}

event: viseme
data: {"frames":[{"time_ms":0,"A":0.5,"I":0.2,"U":0,"E":0.1,"O":0.1}, ...],"seq":0}

event: audio
data: {"base64":"//uQxBBBB...","format":"mp3","duration_ms":1900,"seq":1}

event: viseme
data: {"frames":[...],"seq":1}

# done 在文本完成 + 记忆落库后立即发出（不再等最后一句 TTS）
event: done
data: {}
```

**事件说明:**

| 事件 | 数据 | 说明 |
|------|------|------|
| emotion | {emotion, intensity} | 情绪标签 + 强度 (0.0-1.0) |
| token | {text} | 逐字文本 |
| audio | {base64, format, duration_ms, seq} | 单句音频 (base64), seq 为句子序号, 前端按序排队播放 |
| viseme | {frames, seq} | 单句嘴型时间轴, 与同 seq 的 audio 配对 |
| done | {} | 文本流结束（音频可能仍在流式推送中） |
| tool_request | {request_id, tool_calls, timeout_s} | HITL 工具确认请求（HITL_ENABLED=true 时） |

**分片规则:** 按句末标点（。！？!?；;…）切句; 残句超 40 字且模型漏标点时在最近逗号处兜底强切。
**viseme frame:** {time_ms, A, I, U, E, O} — 5 口型参数（0.0-1.0）, 与同 seq 音频时长对齐。

**情绪枚举值:** happy / sad / angry / surprised / neutral / thoughtful / worried / excited

**错误响应:**
```
event: error
data: {"message":"LLM 服务不可用","code":503}
```

> 兼容性说明: 旧协议（整段 audio/viseme 不带 seq、done 在最后）已被替换;
> 旧前端收到带 seq 的 audio/viseme 会解析失败, 需与后端同步升级。

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
