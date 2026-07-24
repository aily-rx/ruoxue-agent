/**
 * Single chat message bubble.
 */

import type { Message } from "../hooks/useChat";

interface Props {
  message: Message;
}

const EMOTION_LABELS: Record<string, string> = {
  happy: "😊",
  sad: "😢",
  angry: "😠",
  surprised: "😲",
  neutral: "",
  thoughtful: "🤔",
  worried: "😟",
  excited: "🎉",
};

export function ChatBubble({ message }: Props) {
  const isUser = message.role === "user";
  const emotionIcon = message.emotion ? EMOTION_LABELS[message.emotion] : null;

  return (
    <div className={`message ${isUser ? "user" : "ai"}`}>
      {!isUser && (
        <div className="message-avatar">
          {emotionIcon || "🌸"}
        </div>
      )}
      <div className={`bubble ${isUser ? "bubble-user" : "bubble-ai"}`}>
        <div className="bubble-text">
          {message.content}
          {message.isStreaming && <span className="cursor-blink">▉</span>}
        </div>
      </div>
      <span className="message-time">
        {new Date(message.timestamp).toLocaleTimeString("zh-CN", {
          hour: "2-digit",
          minute: "2-digit",
        })}
      </span>
    </div>
  );
}
