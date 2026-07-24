/**
 * Main chat panel: message list + input bar + quick replies.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useChat } from "../hooks/useChat";
import { ChatBubble } from "./ChatBubble";

const QUICK_REPLIES = ["你好", "今天天气怎么样", "你能做什么"];

export function ChatPanel() {
  const { messages, isLoading, error, sendMessage, stopGeneration, clearMessages } =
    useChat();
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
    sendMessage(input);
    setInput("");
    // Reset textarea height
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }
  }, [input, isLoading, sendMessage]);

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
      sendMessage(text);
    },
    [sendMessage],
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
