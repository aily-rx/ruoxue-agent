"""真实链路 claim 级抽检 — 拆解 faithfulness 低分的构成（决策第 1 步）。

运行（本地, 需要 DEEPSEEK_API_KEY + faiss_data/）:
    python -m pytest backend/tests/eval/test_real_chain_claim_audit.py -v -s
    REAL_AUDIT_LIMIT=50 ...   # 默认只抽前 20 题, 可用环境变量扩到 50

背景（2026-08-17）:
    ragas faithfulness 在真实链路实测仅 ~0.17, 远低于合成答案 0.905。该指标
    把回答中"无出处"的句子全部计入, 而真实回复天然包含寒暄/情绪/过渡等
    无害内容 → 低分是"度量错配 + 自由生成"的混合产物, 不能直接指导优化。
    本脚本把低分拆成可决策的两类:
      - 有害无根据: 事实性陈述（参数/文件名/架构/机制等）在检索上下文中
        没有出处 → 真幻觉, 该修
      - 无害无根据: 非事实性内容（寒暄/情绪/过渡/建议）→ 产品价值, 不该修
    同时记录每题检索是否命中 gold chunk, 把"无根据"再归因到检索 miss
    （上下文缺信息）还是模型自由发挥（有上下文不用）。

流程（每题）:
  1. 真实链路: run_agent_stream(question) 流式收集回答, 剥离 [EMOTION: ...] 标签
  2. 上下文复现: search_hybrid(k=4) → _docs[:2000]（与产品一致）
  3. Step A: judge 从回答抽取陈述并标注 factual（寒暄等不抽取）
  4. Step B: judge 逐条判定事实性陈述能否被上下文支撑
  5. 汇总: 有害幻觉率 / 无害无根据占比 / 整体无根据率（对照 1 - faithfulness）
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import pytest
from backend.agent.agent_graph import run_agent_stream  # noqa: E402
from backend.agent.emotional_agent import EMOTION_TAG_RE  # noqa: E402
from backend.agent.rag_service import knowledge_base  # noqa: E402
from backend.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL  # noqa: E402
from backend.tests.eval.dataset import EVAL_CASES  # noqa: E402

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_HAS_KB = (_PROJECT_ROOT / "faiss_data" / "knowledge.index").exists()
_HAS_KEY = bool(DEEPSEEK_API_KEY) and DEEPSEEK_API_KEY != "your-api-key-here"

pytestmark = pytest.mark.skipif(
    not _HAS_KEY or not _HAS_KB,
    reason="需要 DEEPSEEK_API_KEY + faiss_data/（本地手动跑）",
)

_CONTEXT_K = 4  # 与产品 KnowledgeBase.search() 默认一致
_CONTEXT_CHARS = 2000  # 与 test_rag_generation_real.py 一致
_AUDIT_LIMIT = int(os.getenv("REAL_AUDIT_LIMIT", "20"))
_MAX_CONCURRENCY = 2  # judge 并发上限
_JUDGE_MAX_TOKENS = 8192  # 结构化 JSON 输出防截断（同 ragas 踩坑）


class _JudgeError(Exception):
    """judge 输出无法解析（JSON 缺失/格式错）。"""


async def _judge_json(client, system: str, user: str, attempts: int = 3) -> dict:
    """调用 judge 并解析 JSON 输出, 失败重试; 全败抛 _JudgeError。"""
    last_exc: Exception | None = None
    for _ in range(attempts):
        try:
            resp = await client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0,
                max_tokens=_JUDGE_MAX_TOKENS,
            )
            content = resp.choices[0].message.content or ""
            match = re.search(r"\{[\s\S]*\}", content)
            if match is None:
                raise _JudgeError("输出中无 JSON")
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except Exception as exc:  # noqa: BLE001 — judge 偶发截断/格式漂移, 重试兜底
            last_exc = exc
    raise _JudgeError(f"judge 重试 {attempts} 次仍失败: {last_exc!r}")


async def _extract_claims(client, question: str, answer: str) -> list[dict]:
    """Step A: 抽取回答中的陈述并标注是否事实性（寒暄/情绪/过渡不抽取）。"""
    system = (
        "你是评估助手。给定一段数字人助手的回复，抽取其中所有独立的陈述（claim），"
        "并判断每条陈述是否为事实性内容。\n"
        "要求：\n"
        "1. 只抽取内容性陈述——涉及技术参数、文件名、数值、架构、流程、机制、"
        "原因、事件等具体信息的断言。\n"
        "2. 不抽取：寒暄、情绪表达、口头语、过渡句、建议、个人感受"
        "（如“你好呀”“哈哈”“别担心”“这个问题很好”）。"
        "若一条内容性陈述里混有寒暄成分，只抽取其中的事实部分。\n"
        "3. factual=true 表示该陈述是可被外部资料验证的事实性断言；"
        "factual=false 表示其他内容（含“我不知道/没有相关信息”类元陈述）。\n"
        '4. 只输出 JSON：{"claims": [{"text": "...", "factual": true}]}'
    )
    data = await _judge_json(client, system, f"问题：{question}\n\n回复：{answer}")
    claims = data.get("claims") or []
    return [{"text": str(c.get("text", "")), "factual": bool(c.get("factual"))} for c in claims if c.get("text")]


async def _verify_claims(client, question: str, contexts: list[str], factual_claims: list[str]) -> list[bool]:
    """Step B: 逐条判定事实性陈述能否被检索上下文支撑。"""
    if not factual_claims:
        return []
    system = (
        "你是事实核查助手。给定问题和检索上下文，逐条判断每条陈述能否被上下文支持。\n"
        "判定标准：\n"
        "- supported=true：上下文包含与陈述相同的信息（允许同义改写、"
        "允许由多条片段共同支撑）。\n"
        "- supported=false：上下文没有该信息，或上下文与陈述矛盾。"
        "注意：上下文只是没提及也一律算 false（无出处即不支撑）。\n"
        '- 只输出 JSON：{"verdicts": [{"claim": "...", "supported": true}]}，'
        "claim 必须原样引用输入陈述，不要改写。"
    )
    claims_text = "\n".join(f"- {c}" for c in factual_claims)
    contexts_text = "\n\n".join(f"[片段{i + 1}] {c}" for i, c in enumerate(contexts))
    data = await _judge_json(
        client, system, f"问题：{question}\n\n陈述列表：\n{claims_text}\n\n检索上下文：\n{contexts_text}"
    )
    verdicts = data.get("verdicts") or []
    by_claim = {str(v.get("claim", "")): bool(v.get("supported")) for v in verdicts}
    return [by_claim.get(c, False) for c in factual_claims]


async def _audit_one(client, case: dict, sem: asyncio.Semaphore) -> dict:
    """单题: 真实链路回答 → 上下文复现 → claim 抽取 → 支撑判定。"""
    question = case["question"]

    # 1. 真实链路回答（流式 token 拼装, 剥离情绪标签）
    tokens: list[str] = []
    async for ev in run_agent_stream(question, history=[], request_id="claim-audit"):
        if ev.event == "token":
            data = ev.data
            assert isinstance(data, dict)
            tokens.append(str(data.get("text", "")))
    answer = EMOTION_TAG_RE.sub("", "".join(tokens)).strip()

    # 2. 检索上下文复现 + gold 命中判定（把无根据归因到检索还是生成）
    hits = knowledge_base.search_hybrid(question, k=_CONTEXT_K)
    contexts = [knowledge_base._docs[idx][:_CONTEXT_CHARS] for idx, _ in hits]
    hit = any(case["fragment"] in doc for doc in contexts)

    async with sem:
        claims = await _extract_claims(client, question, answer)
        factual = [c["text"] for c in claims if c["factual"]]
        verdicts = await _verify_claims(client, question, contexts, factual)
    factual_verdict = list(zip(factual, verdicts, strict=False))

    n_supported = sum(1 for _, ok in factual_verdict if ok)
    n_unsupported = sum(1 for _, ok in factual_verdict if not ok)
    return {
        "question": question,
        "hit": hit,
        "answer": answer,
        "n_total": len(claims),
        "n_factual": len(factual_verdict),
        "n_supported": n_supported,
        "n_unsupported": n_unsupported,
        "n_nonfactual": sum(1 for c in claims if not c["factual"]),
        "unsupported": [c for c, ok in factual_verdict if not ok],
        "supported": [c for c, ok in factual_verdict if ok],
    }


def _print_summary(rows: list[dict]) -> None:
    """汇总输出: 有害/无害构成 + 检索命中分组归因。"""
    n_total = sum(r["n_total"] for r in rows)
    n_nonfactual = sum(r["n_nonfactual"] for r in rows)
    n_factual = sum(r["n_factual"] for r in rows)
    n_supported = sum(r["n_supported"] for r in rows)
    n_unsupported = sum(r["n_unsupported"] for r in rows)
    harmful = n_unsupported / n_factual if n_factual else 0.0
    nonfactual_share = n_nonfactual / n_total if n_total else 0.0
    overall = (n_nonfactual + n_unsupported) / n_total if n_total else 0.0

    print(
        f"\n[CLAIM AUDIT] 样本={len(rows)} 陈述总数={n_total} "
        f"事实性={n_factual} 其中支撑={n_supported}/无出处={n_unsupported} 非事实性={n_nonfactual}"
    )
    print(f"  有害幻觉率（无出处事实性/事实性）: {harmful:.3f}")
    print(f"  无害无根据占比（非事实性/总数）: {nonfactual_share:.3f}")
    print(f"  整体无根据率（(非事实性+无出处)/总数）: {overall:.3f}  ← 对照 1 - faithfulness ≈ 0.824")

    hit_rows = [r for r in rows if r["hit"]]
    miss_rows = [r for r in rows if not r["hit"]]
    for label, group in (("检索命中", hit_rows), ("检索未命中", miss_rows)):
        f_cnt = sum(r["n_factual"] for r in group)
        u_cnt = sum(r["n_unsupported"] for r in group)
        print(
            f"  [{label}] {len(group)} 题: 事实性={f_cnt} 无出处={u_cnt} "
            f"组内有害幻觉率={u_cnt / f_cnt if f_cnt else 0:.3f}"
        )

    print("\n[每行明细] hit | 事实性/支撑/无出处 | 非事实性 | 问题")
    for r in rows:
        print(
            f"  {'H' if r['hit'] else 'M'} {r['n_factual']}/{r['n_supported']}/{r['n_unsupported']} "
            f"非事实={r['n_nonfactual']} | {r['question'][:28]}"
        )
    print("\n[回答摘录（人工复核非事实性分类）]")
    for r in rows:
        print(f"  [{r['question'][:20]}...] {r['answer'][:160]}")
    print("\n[无出处事实性陈述明细（人工复核）]")
    for r in rows:
        for c in r["unsupported"]:
            print(f"  ✗ [{r['question'][:20]}...] {c}")


@pytest.mark.asyncio
async def test_real_chain_claim_audit() -> None:
    """跑真实链路 claim 级抽检, 输出构成分析（结果解读见分析文档）。"""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    sem = asyncio.Semaphore(_MAX_CONCURRENCY)
    cases = EVAL_CASES[:_AUDIT_LIMIT]
    rows: list[dict] = []
    for case in cases:
        try:
            rows.append(await _audit_one(client, case, sem))
            print(f"  done {len(rows)}/{len(cases)} | {case['question'][:28]}", flush=True)
        except Exception as exc:  # noqa: BLE001 — 单题失败不中断整体
            print(f"  FAIL {case['question'][:28]}: {exc!r}", flush=True)

    _print_summary(rows)
    assert rows, "全部样本失败, 无法出结果"
