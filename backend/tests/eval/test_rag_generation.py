"""RAG 生成质量评估 — RAGAS 三指标（短板① 第二层）。

运行（本地, 需要 DEEPSEEK_API_KEY + faiss_data/）:
    python -m pytest backend/tests/eval/test_rag_generation.py -v -s

流程（每个样本）:
  1. 检索: knowledge_base.search_hybrid(q, k=4) → 与产品 search() 一致的前 4 段
  2. 生成: DeepSeek 仅基于上下文合成答案（不编造, 无资料则明说）
  3. 评分: RAGAS 三指标（judge = DeepSeek, embeddings = 本地 bge）
     - faithfulness     回答是否忠实于上下文（有无编造）
     - answer_relevancy 回答是否切题（仅需 question + answer）
     - context_precision 检索上下文对回答的支撑度（reference = 生成的答案）

环境说明:
  - ragas 未安装 / 无 API Key / faiss_data 缺失 → 跳过（CI 不红）
  - 成本: 20 题 × ~12 次 judge 调用 ≈ 300 次 deepseek-v4-flash 调用, < 1 元
  - 已知限制: ragas 默认英文句切分, 中文 faithfulness 可能系统性偏低,
    以 answer_relevancy / context_precision 为主指标
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest
from backend.agent.rag_service import _embed, knowledge_base  # noqa: E402
from backend.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL  # noqa: E402
from backend.tests.eval.dataset import EVAL_CASES  # noqa: E402

# 必须先注入 ragas 兼容 stub 再 import ragas（见 ragas_compat.py 模块 docstring）
from backend.tests.eval.ragas_compat import (  # noqa: E402
    HAS_RAGAS,
    AnswerRelevancy,
    BaseRagasEmbedding,
    ContextPrecision,
    Faithfulness,
    llm_factory,
)

_logger = logging.getLogger("eval.rag_generation")

# ---------------------------------------------------------------------------
# 前置条件: ragas / API Key / 知识库 三缺一就跳过（与检索评估同策略）
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_HAS_KB = (_PROJECT_ROOT / "faiss_data" / "knowledge.index").exists()
_HAS_KEY = bool(DEEPSEEK_API_KEY) and DEEPSEEK_API_KEY != "your-api-key-here"

pytestmark = pytest.mark.skipif(
    not HAS_RAGAS or not _HAS_KEY or not _HAS_KB,
    reason="需要 ragas + DEEPSEEK_API_KEY + faiss_data/（本地手动跑）",
)

_CONTEXT_K = 4  # 与产品 KnowledgeBase.search() 默认一致
_MAX_CONCURRENCY = 2  # DeepSeek API 并发上限, 防限流/输出截断
_JUDGE_MAX_TOKENS = 8192  # ragas 结构化输出 JSON 默认 1024 会被截断（IncompleteOutput）


class BgeRagasEmbedding(BaseRagasEmbedding):
    """复用项目本地 bge-small-zh-v1.5 的 ragas embedding 适配器。

    不引入 sentence-transformers 依赖——直接走 rag_service._embed 的
    现有 transformers 实现（CLS pooling + L2 归一化）。
    """

    def embed_text(self, text: str, **kwargs) -> list[float]:
        return [float(x) for x in _embed([text])[0]]

    async def aembed_text(self, text: str, **kwargs) -> list[float]:
        return self.embed_text(text)


def _build_metrics(judge, embeddings) -> list:
    """每样本独立构造指标对象（ragas 指标非线程安全, 并发下不共享）。"""
    return [
        Faithfulness(llm=judge),
        AnswerRelevancy(llm=judge, embeddings=embeddings),
        ContextPrecision(llm=judge),
    ]


async def _generate_answer(client, question: str, contexts: list[str]) -> str:
    """仅基于检索上下文合成答案（RAGAS 官方推荐模式, 可复现）。"""
    prompt = (
        "请仅根据以下参考资料回答问题。如果参考资料中没有答案，"
        '请直接回答"资料中没有相关信息"。不要编造资料之外的内容。\n\n'
        + "\n\n".join(f"[资料{i + 1}] {c}" for i, c in enumerate(contexts))
    )
    resp = await client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": "你是严格基于参考资料作答的问答助手。"},
            {"role": "user", "content": f"问题：{question}\n\n{prompt}"},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    return resp.choices[0].message.content or ""


async def _score_one(sem: asyncio.Semaphore, judge, embeddings, gen_client, case: dict) -> dict:
    """单个样本: 检索 → 生成 → 三指标评分。返回 {question, answer, 三分数}。"""
    async with sem:
        question = case["question"]
        hits = knowledge_base.search_hybrid(question, k=_CONTEXT_K)
        contexts = [knowledge_base._docs[idx][:2000] for idx, _ in hits]
        answer = await _generate_answer(gen_client, question, contexts)

        row: dict = {"question": question, "answer_len": len(answer)}
        for metric in _build_metrics(judge, embeddings):
            name = metric.name
            print(f"  scoring {name} | {question[:24]}...", flush=True)
            if name == "faithfulness":
                result = await metric.ascore(user_input=question, response=answer, retrieved_contexts=contexts)
            elif name == "answer_relevancy":
                result = await metric.ascore(user_input=question, response=answer)
            else:  # context_precision: 参数名是 reference 而非 response
                result = await metric.ascore(user_input=question, reference=answer, retrieved_contexts=contexts)
            row[name] = float(result.value)
        return row


@pytest.mark.asyncio
async def test_rag_generation_quality() -> None:
    """跑 20 题基线: 检索→生成→RAGAS 三指标, 输出每样本明细与汇总。"""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    judge = llm_factory(DEEPSEEK_MODEL, client=client, max_tokens=_JUDGE_MAX_TOKENS)
    embeddings = BgeRagasEmbedding()
    sem = asyncio.Semaphore(_MAX_CONCURRENCY)

    rows = await asyncio.gather(*[_score_one(sem, judge, embeddings, client, case) for case in EVAL_CASES])

    # 汇总与明细输出（-s 查看）
    keys = ("faithfulness", "answer_relevancy", "context_precision")
    avg = {k: sum(r[k] for r in rows) / len(rows) for k in keys}
    print(f"\n[RAG GEN EVAL] 样本数={len(rows)}")
    for k in keys:
        print(f"  {k}: {avg[k]:.3f}")
    for r in sorted(rows, key=lambda x: x["faithfulness"]):
        print(f"  {r['faithfulness']:.2f}/{r['answer_relevancy']:.2f}/{r['context_precision']:.2f}  {r['question']}")

    # 防回归断言（2026-08-14 基线: 0.905 / 0.595 / 0.781）
    # 阈值按基线打折留余量, 只防"链路整体失效", 不追求绝对值:
    #   faithfulness 0.905 → ≥ 0.60（编造类回归）
    #   context_precision 0.781 → ≥ 0.50（检索上下文支撑度回归）
    #   answer_relevancy 已知系统性偏低 → ≥ 0.30（仅防完全失效）
    for k in keys:
        assert 0.0 <= avg[k] <= 1.0, f"{k} 超出合法范围: {avg[k]}"
    assert avg["faithfulness"] >= 0.60, f"faithfulness 回归: {avg['faithfulness']:.3f} < 0.60"
    assert avg["context_precision"] >= 0.50, f"context_precision 回归: {avg['context_precision']:.3f} < 0.50"
    assert avg["answer_relevancy"] >= 0.30, f"answer_relevancy 回归: {avg['answer_relevancy']:.3f} < 0.30"
    assert all(0.0 <= r[k] <= 1.0 for r in rows for k in keys)
