"""POST /api/chat 分片 TTS 协议集成测试 — mock agent + TTS, 校验 SSE 事件序列。

验证: token 逐句切分 → 每句一条 audio + 一条 viseme（带 seq）→ done 收尾。
不触碰真实 LLM / Edge TTS / Chroma。
"""

from __future__ import annotations

import json

import pytest
from backend.agent.emotional_agent import SSEEvent
from backend.main import app
from httpx import ASGITransport, AsyncClient


class FakeMemory:
    def __init__(self) -> None:
        self._history: dict[str, list[dict]] = {}

    def get_history(self, session_id: str) -> list[dict]:
        return self._history.get(session_id, [])

    def add_user_message(self, session_id: str, text: str) -> None:
        self._history.setdefault(session_id, []).append({"role": "user", "content": text})

    def add_assistant_message(self, session_id: str, text: str) -> None:
        self._history.setdefault(session_id, []).append({"role": "assistant", "content": text})


class FakeChroma:
    def store_turn(self, session_id: str, user_text: str, assistant_text: str) -> None:
        pass


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _read_sse(response) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    event_name: str | None = None
    async for line in response.aiter_lines():
        if not line:
            continue
        if line.startswith("event: "):
            event_name = line[7:].strip()
        elif line.startswith("data: "):
            events.append((event_name or "", json.loads(line[6:])))
            event_name = None
    return events


async def _fake_agent(user_text, history=None, request_id=None, use_cache=False):
    """模拟 agent: 一个情绪 + 两个完整句（逐 token）。"""
    yield SSEEvent(event="emotion", data={"emotion": "happy", "intensity": 0.6})
    for tok in ("你好", "。", "今天", "天气", "不错", "！"):
        yield SSEEvent(event="token", data={"text": tok})
    yield SSEEvent(event="done", data={})


async def _fake_synth(text: str) -> tuple[bytes, list[dict]]:
    return b"\xff\xfb" + b"\x00" * 100, [{"offset": 0, "duration": 20000000, "text": text}]


async def test_chunked_tts_protocol(client, monkeypatch) -> None:
    monkeypatch.setattr("backend.routes.run_agent_stream", _fake_agent)
    monkeypatch.setattr("backend.routes.synthesize_with_word_boundary", _fake_synth)
    monkeypatch.setattr("backend.routes.memory", FakeMemory())
    monkeypatch.setattr("backend.routes.chroma_memory", FakeChroma())

    async with client.stream(
        "POST", "/api/chat", json={"text": "你好", "session_id": "itest-01"}, timeout=30
    ) as response:
        assert response.status_code == 200
        events = await _read_sse(response)

    names = [name for name, _ in events]
    assert names[0] == "emotion"
    assert "done" in names

    tokens = [d["text"] for name, d in events if name == "token"]
    assert "".join(tokens) == "你好。今天天气不错！"

    audios = [d for name, d in events if name == "audio"]
    assert len(audios) == 2  # 两个完整句 → 两条 audio
    assert [a["seq"] for a in audios] == [0, 1]

    visemes = [d for name, d in events if name == "viseme"]
    assert len(visemes) == 2
    assert [v["seq"] for v in visemes] == [0, 1]
    assert all("frames" in v for v in visemes)

    # done 必须在最后一个 audio/viseme 之前或之后都不影响前端（前端按队列播放）,
    # 但 done 有且仅有一次
    assert names.count("done") == 1


async def test_chat_error_skips_done_and_tts(client, monkeypatch) -> None:
    async def fake_agent_error(user_text, history=None, request_id=None, use_cache=False):
        # 与真实 run_agent_stream 一致: async generator, 首轮迭代时抛错
        raise RuntimeError("LLM down")
        yield  # pragma: no cover — 仅为让函数成为 async generator

    monkeypatch.setattr("backend.routes.run_agent_stream", fake_agent_error)
    monkeypatch.setattr("backend.routes.synthesize_with_word_boundary", _fake_synth)
    monkeypatch.setattr("backend.routes.memory", FakeMemory())
    monkeypatch.setattr("backend.routes.chroma_memory", FakeChroma())

    async with client.stream(
        "POST", "/api/chat", json={"text": "你好", "session_id": "itest-02"}, timeout=30
    ) as response:
        events = await _read_sse(response)

    names = [name for name, _ in events]
    assert "error" in names
    assert "done" not in names  # 出错不发 done, 与旧行为一致
    assert "audio" not in names  # 出错不合成 TTS
