"""Reranker 模块单元测试 — 模型缺失时优雅降级, 不依赖真实模型文件.

覆盖: available() 探测、rerank 在模型缺失时返回 []（调用方保持 RRF 顺序）、
空候选安全。
"""

from __future__ import annotations

from backend.agent.reranker import rerank


def test_available_probes_disk(tmp_path) -> None:
    """模型目录缺少核心文件时 available() 为 False（不抛异常）。"""
    # 模块级 _MODEL_DIR 指向真实位置; 通过 monkeypatch 探测临时空目录
    import backend.agent.reranker as mod

    mod._MODEL_DIR = tmp_path / "missing"
    mod._ready = None
    assert mod.available() is False


def test_rerank_empty_candidates() -> None:
    assert rerank("任何查询", []) == []


def test_rerank_missing_model_falls_back() -> None:
    """模型缺失时返回 []，调用方降级为纯 RRF 顺序。"""
    import backend.agent.reranker as mod

    mod._MODEL_DIR = mod.Path("model_assets/rerankers/not-exists-dir")
    mod._ready = None
    candidates = [(0, "文档A"), (1, "文档B")]
    assert rerank("查询", candidates) == []
