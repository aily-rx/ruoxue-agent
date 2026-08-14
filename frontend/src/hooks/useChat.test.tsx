/**
 * useChat hook 状态流转测试 — mock fetch 的 SSE 流, 验证消息状态机。
 *
 * 覆盖: 发送→用户消息+占位, token 累积, emotion 回调, done 收尾, 错误路径。
 */
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useChat } from "./useChat";

function sseResponse(body: string): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(body));
      controller.close();
    },
  });
  return new Response(stream, { status: 200 });
}

const STREAM_BODY =
  'event: emotion\ndata: {"emotion":"happy","intensity":0.8}\n\n' +
  'event: token\ndata: {"text":"你好"}\n\n' +
  'event: token\ndata: {"text":"世界"}\n\n' +
  "event: done\ndata: {}\n\n";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubChatFetch(body: string = STREAM_BODY): ReturnType<typeof vi.fn> {
  const mock = vi.fn().mockResolvedValue(sseResponse(body));
  vi.stubGlobal("fetch", mock);
  return mock;
}

describe("useChat 状态流转", () => {
  it("发送消息后追加用户消息与 assistant 占位", async () => {
    stubChatFetch();
    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage("你好");
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]).toMatchObject({ role: "user", content: "你好" });
    expect(result.current.messages[1]).toMatchObject({ role: "assistant", isStreaming: false });
  });

  it("token 流式累积到 assistant 消息", async () => {
    stubChatFetch();
    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage("你好");
    });

    expect(result.current.messages[1].content).toBe("你好世界");
    expect(result.current.isLoading).toBe(false);
  });

  it("emotion 事件更新 assistant 消息并触发回调", async () => {
    stubChatFetch();
    const onEmotion = vi.fn();
    const { result } = renderHook(() => useChat({ onEmotion }));

    await act(async () => {
      await result.current.sendMessage("你好");
    });

    expect(result.current.messages[1].emotion).toBe("happy");
    expect(result.current.messages[1].intensity).toBe(0.8);
    expect(onEmotion).toHaveBeenCalledWith("happy", 0.8);
  });

  it("done 事件结束流式状态并触发 onDone", async () => {
    stubChatFetch();
    const onDone = vi.fn();
    const { result } = renderHook(() => useChat({ onDone }));

    await act(async () => {
      await result.current.sendMessage("你好");
    });

    expect(result.current.isLoading).toBe(false);
    expect(onDone).toHaveBeenCalled();
  });

  it("error 事件写入错误信息并结束流式", async () => {
    const body =
      'event: error\ndata: {"message":"LLM 服务不可用","code":500}\n\n';
    stubChatFetch(body);
    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage("你好");
    });

    expect(result.current.error).toBe("LLM 服务不可用");
    expect(result.current.messages[1].content).toContain("[错误]");
    expect(result.current.isLoading).toBe(false);
  });

  it("空文本不发送请求", async () => {
    const fetchMock = stubChatFetch();
    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage("   ");
    });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current.messages).toHaveLength(0);
  });

  it("clearMessages 清空消息与错误", async () => {
    stubChatFetch();
    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage("你好");
    });
    await act(async () => {
      result.current.clearMessages();
    });

    expect(result.current.messages).toHaveLength(0);
    expect(result.current.error).toBeNull();
  });
});
