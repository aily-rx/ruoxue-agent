# Phase 3 Complete Summary - Live2D Digital Human

> Version: v1.0 | Date: 2026-07-25 | Status: Done

---

## 1. Deliverables

### 1.1 Model Rendering

| Feature | Status | Key File |
|---------|--------|----------|
| Cubism SDK 5 init | Done | CubismManager.ts |
| .moc3 model loading | Done | CubismManager.loadModelFromUrl() |
| Texture upload (premultiplied alpha) | Done | RGBA + UNPACK_PREMULTIPLY_ALPHA_WEBGL |
| Physics simulation | Done | physics3.json -> CubismPhysicsUpdater |
| Pose correction | Done | pose3.json -> CubismPoseUpdater |
| EyeBlink auto-blink | Done | 2-5s random, model setting params |
| ResizeObserver | Done | canvas follows CSS layout |
| Model lifecycle (load/dispose) | Done | useLive2D hook, cleanup on unmount |

### 1.2 Emotion Expressions

| Feature | Status | Key File |
|---------|--------|----------|
| 8 emotion mapping | Done | EmotionDriver.ts |
| Expression preset (.exp3.json) | Done | 8 presets, verified per-file |
| Per-parameter driving (22 params) | Done | mouth/eyes/brows/cheek |
| Two-phase smooth transition | Done | Phase 1 (200ms neutral) -> Phase 2 (target) |
| Deferred expression preset | Done | avoids instant preset + smooth lerp split |
| Intensity scaling (0.0-1.0) | Done | neutral not scaled |
| Auto-reset to neutral after reply | Done | 1.5s after audio ends |

### 1.3 Lip-sync

| Feature | Status | Key File |
|---------|--------|----------|
| pypinyin G2P (initial+final) | Done | g2p_service.py |
| 5-parameter mouth (A/I/U/E/O) | Done | viseme_mapper.py |
| Multi-frame compound finals (1-3) | Done | diphthongs/nasals, ~30ms spacing |
| WordBoundary per-char timing | Done | replaces uniform 30ms |
| Global scale fallback | Done | audioDurationMs / last_time_ms |
| EMA smoothing (SMOOTH=0.2) | Done | LipSyncDriver.ts |
| Audio-viseme sync | Done | onPlayStarted callback timestamp |
| Mouth close on stop | Done | LipSyncDriver.stop() -> all zero |

### 1.4 Motion Animation

| Feature | Status | Key File |
|---------|--------|----------|
| 7 .motion3.json loaded | Done | mtn_01-04 + special_01-03 |
| setEffectIds (EyeBlink/LipSync) | Done | motion does not disrupt blink/lipsync |
| Loop support | Done | motion._isLoop = true |
| Idle motion (mtn_01 loop) | Done | priority 0 |
| Context trigger (happy+agree -> mtn_02) | Done | ChatPanel detectMotion() |
| Context trigger (magic keyword -> special_01) | Done | once per reply |
| Resume idle after voice | Done | scheduleEmotionReset 1.5s |
| New message -> stopAllMotions | Done | handleSend cleanup |

### 1.5 Render Pipeline

| Feature | Status |
|---------|--------|
| requestAnimationFrame driven | Done |
| Order: motion -> emotion -> lipSync -> scheduler -> model.update | Done |
| dt cap 100ms (prevent physics burst) | Done |
| Per-frame GL state (clear/depth/blend) | Done |
| MVP matrix (aspect ratio adaptive) | Done |

---

## 2. Architecture Decisions

### 2.1 5-param mouth vs single param

**Decision**: Use A/I/U/E/O five-parameter system instead of the PRD-planned single ParamMouthOpenY.

**Reason**: mao_pro model natively supports these 5 params. ParamMouthOpenY does not exist in this model. The 5-param system provides much richer mouth expression (spread, round, half-open distinctions).

### 2.2 Motion-based idle vs code-driven idle

**Decision**: Use .motion3.json files (mtn_01 loop) instead of IdleMotionDriver code-driven random movement.

**Reason**: Motion files are designer-crafted, far more natural than sine waves or random walks. IdleMotionDriver removed from render loop; file retained for future code-level fine-tuning.

### 2.3 Two-phase emotion transition

