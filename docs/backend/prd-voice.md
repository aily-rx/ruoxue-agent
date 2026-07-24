# Ruoxue — 语音交互 PRD

> 版本: v1.0 | 日期: 2026-07-24 | 状态: Phase 2 设计

---

## 一、需求概述

用户可以通过麦克风与数字人对话，数字人通过 TTS 语音回复。

---

## 二、语音输入 (ASR)

### 2.1 前端录音

```
MicRecorder 状态机:
  idle -> recording -> recognizing -> idle
```

- 编码: 16-bit PCM, mono, 16kHz
- 自动停止: 静音 2s 或 60s 超时
- 最小长度: 0.5s (过滤误触)
- 实时音量回调: onLevel(db) -> UI 声波动画

### 2.2 后端识别

```
SenseVoice Small int8 量化版
- 模型大小: ~229MB
- 支持语种: zh/en/ja/ko/yue (自动检测)
- 输出: {text, language, emotion}
- 启动预加载: FastAPI lifespan 事件
```

---

## 三、语音输出 (TTS)

### 3.1 方案

使用 Edge TTS (免费):
- 声音: zh-CN-XiaoxiaoNeural (女声)
- 格式: MP3
- 参数调节: rate/pitch 可调 (Phase 3 情绪化语调暂不做)

### 3.2 播放

前端 AudioManager:
```
base64 MP3 -> ArrayBuffer -> decodeAudioData -> AudioBufferSourceNode
```

---

## 四、语音对话模式 (Phase 2)

```
WebSocket 双向通道:

客户端 -> 服务端:
  {"type": "audio_chunk", "data": "<base64>"}  流式上传
  {"type": "audio_end", "data": null}           录制结束

服务端 -> 客户端:
  {"type": "asr_result", "data": {"text": "..."}}
  {"type": "token", "data": {"text": "..."}}
  {"type": "emotion", "data": {"emotion": "happy"}}
  {"type": "audio", "data": {"base64": "..."}}
  {"type": "viseme", "data": [{...}]}
  {"type": "done", "data": null}
```

> 降级方案: 录音 -> HTTP /api/asr -> 文字 -> HTTP /api/chat (SSE)，WebSocket 非必需。

---

## 五、验收标准

- [ ] 中文语音识别准确率 > 90%
- [ ] 端到端延迟 < 3s (录音结束 -> 开始播放回复)
- [ ] 噪音环境下不误触发
- [ ] SenseVoice 模型启动时间 < 5s
- [ ] 音频播放与口型同步

---

*最后更新: 2026-07-24*
