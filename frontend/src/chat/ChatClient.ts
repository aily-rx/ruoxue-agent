/**
 * SSE stream client for Ruoxue chat API.
 *
 * Handles fetch + ReadableStream parsing of text/event-stream,
 * dispatching emotion / token / done / error callbacks.
 */

export interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
}

export interface ChatClientCallbacks {
  onEmotion?: (emotion: string, intensity: number) => void;
  onToken?: (text: string) => void;
  onDone?: () => void;
  onError?: (message: string) => void;
}

const API_BASE = "/api";

export function streamChat(
  text: string,
  sessionId: string,
  callbacks: ChatClientCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  return fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, session_id: sessionId }),
    signal,
  }).then(async (response) => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error("No readable stream");

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE lines
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      let currentEvent = "";
      for (const line of lines) {
        if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          const raw = line.slice(6);
          try {
            const data = JSON.parse(raw);
            dispatch(currentEvent, data, callbacks);
          } catch {
            // Skip unparseable lines
          }
          currentEvent = "";
        }
      }
    }
  });
}

function dispatch(
  event: string,
  data: Record<string, unknown>,
  cb: ChatClientCallbacks,
): void {
  switch (event) {
    case "emotion":
      cb.onEmotion?.(data.emotion as string, data.intensity as number);
      break;
    case "token":
      cb.onToken?.(data.text as string);
      break;
    case "done":
      cb.onDone?.();
      break;
    case "error":
      cb.onError?.(data.message as string);
      break;
  }
}
