/**
 * Core chat state management hook.
 *
 * Manages messages, streaming, send/abort, and SSE lifecycle.
 */

import { useCallback, useRef, useState } from "react";
import { streamChat } from "../chat/ChatClient";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  emotion?: string;
  intensity?: number;
  isStreaming?: boolean;
  timestamp: number;
}

function genId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const sessionId = useRef<string>(genId());

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isLoading) return;

      setError(null);

      // Add user message
      const userMsg: Message = {
        id: genId(),
        role: "user",
        content: trimmed,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);

      // Add placeholder for assistant reply
      const assistantId = genId();
      const assistantMsg: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        isStreaming: true,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsLoading(true);

      // Start SSE stream
      const abort = new AbortController();
      abortRef.current = abort;

      try {
        await streamChat(
          trimmed,
          sessionId.current,
          {
            onEmotion(emotion, intensity) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, emotion, intensity } : m,
                ),
              );
            },
            onToken(token) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + token }
                    : m,
                ),
              );
            },
            onDone() {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, isStreaming: false } : m,
                ),
              );
              setIsLoading(false);
            },
            onError(msg) {
              setError(msg);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: `[错误] ${msg}`, isStreaming: false }
                    : m,
                ),
              );
              setIsLoading(false);
            },
          },
          abort.signal,
        );
      } catch (err: unknown) {
        if ((err as Error).name === "AbortError") return;
        const msg = err instanceof Error ? err.message : "Unknown error";
        setError(msg);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: `[连接失败] ${msg}`, isStreaming: false }
              : m,
          ),
        );
        setIsLoading(false);
      }
    },
    [isLoading],
  );

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsLoading(false);
    setMessages((prev) =>
      prev.map((m) =>
        m.isStreaming ? { ...m, isStreaming: false } : m,
      ),
    );
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
    sessionId.current = genId();
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    stopGeneration,
    clearMessages,
  };
}
