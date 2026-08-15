/**
 * Core chat state management hook.
 *
 * Manages messages, streaming, send/abort, and SSE lifecycle.
 */

import { useCallback, useRef, useState } from "react";
import { streamChat, ToolRequest } from "../chat/ChatClient";

export interface VisemeFrame {
  time_ms: number;
  A: number;
  I: number;
  U: number;
  E: number;
  O: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  emotion?: string;
  intensity?: number;
  isStreaming?: boolean;
  timestamp: number;
  visemes?: VisemeFrame[];
}

function genId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

export interface UseChatOptions {
  onAudio?: (base64: string, format: string, durationMs: number, seq: number) => void;
  onEmotion?: (emotion: string, intensity: number) => void;
  onToken?: (text: string) => void;
  onViseme?: (frames: VisemeFrame[], seq: number) => void;
  onToolRequest?: (request: ToolRequest) => void;
  onDone?: () => void;
}

export function useChat(options: UseChatOptions = {}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const sessionId = useRef<string>(genId());
  const onAudioRef = useRef(options.onAudio);
  onAudioRef.current = options.onAudio;
  const onEmotionRef = useRef(options.onEmotion);
  onEmotionRef.current = options.onEmotion;
  const onTokenRef = useRef(options.onToken);
  onTokenRef.current = options.onToken;
  const onVisemeRef = useRef(options.onViseme);
  onVisemeRef.current = options.onViseme;
  const onToolRequestRef = useRef(options.onToolRequest);
  onToolRequestRef.current = options.onToolRequest;
  const onDoneRef = useRef(options.onDone);
  onDoneRef.current = options.onDone;

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
              onEmotionRef.current?.(emotion, intensity);
            },
            onToken(token) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + token }
                    : m,
                ),
              );
              onTokenRef.current?.(token);
            },
            onAudio(base64, format, durationMs, seq) {
              onAudioRef.current?.(base64, format, durationMs, seq);
            },
            onViseme(frames, seq) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, visemes: [...(m.visemes ?? []), ...frames] }
                    : m,
                ),
              );
              onVisemeRef.current?.(frames, seq);
            },
            onToolRequest(request) {
              onToolRequestRef.current?.(request);
            },
            onDone() {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, isStreaming: false } : m,
                ),
              );
              setIsLoading(false);
              onDoneRef.current?.();
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

  // Human-in-the-loop: 回复工具调用确认（对应 SSE tool_request 事件）
  const confirmToolCall = useCallback(
    async (requestId: string, approved: boolean): Promise<boolean> => {
      try {
        const resp = await fetch("/api/hitl-confirm", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ request_id: requestId, approved }),
        });
        return resp.ok;
      } catch {
        return false;
      }
    },
    [],
  );

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    stopGeneration,
    clearMessages,
    confirmToolCall,
  };
}
