"""真实链路对照评估 — 验证评估指标的含义边界（短板① 生成层收尾）。

运行（本地, 需要 DEEPSEEK_API_KEY + faiss_data/）:
    python -m pytest backend/tests/eval/test_rag_generation_real.py -v -s

2026-08-14 对照结论（真实数据修正了设计假设）:
- 合成答案 faithfulness = 0.905（test_rag_generation.py, 20 题均值）
- 真实链路 faithfulness ≈ 0.26（本文件实测）
- 结论: faithfulness 度量的是"回答贴合给定上下文的程度"——合成答案被
  prompt 约束"仅根据资料回答"所以高; 真实回复是自由生成（情绪标签、寒暄、
  模型自身知识补充）, 天然包含上下文之外的陈述所以低。
  两者度量不同维度, 不能直接比高低;"合成 = 下限"假设不成立,
  合成评估的正确解读是"约束生成下的检索+生成质量", 而非真实链路的下限。
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

# ragas 兼容 stub（必须在 import ragas 前执行）
if "langchain_community.chat_models.vertexai" not in sys.modules:
    _stub = types.ModuleType("langchain_community.chat_models.vertexai")
    _stub.ChatVertexAI = type("ChatVertexAI", (), {})  # type: ignore[attr-defined]
    _stub.VertexAI = type("VertexAI", (), {})  # type: ignore[attr-defined]
    sys.modules["langchain_community.chat_models.vertexai"] = _stub

from backend.agent.rag_service import knowledge_base  # noqa: E402
from backend.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL  # noqa: E402
from backend.tests.eval.ragas_compat import HAS_RAGAS, Faithfulness, llm_factory  # noqa: E402

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_HAS_KB = (_PROJECT_ROOT / "faiss_data" / "knowledge.index").exists()
_HAS_KEY = bool(DEEPSEEK_API_KEY) and DEEPSEEK_API_KEY != "your-api-key-here"

pytestmark = pytest.mark.skipif(
    not HAS_RAGAS or not _HAS_KEY or not _HAS_KB,
    reason="需要 ragas + DEEPSEEK_API_KEY + faiss_data/（本地手动跑）",
)

# 选"答案明确存在于知识库"的题, 保证 contexts 一定包含支撑内容（对照才公平）
_REAL_CASES = [
    "Live2D 模型渲染出现白色矩形覆盖部件是什么原因？",
    "数字人处于思考状态时表情如何表现？",
]


@pytest.mark.asyncio
async def test_real_chain_faithfulness_scorable() -> None:
    """真实链路能完成评估且分数落在合法范围（对照意义见模块 docstring）。"""
    from backend.agent.agent_graph import run_agent_stream
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    judge = llm_factory(DEEPSEEK_MODEL, client=client, max_tokens=8192)
    metric = Faithfulness(llm=judge)

    for question in _REAL_CASES:
        # 真实 Agent 链路（完整 prompt + 工具调用）
        tokens: list[str] = []
        async for ev in run_agent_stream(question, history=[], request_id="real-eval"):
            if ev.event == "token":
                data = ev.data
                assert isinstance(data, dict)
                tokens.append(str(data.get("text", "")))
        answer = "".join(tokens).strip()
        assert answer, f"真实链路无回复: {question}"

        # 复现工具内部的 contexts（search_knowledge → search_hybrid k=4）
        hits = knowledge_base.search_hybrid(question, k=4)
        contexts = [knowledge_base._docs[idx][:2000] for idx, _ in hits]

        # 真实回复可能很长 + DeepSeek 偶发截断 → 截前 600 字符并重试评分
        answer_short = answer[:600]
        result = None
        for _ in range(3):
            try:
                result = await metric.ascore(user_input=question, response=answer_short, retrieved_contexts=contexts)
                break
            except Exception as exc:  # IncompleteOutput 等 judge 偶发错误
                print(f"    评分重试: {exc.__class__.__name__}")
        assert result is not None, f"评分 3 次重试均失败: {question}"
        print(f"  真实链路 faithfulness: {result.value:.3f} | {question[:24]}...")
        assert 0.0 <= result.value <= 1.0, f"分数越界: {question}"

    # 对照说明（2026-08-14 实测: 真实 ~0.26 vs 合成 0.905, 含义见模块 docstring）
    print("  对照: 合成答案 faithfulness 基线 = 0.905; 真实链路明显更低（自由生成）")
