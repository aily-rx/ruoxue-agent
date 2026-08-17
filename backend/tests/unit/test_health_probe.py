"""健康检查 LLM 探测单元测试 — ping_llm 快速路径 + routes 层 60s 缓存。"""

from __future__ import annotations

import backend.agent.agent_graph as ag
import backend.routes as routes


class BoomLLM:
    """模拟 LLM 调用抛错（网络/鉴权失败）。"""

    async def ainvoke(self, *a, **kw):
        raise RuntimeError("network down")


async def test_ping_llm_false_without_api_key(monkeypatch) -> None:
    """未配置 API key → 不发网络请求, 直接 False。"""
    monkeypatch.setattr(ag, "DEEPSEEK_API_KEY", "your-api-key-here")
    assert await ag.ping_llm(timeout=1.0) is False


async def test_ping_llm_false_on_llm_error(monkeypatch) -> None:
    """LLM 调用抛错 → False（不向上抛, health 端点保持 200）。"""
    monkeypatch.setattr(ag, "DEEPSEEK_API_KEY", "sk-real-key")
    monkeypatch.setattr(ag, "_build_llm", lambda: BoomLLM())
    assert await ag.ping_llm(timeout=1.0) is False


async def test_health_cache_reuses_result_within_ttl(monkeypatch) -> None:
    """TTL 内重复探测复用缓存, 不重复打 API。"""
    routes._llm_health_cache = None
    calls = {"n": 0}

    async def fake_ping(timeout=2.5):
        calls["n"] += 1
        return True

    monkeypatch.setattr(routes, "ping_llm", fake_ping)
    assert await routes._check_llm_available() is True
    assert await routes._check_llm_available() is True
    assert calls["n"] == 1


async def test_health_cache_expires_after_ttl(monkeypatch) -> None:
    """缓存过期后重新探测。"""
    routes._llm_health_cache = None
    calls = {"n": 0}

    async def fake_ping(timeout=2.5):
        calls["n"] += 1
        return True

    monkeypatch.setattr(routes, "ping_llm", fake_ping)
    await routes._check_llm_available()
    # 把缓存时间戳拨回 TTL 之外
    cache = routes._llm_health_cache
    assert cache is not None
    routes._llm_health_cache = (cache[0] - routes._LLM_HEALTH_TTL_S - 1, True)
    await routes._check_llm_available()
    assert calls["n"] == 2
