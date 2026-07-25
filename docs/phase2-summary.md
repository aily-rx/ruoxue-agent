# Phase 2 Complete Summary - Voice Interaction

> Version: v1.0 | Date: 2026-07-25 | Status: Done

---

## 1. Deliverables

### 1.1 Backend - ASR (Speech Recognition)

| Feature | Status | Key File |
|---------|--------|----------|
| SenseVoice Small int8 ONNX model | Done | asr_service.py |
| sherpa-onnx OfflineRecognizer | Done | from_sense_voice() |
| Startup preload (FastAPI lifespan) | Done | main.py |
| Graceful degradation if model missing | Done | try/except, chat still works |
| WAV decoding (stdlib wave) | Done | _decode_wav_to_float32() |
| 16-bit + 32-bit float PCM support | Done | struct.unpack per sample width |
| Multi-channel to mono averaging | Done | channel average |
| POST /api/asr endpoint | Done | UploadFile validation |
| Output: {text, language, emotion} | Done | SenseVoice tag parsing |
| Format tag stripping | Done | re.sub cleanup |
| Health check reports ASR status | Done | asr_available field |

### 1.2 Backend - TTS (Speech Synthesis)

| Feature | Status | Key File |
|---------|--------|----------|
| Edge TTS integration (free Microsoft TTS) | Done | tts_service.py |
| zh-CN-XiaoxiaoNeural voice | Done | TTS_VOICE config |
| Basic MP3 synthesis | Done | synthesize() |
| WordBoundary mode (word-level timestamps) | Done | synthesize_with_word_boundary() |
| HTTP proxy support (TTS_PROXY) | Done | edge_tts.Communicate(proxy=...) |
| TTS failure is non-fatal (chat continues) | Done | try/except in routes.py |
| MP3 duration from frame count | Done | _mp3_duration() fallback |

### 1.3 Backend - G2P + Viseme

| Feature | Status | Key File |
|---------|--------|----------|
| pypinyin G2P (initial + final split) | Done | g2p_service.py |
| CJK character detection (Unicode range) | Done | _CJK_RE regex |
| Pinyin split regex (zh/ch/sh handling) | Done | _PINYIN_SPLIT_RE |
| 5-parameter mouth system (A/I/U/E/O) | Done | viseme_mapper.py |
| All initials mapped (21 consonants) | Done | INIT dict |
| All finals mapped (simple+compound+nasal) | Done | _frames_for_final() |
| Multi-frame compound finals (1-3 frames) | Done | diphthongs/triphthongs |
| Punctuation -> closed mouth | Done | _s() zero frame |
| Unknown phoneme fallback | Done | default 0.2 shape |

### 1.4 Backend - SSE Protocol Extension

