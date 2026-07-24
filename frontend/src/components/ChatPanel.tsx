/**
 * Main chat panel: message list + input bar + quick replies + voice input.
 * Phase 3: audio/viseme buffering for Live2D lip-sync.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useChat, VisemeFrame } from "../hooks/useChat";
import { ChatBubble } from "./ChatBubble";
import { VoiceButton } from "./VoiceButton";
import { AudioManager } from "../audio/AudioManager";
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

  // Motion context detection
  const replyBufferRef = useRef('');
  const emotionRef = useRef('');
  const motionTriggeredRef = useRef(false);

  const AGREE_KEYWORDS = ['对', '没错', '是的', '确实', '说得对', '同意', '赞成', '认同', '当然', '正是', '有道理', '我也觉得', '我也是', '好啊', '好的呀', '没问题', '可以的', '行', '可以'];
  const MAGIC_KEYWORDS = ['魔法', '变个魔法', '变魔法', '施法', '魔术', '变个魔术', '变魔术', '咒语', '法术', '变戏法'];

  var detectMotion = function(text: string) {
    if (motionTriggeredRef.current) return;
    var emo = emotionRef.current;
    if (emo !== 'happy') return;
    for (var i = 0; i < MAGIC_KEYWORDS.length; i++) {
      if (text.indexOf(MAGIC_KEYWORDS[i]) !== -1) {
        motionTriggeredRef.current = true;
        live2dRef?.current?.playMotion('special_01', 1);
        return;
      }
    }
    for (var i = 0; i < AGREE_KEYWORDS.length; i++) {
      if (text.indexOf(AGREE_KEYWORDS[i]) !== -1) {
        motionTriggeredRef.current = true;
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
      console.log('[ChatPanel] resetting: neutral + idle');
      live2dRef?.current?.setEmotion('neutral', 1.0);
      live2dRef?.current?.startIdleMotion();
      resetTimeoutRef.current = null;
    }, 1500);
  }, [live2dRef]);

  const playAudio = useCallback((b64: string) => {
    if (!audioRef.current) audioRef.current = new AudioManager();
    audioRef.current.stop();
    audioRef.current.playBase64(b64, scheduleEmotionReset).catch(function(e: Error) {
      console.error("Audio:", e);
    });
  }, [scheduleEmotionReset]);

  const flushPending = useCallback(() => {
    const p = pendingRef.current;
    if (p.base64 && p.visemes) {
      const b64 = p.base64, v = p.visemes, d = p.durationMs ?? 0;
      pendingRef.current = {};
      playAudio(b64);
      updateRef.current?.({ visemes: v, audioDurationMs: d });
    }
  }, [playAudio]);

  const handleAudio = useCallback((base64: string, _f: string, durationMs: number) => {
    pendingRef.current.base64 = base64;
    pendingRef.current.durationMs = durationMs;
    flushPending();
  }, [flushPending]);

  const handleEmotion = useCallback((emotion: string, intensity: number) => {
    emotionRef.current = emotion;  // capture for motion detection
    onLive2DUpdate?.({ emotion, intensity });
  }, [onLive2DUpdate]);

  const handleToken = useCallback((token: string) => {
    replyBufferRef.current += token;
    detectMotion(replyBufferRef.current);
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
    // If audio was already flushed (with visemes), reset is already scheduled by audio onended.
    // If no audio at all, skip reset — next message will trigger thinking expression.
    pendingRef.current = {};
  }, [playAudio]);

  const { messages, isLoading, error, sendMessage, stopGeneration, clearMessages } =
    useChat({ onAudio: handleAudio, onEmotion: handleEmotion, onToken: handleToken, onViseme: handleViseme, onDone: handleDone });
  const [input, setInput] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

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
    // Reset motion state for new reply
    replyBufferRef.current = '';
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
      replyBufferRef.current = '';
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
      replyBufferRef.current = '';
      emotionRef.current = '';
      motionTriggeredRef.current = false;
      live2dRef?.current?.stopAllMotions();
      live2dRef?.current?.setEmotion('thoughtful', 0.5);
      sendMessage(text);
    },
    [sendMessage, live2dRef],
  );

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
        <VoiceButton
          onRecognized={handleVoiceRecognized}
          disabled={isLoading}
        />
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
