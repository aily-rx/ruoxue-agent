# Phase 1 Complete Summary - Text Chat

> Version: v1.0 | Date: 2026-07-25 | Status: Done

---

## 1. Deliverables

### 1.1 Backend - LLM Agent

| Feature | Status | Key File |
|---------|--------|----------|
| LangChain + DeepSeek integration | Done | emotional_agent.py |
| SSE streaming reply (token by token) | Done | ChatOpenAI(streaming=True) |
| [EMOTION: xxx|0.0] tag injection via system prompt | Done | EMOTION_SYSTEM_PROMPT |
| Regex tag extraction from stream (EMOTION_TAG_RE) | Done | Accumulate text, match at prefix |
| 8 emotion labels (happy/sad/angry/surprised/neutral/thoughtful/worried/excited) | Done | Emotion enum |
| Intensity 0.0-1.0 | Done | float in emotion tag |
| Default fallback (neutral/0.3) when LLM outputs no tag | Done | Final check in generate_reply |
| Conversation memory with sliding window | Done | ConversationMemory, MAX_HISTORY_TURNS=20 |
| Per-session history isolation | Done | session_id keyed dict |
| LangChain MessagesPlaceholder compatibility | Done | history passed as [{"role":...,"content":...}] |

### 1.2 Backend - API

| Feature | Status | Key File |
|---------|--------|----------|
| FastAPI application | Done | main.py |
| POST /api/chat (SSE stream) | Done | StreamingResponse, text/event-stream |
| GET /api/health | Done | HealthResponse with status/version/llm_available |
| CORS middleware (allow localhost:5173) | Done | CORSMiddleware |
| Environment config (.env) | Done | config.py + python-dotenv |
| Pydantic request validation (text 1-2000 chars) | Done | ChatRequest model |
| Auto session_id generation (uuid hex 12) | Done | uuid.uuid4().hex[:12] |

### 1.3 Frontend - UI

| Feature | Status | Key File |
|---------|--------|----------|
| React 18 + TypeScript (strict) + Vite 6 | Done | package.json, tsconfig.json, vite.config.ts |
| Vite proxy (/api -> localhost:8000) | Done | vite.config.ts proxy |
| CSS design token system (9 variables) | Done | style.css :root |
| ChatPanel container | Done | ChatPanel.tsx |
| ChatBubble (user right purple, AI left gray) | Done | ChatBubble.tsx |
| Emotion emoji avatar on AI messages | Done | 8 emotion -> emoji mapping |
| Quick reply buttons (3 presets) | Done | Shown on empty state only |
| Auto-resize textarea (max 120px) | Done | onInput -> scrollHeight |
| Send/Stop button toggle | Done | isLoading state |
| Enter to send, Shift+Enter for newline | Done | onKeyDown handler |
| Streaming cursor blink animation | Done | cursor-blink CSS animation |
| Empty state placeholder | Done | Welcome card |
| Error banner with retry | Done | error-banner |
| Auto-scroll to bottom on new messages | Done | useEffect on messages |
| Responsive layout (mobile <768px) | Done | @media queries |
| Message fade-in animation | Done | fadeIn 0.3s ease |

### 1.4 Frontend - SSE Client

| Feature | Status | Key File |
|---------|--------|----------|
| fetch + ReadableStream SSE parser | Done | ChatClient.ts |
| Event dispatch (emotion/token/done/error) | Done | dispatch() switch |
| AbortController support (stop generation) | Done | AbortSignal pass-through |
| Cross-chunk event type persistence | Done | currentEvent hoisted outside while(true) |
| Session persistence (useRef, per-page) | Done | sessionId useRef in useChat |

### 1.5 State Management