| Feature | Status | Key File |
|---------|--------|----------|
| event: audio (base64 MP3 + duration_ms) | Done | routes.py |
| event: viseme (5-param timeline) | Done | routes.py |
| WordBoundary -> audio duration | Done | (offset+duration)/10000 -> ms |
| Viseme duration scaling | Done | audioDurationMs / lastVisemeMs |
| WordBoundary per-char duration | Done | even split per word |
| Emoji stripping before TTS | Done | _strip_emoji() Unicode regex |
| Action tag stripping | Done | _strip_action_tags() keyword list |
| Symbol stripping (*#_~ etc.) | Done | _strip_symbols() |
| Triple-filter pipeline | Done | emoji -> action -> symbol |

### 1.5 Frontend - Recording + Playback

| Feature | Status | Key File |
|---------|--------|----------|
| Web Audio API microphone recording | Done | MicRecorder.ts |
| 16kHz PCM WAV encoding | Done | AudioContext conversion |
| Press-to-talk interaction | Done | VoiceButton onPointerDown/Up |
| Recording state animation (pulse ring) | Done | CSS pulse-ring |
| Real-time audio level display | Done | dB -> 0..1 scale |
| Recognizing spinner | Done | CSS spin animation |
| Error display (permission, device) | Done | voice-error span |
| AudioManager MP3 playback (base64) | Done | atob -> decodeAudioData |
| AudioContext lifecycle | Done | _getContext() lazy init |
| Stop previous audio on new message | Done | stop() before play |
| Playback ended callback | Done | source.onended |
| Audio-viseme sync | Done | onPlayStarted timestamp |

### 1.6 Frontend - Voice UI

| Feature | Status | Key File |
|---------|--------|----------|
| VoiceButton component | Done | VoiceButton.tsx |
| useVoice hook (state machine) | Done | useVoice.ts |
| ASRClient HTTP upload | Done | ASRClient.ts |
| WAV Blob upload | Done | FormData + fetch |
| Voice -> sendMessage | Done | handleVoiceRecognized |
| Disable voice during generation | Done | disabled={isLoading} |
| Cancel on pointer leave | Done | onPointerLeave |

---

## 2. Architecture Decisions

### 2.1 Offline ASR (SenseVoice) over Cloud API

**Decision**: Use local SenseVoice ONNX model instead of cloud ASR.

**Reason**: Zero cost, no network dependency, privacy-preserving. Trade-off: ~229MB model download, 2-5s startup. Preloaded at server startup so recognition is instant.

### 2.2 HTTP ASR over WebSocket streaming

**Decision**: Use HTTP POST /api/asr with complete WAV upload instead of WebSocket streaming.

**Reason**: Phase 1 did not implement WebSocket. Press-to-talk + complete WAV upload is simpler and sufficient. WebSocket streaming deferred to Phase 4.

### 2.3 Edge TTS over local TTS

**Decision**: Use Microsoft Edge TTS (free cloud) instead of local TTS engine.

**Reason**: Edge TTS quality significantly better than open-source alternatives. Free with no API key. WordBoundary mode provides precise timing for viseme sync. Trade-off: requires internet.

### 2.4 5-parameter mouth over single ParamMouthOpenY

**Decision**: Drive 5 Live2D mouth parameters (A/I/U/E/O) instead of single openness.

**Reason**: mao_pro model uses these 5 params natively. Single ParamMouthOpenY does not exist. 5-param captures mouth nuances (round vs spread vs open) impossible with a scalar.

### 2.5 Per-char duration + global scale

**Decision**: Generate viseme frames with WordBoundary per-character durations, then apply global scale factor.

**Reason**: WordBoundary gives word-level not phoneme-level timing. Per-character distribution is approximate. Global scale ensures total viseme duration matches actual audio, catching accumulated errors.

---

## 3. Bug Fix History

| # | Bug | Root Cause | Fix | Lesson |
|---|-----|-----------|-----|--------|
| 1 | Viseme ahead of audio | LipSyncDriver used own timer; AudioManager async decode took 50-300ms | onPlayStarted callback passes exact audio start timestamp | Async decode creates timing gap; bridge via shared timestamp |
| 2 | TTS pronouncing emoji | Emoji passed directly to Edge TTS | Strip via Unicode regex before synthesis | LLM output contains emoji; filter before audio pipeline |
| 3 | TTS pronouncing action tags | LLM outputs parenthetical descriptions despite prompt | Strip with keyword regex _ACTION_TAG_RE | Prompts are not guarantees; defensive filtering needed |
| 4 | TTS choking on markdown symbols | Formatting symbols have no phonetic representation | Strip with _SYMBOL_RE before synthesis | Clean display text != clean TTS text |

---

## 4. Known Limitations

| # | Issue | Notes |
|---|-------|-------|
| 1 | ASR model download not automated | User must place model in model_assets/asr/ |
| 2 | ASR accuracy not benchmarked | No formal WER measurement |
| 3 | Edge TTS network dependency | Requires internet; TTS_PROXY for restricted environments |
| 4 | No streaming TTS | Full LLM reply completed before TTS starts; adds 1-3s latency |
| 5 | WordBoundary char distribution approximate | Even split per word, not validated against phonemes |
| 6 | Single TTS voice | No voice selection UI or per-emotion modulation |
| 7 | Recording requires user gesture | Web Audio requires user interaction before AudioContext starts |

---

## 5. File Manifest

### New files (Phase 2)

backend/asr/__init__.py
backend/asr/asr_service.py
backend/tts/__init__.py
backend/tts/tts_service.py
backend/tts/g2p_service.py
backend/tts/viseme_mapper.py
frontend/src/components/VoiceButton.tsx
frontend/src/chat/ASRClient.ts
frontend/src/hooks/useVoice.ts
frontend/src/audio/AudioManager.ts
frontend/src/audio/MicRecorder.ts

### Modified files (Phase 2)

backend/main.py (ASR preload in lifespan)
backend/routes.py (POST /api/asr, audio/viseme events, TTS filter pipeline)
backend/config.py (TTS_VOICE, TTS_PROXY, ASR_MODEL_DIR)
frontend/src/components/ChatPanel.tsx (VoiceButton, AudioManager, sync, motion detection)
frontend/src/App.tsx (emotion bridge to Live2DCanvas)

---

## 6. Phase 3 Handoff Notes

1. Viseme protocol (5-param timeline) ready -> LipSyncDriver consumes directly
2. Emotion SSE event already drives Live2DCanvas -> EmotionDriver mapping
3. AudioManager onPlayStarted provides sync timestamp -> LipSyncDriver startTime
4. TTS filtering (emoji/action/symbol) ensures clean audio -> no Phase 3 changes
5. ASR returns emotion from voice tone -> could complement LLM emotion in future
6. MicRecorder 16kHz PCM is standard format -> reusable for future audio input

---

*Last updated: 2026-07-25*