/**
 * Main chat panel: message list + input bar + quick replies + voice input.
 * Phase 3: audio/viseme buffering for Live2D lip-sync.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useChat, VisemeFrame } from "../hooks/useChat";
import { ChatBubble } from "./ChatBubble";
import { VoiceButton } from "./VoiceButton";
import { AudioManager } from "../audio/AudioManager";
import type { ToolRequest } from "../chat/ChatClient";
import type { Live2DCanvasHandle } from "./Live2DCanvas";

const QUICK_REPLIES = ["你好", "今天天气怎么样", "你能做什么"];

interface PanelProps {
  onLive2DUpdate?: (data: any) => void;
  live2dRef?: React.RefObject<Live2DCanvasHandle | null>;
}

export function ChatPanel({ onLive2DUpdate, live2dRef }: PanelProps) {
  const audioRef = useRef<AudioManager | null>(null);
  const pendingRef = useRef<{ base64?: string; visemes?: VisemeFrame[]; durationMs?: number }>({});
  const updateRef = useRef(onLive2DUpdate);
  updateRef.current = onLive2DUpdate;

  // Motion context detection — analyses user's message, not AI's reply
  const userMessageRef = useRef('');
  const emotionRef = useRef('');
  const motionTriggeredRef = useRef(false);

  // User expresses agreement/approval/recognition TOWARD the AI
  const USER_AGREE_KEYWORDS = ['认可', '认同', '说得对', '没错', '有道理', '你真棒', '你好厉害', '喜欢你', '厉害', '好聪明', '不错', '挺好的', '很好', '真不错', '太棒了'];
  const MAGIC_KEYWORDS = ['魔法', '变魔法', '变个魔法', '施法', '施魔法', '施了魔法', '魔术', '变魔术', '变个魔术', '咒语', '咒', '法术', '变戏法', '魔杖', '变出'];

  var detectMotion = function() {
    if (motionTriggeredRef.current) return;
    var userMsg = userMessageRef.current;
    // Magic keywords in user's message -> special_01
    for (var i = 0; i < MAGIC_KEYWORDS.length; i++) {
      if (userMsg.indexOf(MAGIC_KEYWORDS[i]) !== -1) {
        motionTriggeredRef.current = true;
        console.log('[Motion] TRIGGER special_01 | keyword:', MAGIC_KEYWORDS[i], '| user:', userMsg.slice(-40));
        live2dRef?.current?.playMotion('special_01', 1);
        return;
      }
    }
    // User approval/recognition -> mtn_02
    for (var i = 0; i < USER_AGREE_KEYWORDS.length; i++) {
      if (userMsg.indexOf(USER_AGREE_KEYWORDS[i]) !== -1) {
        motionTriggeredRef.current = true;
        console.log('[Motion] TRIGGER mtn_02 | keyword:', USER_AGREE_KEYWORDS[i], '| user:', userMsg.slice(-40));
        live2dRef?.current?.playMotion('mtn_02', 1);
        return;
      }
    }
  };

  // Reset emotion after audio ends, restart idle motion
  const resetTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scheduleEmotionReset = useCallback(() => {
    if (resetTimeoutRef.current) clearTimeout(resetTimeoutRef.current);
    resetTimeoutRef.current = setTimeout(function() {
      live2dRef?.current?.setEmotion('neutral', 1.0);
      live2dRef?.current?.startIdleMotion();
      resetTimeoutRef.current = null;
    }, 1500);
  }, [live2dRef]);

  /**
   * Play TTS audio. When viseme data is available, lip-sync starts exactly when
   * audio playback begins (via onPlayStarted callback), eliminating the timing gap
   * between async audio decode and the LipSyncDriver's independent timer.
   */
  const playAudio = useCallback((
    b64: string,
    visemes?: VisemeFrame[],
    durationMs?: number,
  ) => {
    if (!audioRef.current) audioRef.current = new AudioManager();
    audioRef.current.stop();

    // Capture performance.now() at the exact moment AudioContext starts playback.
    // This bridges the Web Audio timeline and the render loop's rAF timer,
    // ensuring viseme frames are evaluated against real audio progress.
    const onPlayStarted = visemes && visemes.length > 0
      ? function(_ctxTime: number) {
          const startTime = performance.now();
          live2dRef?.current?.startLipSync(visemes, durationMs ?? 0, startTime);
        }
      : undefined;

    audioRef.current.playBase64(b64, scheduleEmotionReset, onPlayStarted).catch(function(e: Error) {
      console.error("Audio:", e);
    });
  }, [scheduleEmotionReset, live2dRef]);

  const flushPending = useCallback(() => {
    const p = pendingRef.current;
    if (p.base64 && p.visemes) {
      const b64 = p.base64, v = p.visemes, d = p.durationMs ?? 0;
      pendingRef.current = {};
      playAudio(b64, v, d);
    }
  }, [playAudio]);

  const handleAudio = useCallback((base64: string, _f: string, durationMs: number) => {
    pendingRef.current.base64 = base64;
    pendingRef.current.durationMs = durationMs;
    flushPending();
  }, [flushPending]);

  const handleEmotion = useCallback((emotion: string, intensity: number) => {
    emotionRef.current = emotion;  // capture for motion detection
    console.log('[Motion] emotion detected:', emotion, 'intensity:', intensity);
    onLive2DUpdate?.({ emotion, intensity });
  }, [onLive2DUpdate]);

  const handleToken = useCallback((_token: string) => {
    detectMotion();  // checks userMessageRef, fires once per reply
  }, []);

  const handleViseme = useCallback((visemes: VisemeFrame[]) => {
    pendingRef.current.visemes = visemes;
    flushPending();
  }, [flushPending]);

  const handleDone = useCallback(() => {
    const p = pendingRef.current;
    if (p.base64 && !p.visemes) {
      // Audio arrived without visemes — play it (reset handled by audio onended)
      playAudio(p.base64);
    }
    pendingRef.current = {};
  }, [playAudio]);

  const [input, setInput] = useState("");
  const [uploading, setUploading] = useState(false);
  const [pendingTool, setPendingTool] = useState<ToolRequest | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Human-in-the-loop: 工具调用确认（HITL_ENABLED=true 时后端会发 tool_request）
  const handleToolRequest = useCallback((request: ToolRequest) => {
    setPendingTool(request);
  }, []);

  const { messages, isLoading, error, sendMessage, stopGeneration, clearMessages, confirmToolCall } =
    useChat({ onAudio: handleAudio, onEmotion: handleEmotion, onToken: handleToken, onViseme: handleViseme, onDone: handleDone, onToolRequest: handleToolRequest });

  const handleToolConfirm = useCallback((approved: boolean) => {
    if (!pendingTool) return;
    const rid = pendingTool.requestId;
    setPendingTool(null);
    confirmToolCall(rid, approved).then((ok) => {
      if (!ok) console.warn("HITL confirm failed:", rid);
    });
  }, [pendingTool, confirmToolCall]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = useCallback(() => {
    if (!input.trim() || isLoading) return;
    pendingRef.current = {};
    audioRef.current?.stop();
    if (resetTimeoutRef.current) { clearTimeout(resetTimeoutRef.current); resetTimeoutRef.current = null; }
    // Store user message for motion detection, then reset motion state
    userMessageRef.current = input.trim();
    emotionRef.current = '';
    motionTriggeredRef.current = false;
    live2dRef?.current?.stopAllMotions();
    live2dRef?.current?.setEmotion('thoughtful', 0.5);
    sendMessage(input);
    setInput("");
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }
  }, [input, isLoading, sendMessage, live2dRef]);

  const handleVoiceRecognized = useCallback(
    (text: string) => {
      pendingRef.current = {};
      audioRef.current?.stop();
      if (resetTimeoutRef.current) { clearTimeout(resetTimeoutRef.current); resetTimeoutRef.current = null; }
      userMessageRef.current = text.trim();
      emotionRef.current = '';
      motionTriggeredRef.current = false;
      live2dRef?.current?.stopAllMotions();
      live2dRef?.current?.setEmotion('thoughtful', 0.5);
      sendMessage(text);
    },
    [sendMessage, live2dRef],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleQuickReply = useCallback(
    (text: string) => {
      audioRef.current?.stop();
      if (resetTimeoutRef.current) { clearTimeout(resetTimeoutRef.current); resetTimeoutRef.current = null; }
      userMessageRef.current = text.trim();
      emotionRef.current = '';
      motionTriggeredRef.current = false;
      live2dRef?.current?.stopAllMotions();
      live2dRef?.current?.setEmotion('thoughtful', 0.5);
      sendMessage(text);
    },
    [sendMessage, live2dRef],
  );

  // File upload
  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const resp = await fetch("/api/upload", { method: "POST", body: form });
      if (!resp.ok) throw new Error((await resp.json()).detail ?? "Upload failed");
      const data = await resp.json();
      // Auto-send message asking agent to read the uploaded file
      const msg = `请帮我查看这个文件：${data.path}`;
      pendingRef.current = {};
      audioRef.current?.stop();
      if (resetTimeoutRef.current) { clearTimeout(resetTimeoutRef.current); resetTimeoutRef.current = null; }
      userMessageRef.current = msg;
      emotionRef.current = '';
      motionTriggeredRef.current = false;
      live2dRef?.current?.stopAllMotions();
      live2dRef?.current?.setEmotion('thoughtful', 0.5);
      sendMessage(msg);
    } catch (err: any) {
      console.error("Upload failed:", err);
    } finally {
      setUploading(false);
      // Reset file input so same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }, [sendMessage, live2dRef]);

  // Auto-resize textarea
  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setInput(e.target.value);
      const el = e.target;
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 120) + "px";
    },
    [],
  );

  return (
    <div className="chat-panel">
      {/* Header */}
      <header className="chat-header">
        <span className="chat-logo">🌸 Ruoxue</span>
        <span className={`chat-status ${error ? "offline" : "online"}`}>
          {error ? "○ 已断开" : "● 已连接"}
        </span>
      </header>

      {/* Messages */}
      <main className="chat-messages" ref={listRef}>
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-card">
              <div className="empty-icon">👋</div>
              <h2>你好！我是 Ruoxue</h2>
              <p>你的 AI 助手，试试问我问题吧</p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <ChatBubble key={msg.id} message={msg} />
        ))}

        {error && (
          <div className="error-banner">
            <span>⚠️ {error}</span>
            <button onClick={clearMessages}>重试</button>
          </div>
        )}
      </main>

      {/* Quick replies */}
      {messages.length === 0 && (
        <div className="quick-replies">
          {QUICK_REPLIES.map((qr) => (
            <button
              key={qr}
              className="quick-reply-btn"
              onClick={() => handleQuickReply(qr)}
              disabled={isLoading}
            >
              {qr}
            </button>
          ))}
        </div>
      )}

      {/* Input bar */}
      <footer className="input-bar">
        {pendingTool && (
          <div className="hitl-bar">
            <span>
              🤖 若雪想调用工具：
              {pendingTool.toolCalls.map((t) => t.name).join(", ")}，是否允许？
            </span>
            <button className="hitl-btn allow" onClick={() => handleToolConfirm(true)}>
              允许
            </button>
            <button className="hitl-btn deny" onClick={() => handleToolConfirm(false)}>
              拒绝
            </button>
          </div>
        )}
        <VoiceButton
          onRecognized={handleVoiceRecognized}
          disabled={isLoading}
        />
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.md,.pdf,.py,.ts,.tsx,.json,.yaml,.yml,.html,.css"
          onChange={handleFileSelect}
          style={{ display: "none" }}
        />
        <button
          className={`upload-btn ${uploading ? "uploading" : ""}`}
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading || uploading}
          title="上传文件"
        >
          {uploading ? "⏳" : "📎"}
        </button>
        <textarea
          ref={inputRef}
          className="chat-input"
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder="输入你想问的..."
          rows={1}
          disabled={isLoading}
        />
        {isLoading ? (
          <button className="send-btn stop" onClick={stopGeneration}>
            停止
          </button>
        ) : (
          <button
            className="send-btn"
            onClick={handleSend}
            disabled={!input.trim()}
          >
            发送
          </button>
        )}
      </footer>
    </div>
  );
}
