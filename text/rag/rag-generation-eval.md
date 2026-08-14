# RAG 生成质量评估基线（RAGAS）

> 运行方式: `python -m pytest backend/tests/eval/test_rag_generation.py -v -s`
> 前置条件: 已装 ragas + DEEPSEEK_API_KEY + faiss_data/（三缺一自动跳过）
> 数据: 复用 `backend/tests/eval/dataset.py` 的 20 题（与检索评估同一套题）
> 评估链路: 检索（search_hybrid k=4）→ DeepSeek 仅基于上下文合成答案 → RAGAS 三指标（judge = DeepSeek, embeddings = 本地 bge-small-zh-v1.5）

## 一、基线（2026-08-14，20 样本，耗时约 12 分钟，成本 < 1 元）

| 指标 | 得分 | 回答的问题 |
|------|:---:|---|
| **faithfulness** | **0.905** | 回答有没有编造上下文之外的内容 |
| **answer_relevancy** | **0.595** | 回答是否切题（RAGAS 用 judge 反向生成问题算语义相似度） |
| **context_precision** | **0.781** | 检索出的上下文对回答的支撑程度 |

**解读（面试话术）**：
- faithfulness 0.905 说明"检索层 0.95 Recall 的高质量上下文 + 严格基于资料的生成"组合几乎不产生幻觉——**生成层没有给检索层拖后腿**
- context_precision 0.781 说明喂给 LLM 的 4 段上下文大部分被用上了（检索质量 → 生成质量的正向传导）
- answer_relevancy 偏低是**评估方法学的已知限制**（见下），不代表回答真的跑题

## 二、已知限制（诚实标注）

1. **answer_relevancy 系统性偏低**：RAGAS 该指标用 judge 从回答反向生成 N 个问题再算与原问题的语义相似度——中文短回答、以及"资料中没有相关信息"类回答（检索 miss 的题）天然得分低。**对比时只看相对变化，不追求绝对值高**。
2. **judge 是 DeepSeek 而非 GPT**：judge 模型不同分数绝对值会漂移——**同 judge 模型下的对比才有意义**（本基线即 DeepSeek 当 judge 的锚点）。
3. **中文句切分**：ragas 默认英文句切分器，中文按句号粗切，faithfulness 的逐句判断粒度偏粗。
4. **合成答案 ≠ 真实链路（2026-08-14 实测对照）**：真实链路 faithfulness 实测仅
   0.176/0.158（`test_rag_generation_real.py`），远低于合成答案 0.905——**"合成=下限"
   假设被数据推翻**。原因：faithfulness 度量"回答贴合给定上下文的程度"，合成答案被
   prompt 约束所以高；真实回复是自由生成（情绪标签/寒暄/模型知识补充），天然包含
   上下文之外的陈述。正确解读：**合成评估度量"约束生成下的检索+生成质量"，不代表
   真实链路的下限**——评估设计不能想当然，指标含义要靠对照实验验证。

## 三、技术要点（踩坑记录）

| 坑 | 解法 |
|---|---|
| ragas 0.4.3 无条件 import 已移除的 `langchain_community.chat_models.vertexai` | `ragas_compat.py` 注入 stub（ChatVertexAI 仅用于 isinstance 检查，永远不会实例化） |
| ragas 0.4.3 的 `evaluate()` 不认新 SimpleBaseMetric 指标 | 绕过 evaluate，直接调各指标 `ascore()`（三个指标参数名不同：faithfulness 用 response / answer_relevancy 只要 user_input+response / context_precision 参数名是 **reference**） |
| judge 输出被 max_tokens 截断（IncompleteOutput） | `llm_factory(..., max_tokens=8192)`（默认 1024 不够） |
| judge 需要异步客户端 | `AsyncOpenAI`（同步客户端 `agenerate()` 直接报错） |
| embeddings 要复用本地 bge | 自定义 `BgeRagasEmbedding` 实现 `BaseRagasEmbedding` 接口（embed_text/aembed_text），零新依赖 |
| 并发 4 时偶发输出截断 | 并发降到 2（`_MAX_CONCURRENCY=2`） |

## 四、重跑与对比

```bash
# 检索层（Recall@k/MRR）
python -m pytest backend/tests/eval/test_rag_retrieval.py -v -s
# 生成层（RAGAS 三指标）
python -m pytest backend/tests/eval/test_rag_generation.py -v -s
```

每次改 chunk 策略 / embedding / 检索 k / 生成 prompt 后重跑两套，检索层看 Recall/MRR，生成层看 RAGAS——**两个数字一起动才算优化**。

## 五、防回归线（2026-08-14 定值, 已固化为测试断言）

按基线（0.905 / 0.595 / 0.781）打折留余量，只防"链路整体失效"，不追绝对值：

| 指标 | 基线 | 防回归线 | 说明 |
|---|---|---|---|
| faithfulness | 0.905 | **≥ 0.60** | 编造类回归 |
| context_precision | 0.781 | **≥ 0.50** | 检索上下文支撑度回归 |
| answer_relevancy | 0.595 | **≥ 0.30** | 已知系统性偏低, 仅防完全失效 |

## 五、后续优化方向

1. answer_relevancy 分析：已加"无信息类 vs 正常类"分组输出（`RAGAS_LIMIT=50` 全量跑时查看）——无信息类回答天然拉低均值，分析结果见运行输出
2. 评估集扩到 50+ 题：✅ 已完成（2026-08-14）——检索层 50 题基线 Recall@5=0.78（20 题 0.95 是样本量高估），miss 分类见 `text/rag/rag-eval.md`
3. 真实链路对照：✅ 已完成（2026-08-14）——结论见"已知限制"第 4 条
