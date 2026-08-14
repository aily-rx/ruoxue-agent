"""RAG 检索质量评估 — Recall@k / MRR（短板① 基线 + 短板② 对比）。

运行（本地，需已构建 faiss_data/）：
    python -m pytest backend/tests/eval/test_rag_retrieval.py -v -s

评估两种检索方式并对比：
- search_indices : 纯向量检索（FAISS + all-MiniLM-L6-v2）→ 短板① 基线
- search_hybrid  : 向量 + BM25 混合检索（RRF 合并）→ 短板② 优化

历史基线（2026-08-13，纯向量，12501 chunks）：
    n=20  recall@1=0.050  recall@3=0.150  recall@5=0.150  mrr@5=0.092
    → 根因：英文 embedding 对中文向量坍缩，见 text/rag/rag-eval.md

基线用途：后续所有检索优化（rerank、chunk 策略调整、换 embedding）都以本文件
输出的指标为基准做对比，保证改动可量化、可回归。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.agent.rag_service import knowledge_base
from backend.tests.eval.dataset import EVAL_CASES

TOP_KS = (1, 3, 5)

# faiss_data/ 被 gitignore，CI 无知识库时跳过本评估（本地手动跑）
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(
    not (_PROJECT_ROOT / "faiss_data" / "knowledge.index").exists(),
    reason="faiss_data/ 未构建（被 gitignore），跳过 RAG 检索评估",
)


def _gold_chunk_indices(fragment: str) -> set[int]:
    """知识库中包含 fragment 的所有 chunk 下标（可能多个，任一命中即算命中）。"""
    return {idx for idx, doc in enumerate(knowledge_base._docs) if fragment in doc}


def _rank_of_gold(gold: set[int], results: list[tuple[int, float]]) -> int:
    """gold 中任一 chunk 在结果中的最小排名（1-based），未命中返回 0。"""
    for rank, (idx, _score) in enumerate(results, start=1):
        if idx in gold:
            return rank
    return 0


def _evaluate(method: str) -> dict:
    search = getattr(knowledge_base, method)
    recall: dict[int, int] = dict.fromkeys(TOP_KS, 0)
    mrr_total = 0.0
    n = len(EVAL_CASES)
    details: list[dict] = []

    for case in EVAL_CASES:
        gold = _gold_chunk_indices(case["fragment"])
        if not gold:
            raise AssertionError(f"评估数据无效：知识库中找不到 fragment {case['fragment']!r}")
        results = search(case["question"], k=max(TOP_KS))
        rank = _rank_of_gold(gold, results)
        if rank:
            mrr_total += 1.0 / rank
        for k in TOP_KS:
            if rank and rank <= k:
                recall[k] += 1
        details.append(
            {
                "question": case["question"],
                "rank": rank,
                "top_scores": [round(s, 3) for _, s in results],
            }
        )

    metrics = {
        "n": n,
        "recall@1": recall[1] / n,
        "recall@3": recall[3] / n,
        "recall@5": recall[5] / n,
        "mrr@5": mrr_total / n,
    }
    return {"metrics": metrics, "details": details}


@pytest.fixture(scope="module", autouse=True)
def _ensure_kb_loaded() -> None:
    """前置条件：faiss_data/ 知识库必须存在（评估针对真实索引）。"""
    assert knowledge_base.chunk_count > 0, "知识库为空：请在项目根目录运行（faiss_data/knowledge.index 缺失）"


@pytest.mark.parametrize("method", ["search_indices", "search_hybrid"])
def test_rag_retrieval_metrics(method: str, capsys: pytest.CaptureFixture[str]) -> None:
    """对比纯向量 vs 混合检索的指标。混合检索应显著优于纯向量。"""
    result = _evaluate(method)
    metrics, details = result["metrics"], result["details"]

    with capsys.disabled():
        print(
            f"\n[RAG EVAL:{method}] 样本数={metrics['n']}  "
            f"recall@1={metrics['recall@1']:.3f}  "
            f"recall@3={metrics['recall@3']:.3f}  "
            f"recall@5={metrics['recall@5']:.3f}  "
            f"mrr@5={metrics['mrr@5']:.3f}"
        )
        for d in details:
            flag = "hit " if d["rank"] else "miss"
            print(f"  {flag} rank={d['rank']:>2}  {d['question']}")

    # 阈值：防止检索链路整体失效（历史基线见模块 docstring）
    assert metrics["recall@5"] > 0, "检索完全失效，请检查知识库索引"
    assert metrics["recall@1"] > 0, "top-1 完全未命中，请检查检索链路"


def test_hybrid_improves_over_vector() -> None:
    """混合检索必须优于纯向量（短板② 的验收条件：Recall@5 显著提升）。"""
    vector = _evaluate("search_indices")["metrics"]
    hybrid = _evaluate("search_hybrid")["metrics"]
    assert (
        hybrid["recall@5"] > vector["recall@5"]
    ), f"混合检索未超过纯向量：vector={vector['recall@5']:.3f} hybrid={hybrid['recall@5']:.3f}"
    assert (
        hybrid["mrr@5"] > vector["mrr@5"]
    ), f"混合检索 MRR 未超过纯向量：vector={vector['mrr@5']:.3f} hybrid={hybrid['mrr@5']:.3f}"