**Decision**: Non-neutral emotion transitions go through neutral first (200ms) before reaching target.

**Reason**: Prevents previous emotion expression preset (Add mode) residue. Example: happy->sad without reset causes happy eye-smile to stack on sad expression. Phase 1 drives all 22 neutral params for complete reset.

### 2.4 ref + useImperativeHandle pattern

**Decision**: Live2DCanvas exposes sync API via ref (setEmotion/playMotion/startLipSync) instead of pure props.

**Reason**: Bypasses React render cycle delay (~16ms + scheduling). Audio sync, emotion switching, and motion triggering all need immediate frame-level response.

---

## 3. Bug Fix History

| # | Bug | Root Cause | Fix | Lesson |
|---|-----|-----------|-----|--------|
| 1 | White rectangles | Premultiplied alpha mismatch (Context+Renderer+Texture) | All 3 layers set premultiplied | Compare against official Sample |
| 2 | Model ghosting | Missing Physics+Pose+CubismUpdateScheduler | Load .physics3.json+.pose3.json, register updaters | SDK param pipeline is layered |
| 3 | Emotion not showing | Wrong param names (used non-existent ParamMouthOpenY) | Read .exp3.json per-file for real param names | Read model data before writing code |
| 4 | Expression mapping all wrong | Guessed expression indices | Manually verified each .exp3.json visual effect | Never assume index semantics |
| 5 | Reset broken | reset() set params to 0, but model defaults != 0 | Use _model.loadParameters() to restore saved snapshot | Zero != default |
| 6 | Phase 2 target cleared | Same-frame race: Phase 2 trigger + cleanup check | Reorder: expression cleanup check before Phase 2 trigger | State mutation + check in same frame = race |
| 7 | Canvas resize destroys WebGL | Setting canvas.width/height to same value destroys context | Add equality guard before assignment | WebGL canvas dim assignment has side effects |
| 8 | Audio-viseme desync | viseme uses own performance.now(), audio async decodes | onPlayStarted callback with synced timestamp | ref + callback bypasses React cycle |

---

## 4. Remaining Issues

| # | Issue | Priority | Notes |
|---|-------|----------|-------|
| 1 | Viseme per-char accuracy unverified | Low | WordBoundary distribution has scale fallback but not per-char validated |
| 2 | Param names hardcoded for mao_pro | Low | EmotionDriver CONFIG uses model-specific names; switching model requires update |
| 3 | Motion file paths hardcoded | Low | motionNames array hardcoded in CubismManager |
| 4 | Physics/Pose/EyeBlink load failures silent | Low | try/catch only logs, does not block model, but user unaware |
| 5 | No auto model switching | Phase 4 | Only single model path supported |

---

## 5. File Manifest

### New files (Phase 3)

frontend/src/components/Live2DCanvas.tsx
frontend/src/hooks/useLive2D.ts
frontend/src/live2d/index.ts
frontend/src/live2d/CubismManager.ts
frontend/src/live2d/EmotionDriver.ts
frontend/src/live2d/LipSyncDriver.ts
frontend/src/live2d/IdleMotionDriver.ts (deprecated, kept for reference)
frontend/src/live2d/sdk/** (Cubism SDK for Web 5 TypeScript port)
backend/tts/g2p_service.py
backend/tts/viseme_mapper.py
public/live2d/mao_zh_Hans/** (Live2D model assets)

### Modified files (Phase 3)

frontend/src/App.tsx (Live2DCanvas split layout + live2dRef)
frontend/src/ChatPanel.tsx (motion detection + audio-viseme sync + emotion reset)
frontend/src/audio/AudioManager.ts (onPlayStarted callback)
backend/routes.py (viseme events + WordBoundary per-char timing)

---

## 6. Phase 4 Handoff Notes

1. EmotionDriver param names need update per-model (re-read .exp3.json)
2. Motion loading should read from model3.json FileReferences.Motions dynamically
3. Conversation memory: dict -> Chroma vector store, must keep compatible interface
4. Tool call results can trigger emotion + motion (e.g. search success -> excited + special_03)
5. LipSyncDriver could upgrade to audio RMS-based dynamic mouth (replacing G2P estimation)

---

*Last updated: 2026-07-25*
