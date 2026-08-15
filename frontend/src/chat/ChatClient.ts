/**
 * SSE stream client for Ruoxue chat API.
 *
 * Handles fetch + ReadableStream parsing of text/event-stream,
 * dispatching emotion / token / done / error callbacks.
 */

export interface SSEEvent {
  event: string;
  data: unknown;
}

export interface ToolRequest {
  requestId: string;
  toolCalls: Array<{ name: string; args?: Record<string, unknown> }>;
  timeoutS?: number;
}

export interface VisemeFrame {
  time_ms: number;
  A: number;
  I: number;
  U: number;
  E: number;
  O: number;
}

export interface ChatClientCallbacks {
  onEmotion?: (emotion: string, intensity: number) => void;
  onToken?: (text: string) => void;
  /** 分片音频: seq 为句子序号, 前端按序排队播放 */
  onAudio?: (base64: string, format: string, durationMs: number, seq: number) => void;
  /** 分片口型帧: 与同 seq 的 audio 配对, 播放开始时驱动嘴型 */
  onViseme?: (frames: VisemeFrame[], seq: number) => void;
  onToolRequest?: (request: ToolRequest) => void;
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
    let currentEvent = ""; // Must persist across chunks: FastAPI yields each SSE line separately

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE lines
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

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
  data: unknown,
  cb: ChatClientCallbacks,
): void {
  const d = data as Record<string, unknown>;
  switch (event) {
    case "emotion":
      cb.onEmotion?.(d.emotion as string, d.intensity as number);
      break;
    case "token":
      cb.onToken?.(d.text as string);
      break;
    case "audio":
      cb.onAudio?.(
        d.base64 as string,
        (d.format as string) || "mp3",
        (d.duration_ms as number) || 0,
        (d.seq as number) ?? 0,
      );
      break;
    case "viseme":
      cb.onViseme?.((d.frames as VisemeFrame[]) || [], (d.seq as number) ?? 0);
      break;
    case "tool_request":
      cb.onToolRequest?.({
        requestId: d.request_id as string,
        toolCalls: (d.tool_calls as Array<{ name: string; args?: Record<string, unknown> }>) || [],
        timeoutS: d.timeout_s as number | undefined,
      });
      break;
    case "done":
      cb.onDone?.();
      break;
    case "error":
      cb.onError?.(d.message as string);
      break;
  }
}
