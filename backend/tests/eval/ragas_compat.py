"""ragas 0.4.3 与项目依赖的兼容层（生成质量评估专用）。

两个已知兼容问题的处理：
1. ragas/llms/base.py 无条件 import `langchain_community.chat_models.vertexai`
   —— 该模块已从新版 langchain-community 移除。ChatVertexAI 只用于 isinstance
   检查（MULTIPLE_COMPLETION_SUPPORTED 列表），本项目的 judge 是 DeepSeek，
   永远不会实例化它 → 在 import ragas 之前注入 stub 让 import 通过。
2. ragas 0.4.3 的 `evaluate()` 只接受旧 Metric 体系，而 collections 指标是
   新 SimpleBaseMetric 体系 → 评测脚本绕过 evaluate()，直接调各指标的
   `ascore()`（见 test_rag_generation.py）。

本模块必须先于任何 ragas import 被导入。
"""

import sys
import types

if "langchain_community.chat_models.vertexai" not in sys.modules:
    _stub = types.ModuleType("langchain_community.chat_models.vertexai")
    _stub.ChatVertexAI = type("ChatVertexAI", (), {})  # type: ignore[attr-defined]
    _stub.VertexAI = type("VertexAI", (), {})  # type: ignore[attr-defined]
    sys.modules["langchain_community.chat_models.vertexai"] = _stub

try:
    import ragas  # noqa: F401  — 仅验证 ragas 可用性
    from ragas.embeddings.base import BaseRagasEmbedding
    from ragas.llms import llm_factory
    from ragas.metrics.collections import AnswerRelevancy, ContextPrecision, Faithfulness

    HAS_RAGAS = True
except ImportError:
    HAS_RAGAS = False
    # 兜底名字: 未装 ragas 时 import 本模块仍须成功,
    # 由各测试的 pytestmark skipif(not HAS_RAGAS) 负责跳过
    BaseRagasEmbedding = None  # type: ignore[assignment, misc]
    llm_factory = None  # type: ignore[assignment, misc]
    AnswerRelevancy = None  # type: ignore[assignment, misc]
    ContextPrecision = None  # type: ignore[assignment, misc]
    Faithfulness = None  # type: ignore[assignment, misc]


__all__ = [
    "HAS_RAGAS",
    "BaseRagasEmbedding",
    "llm_factory",
    "AnswerRelevancy",
    "ContextPrecision",
    "Faithfulness",
]
