/**
 * ChatClient SSE 解析测试 — 覆盖跨 chunk 事件类型保留的回归场景。
 *
 * 关键回归: FastAPI 可能把 `event:` 行和 `data:` 行分到不同的网络 chunk,
 * currentEvent 变量必须跨 chunk 保留（曾经因此 token 被静默丢弃）。
 */
import { describe, expect, it, vi, afterEach } from "vitest";
import { streamChat } from "./ChatClient";

function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

function stubFetch(body: string | string[]): ReturnType<typeof vi.fn> {
  const chunks = Array.isArray(body) ? body : [body];
  const mock = vi.fn().mockResolvedValue(sseResponse(chunks));
  vi.stubGlobal("fetch", mock);
  return mock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("streamChat SSE 解析", () => {
  it("解析单个 chunk 内的完整事件序列", async () => {
    const body =
      'event: emotion\ndata: {"emotion":"happy","intensity":0.8}\n\n' +
      'event: token\ndata: {"text":"你好"}\n\n' +
      "event: done\ndata: {}\n\n";
    stubFetch(body);

    const events: string[] = [];
    await streamChat("hi", "s1", {
      onEmotion: (e, i) => events.push(`emotion:${e}:${i}`),
      onToken: (t) => events.push(`token:${t}`),
      onDone: () => events.push("done"),
    });

    expect(events).toEqual(["emotion:happy:0.8", "token:你好", "done"]);
  });

  it("回归: event 行与 data 行跨 chunk 拆分时事件类型不丢失", async () => {
    // FastAPI 逐行 yield, 事件边界可能落在任意 chunk 边界
    const chunk1 = 'event: token\ndata: {"text":"你好"}\n\nevent: emoti';
    const chunk2 = 'on\ndata: {"emotion":"sad","intensity":0.5}\n\nevent: done\nda';
    const chunk3 = "ta: {}\n\n";
    stubFetch([chunk1, chunk2, chunk3]);

    const events: string[] = [];
    await streamChat("hi", "s1", {
      onEmotion: (e, i) => events.push(`emotion:${e}:${i}`),
      onToken: (t) => events.push(`token:${t}`),
      onDone: () => events.push("done"),
    });

    expect(events).toEqual(["token:你好", "emotion:sad:0.5", "done"]);
  });

  it("多事件拆到多个 chunk 时依次解析", async () => {
    const chunk1 = 'event: token\ndata: {"text":"第"}\n\n';
    const chunk2 = 'event: token\ndata: {"text":"二段"}\n\n';
    const chunk3 = "event: done\ndata: {}\n\n";
    stubFetch([chunk1, chunk2, chunk3]);

    const tokens: string[] = [];
    await streamChat("hi", "s1", { onToken: (t) => tokens.push(t) });

    expect(tokens).toEqual(["第", "二段"]);
  });

  it("data 行跨 chunk 拆分时 JSON 能完整解析", async () => {
    const chunk1 = 'event: token\ndata: {"tex';
    const chunk2 = 't":"你好"}\n\n';
    stubFetch([chunk1, chunk2]);

    const tokens: string[] = [];
    await streamChat("hi", "s1", { onToken: (t) => tokens.push(t) });

    expect(tokens).toEqual(["你好"]);
  });

  it("不可解析的 data 行被忽略且不中断后续事件", async () => {
    const body =
      'event: token\ndata: 这不是JSON\n\n' +
      'event: token\ndata: {"text":"正常"}\n\n' +
      "event: done\ndata: {}\n\n";
    stubFetch(body);

    const tokens: string[] = [];
    await streamChat("hi", "s1", { onToken: (t) => tokens.push(t) });

    expect(tokens).toEqual(["正常"]);
  });

  it("HTTP 非 200 时抛出错误", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("bad", { status: 500 })),
    );
    await expect(streamChat("hi", "s1", {})).rejects.toThrow("HTTP 500");
  });

  it("响应无 body 时抛出错误", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 200 })));
    await expect(streamChat("hi", "s1", {})).rejects.toThrow("No readable stream");
  });
});