| Feature | Status | Key File |
|---------|--------|----------|
| useChat hook (messages/send/abort/clear) | Done | useChat.ts |
| Message model (id/role/content/emotion/intensity/isStreaming/timestamp) | Done | Message interface |
| Optimistic user message + placeholder AI message | Done | sendMessage() |
| Stream token accumulation into AI message | Done | onToken callback -> setMessages |
| Emotion update on AI message | Done | onEmotion callback |
| Abort/stop mid-generation | Done | stopGeneration() |
| Clear conversation + reset session | Done | clearMessages() -> genId() |
| Callback refs pattern (avoid stale closures) | Done | onAudioRef/onEmotionRef/etc |

---

## 2. Architecture Decisions

### 2.1 SSE over WebSocket

**Decision**: Use SSE (Server-Sent Events) instead of WebSocket for chat streaming.

**Reason**: Phase 1 is unidirectional text generation. SSE is simpler (no upgrade handshake, native EventSource pattern, auto-reconnect). WebSocket planned for Phase 2 voice streaming.

### 2.2 Emotion tag via prompt injection

**Decision**: LLM outputs [EMOTION: happy|0.5] as a text prefix rather than a separate API call.

**Reason**: Single LLM call is faster and cheaper. The tag format is simple enough for regex extraction from streaming text. Trade-off: if LLM fails to output the tag, we have a neutral fallback.

### 2.3 In-memory dict memory over Chroma

**Decision**: Simple dict-based ConversationMemory for Phase 1, defer Chroma to Phase 4.

**Reason**: Phase 1 scope is proof-of-concept. Dict with sliding window is zero-dependency, fast, and sufficient for 20-turn conversations. Chroma adds complexity (embedding model, persistence, search) that is not needed yet.

### 2.4 Design tokens in CSS :root

**Decision**: All colors, spacing, radii, shadows defined as CSS custom properties.

**Reason**: Enables theme switching, consistent spacing, and prevents hardcoded values scattered across components. Single source of truth for visual design.

### 2.5 useRef for sessionId

**Decision**: sessionId stored in useRef, not useState.

**Reason**: sessionId should never trigger re-renders and must survive across the page lifetime. useState would cause unnecessary re-renders and risk accidental resets.

---

## 3. Bug Fix History

| # | Bug | Root Cause | Fix | Lesson |
|---|-----|-----------|-----|--------|
| 1 | SSE tokens silently dropped, incomplete replies | FastAPI splits SSE event: and data: lines across different TCP chunks; ChatClient declared currentEvent inside while(true) loop, reset each read() | Hoist currentEvent outside while(true) | SSE parser state variables must persist across chunk boundaries |

---

## 4. Known Limitations

| # | Issue | Notes |
|---|-------|-------|
| 1 | No streaming abort on backend | Frontend AbortController cancels fetch but LLM generation continues server-side |
| 2 | Memory not persisted | Server restart loses all conversation history |
| 3 | No token limit enforcement | 8192 max_tokens but no input truncation if history grows too large |
| 4 | Single LLM provider | Hardcoded to DeepSeek, switching requires config + prompt changes |
| 5 | No typing indicator latency | Token speed depends entirely on LLM API response time |

---

## 5. File Manifest

### New files (Phase 1)

backend/
  main.py
  routes.py
  config.py
  agent/__init__.py
  agent/emotional_agent.py
  agent/memory.py

frontend/src/
  main.tsx
  App.tsx
  style.css
  vite-env.d.ts
  components/ChatPanel.tsx
  components/ChatBubble.tsx
  chat/ChatClient.ts
  hooks/useChat.ts

### Configuration files

backend/.env.example
backend/requirements.txt
frontend/package.json
frontend/tsconfig.json
frontend/vite.config.ts

---

## 6. Phase 2 Handoff Notes

1. emotion callback in useChat already wired -> ready for Live2D emotion driver
2. ChatRequest model accepts session_id -> ready for multi-turn
3. SSE protocol extensible -> add audio/viseme events without breaking existing parser
4. ChatClient dispatch() switch -> add new event types without refactor
5. design token system -> all new components must use CSS variables

---

*Last updated: 2026-07-25*
