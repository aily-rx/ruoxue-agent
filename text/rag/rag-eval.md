# RAG 检索质量评估基线

> 运行方式: `python -m pytest backend/tests/eval/test_rag_retrieval.py -v -s`
> 数据: faiss_data 13501 chunks（2026-08-13 重建，28 份文档）

## 一、最终对比（2026-08-13 完整结果）

| 配置 | Recall@1 | Recall@3 | Recall@5 | MRR@5 |
|------|:---:|:---:|:---:|:---:|
| ① 英文向量 all-MiniLM-L6-v2（原始） | 0.050 | 0.150 | 0.150 | 0.092 |
| ② 中文向量 bge-small-zh-v1.5 | 0.350 | 0.500 | 0.700 | 0.459 |
| ③ 中文向量 + BM25 混合（RRF） | **0.650** | **0.800** | **0.950** | **0.749** |

**结论：混合检索（③）相比原始实现（①），Recall@5 提升 6.3 倍、MRR 提升 8.1 倍，
达到并超过本文件最初设定的目标线（Recall@5 ≥ 0.80 / Recall@1 ≥ 0.50 / MRR@5 ≥ 0.60）。**

## 一·五、评估集扩充（2026-08-14，n=50）

20 题样本量偏小（0.95 有高估成分）。扩充 30 题（覆盖架构分层/记忆设计/PRD 细节/
前端模块/安全规划等主题，fragment 全部来自知识库原文并经校验脚本确认存在）后：

| 配置 | Recall@1 | Recall@3 | Recall@5 | MRR@5 |
|------|:---:|:---:|:---:|:---:|
| 纯向量 | 0.380 | 0.500 | 0.600 | 0.454 |
| 混合（当前） | 0.500 | 0.640 | **0.780** | 0.588 |

**结论：50 题下 Recall@5=0.78 是更真实的水平估计**——新增题暴露了三类检索盲区：

| miss 类型 | 数量 | 例子 | 优化方向 |
|---|---|---|---|
| 跨语言（中文问题对英文原文） | 2 | "流式回复"→"SSE streaming reply"；"按什么维度隔离"→"Per-session history isolation" | 中英同义词扩展 / rerank |
| 反查类（问题不含答案关键词） | ~6 | "切片参数是多少"→"chunk_size=500"；"用什么文件"→"mtn_01 loop" | 问参数值/文件名的问题需要更强的语义召回，rerank 或扩充 bge 训练域 |
| 分词粒度 | ~3 | "ASRClient.ts"（BM25 词表可能为整串而非 "asr"）；"LLM 服务不可用" 目标 chunk 排名第 6+ | 英文串/驼峰名的 jieba 分词细化 |

**面试话术（诚实版）**：20 题样本下 Recall@5 0.95；扩充到 50 题后 0.78——差距来自
反查类和跨语言类问题，这正是评估集的价值：**数字从乐观变为可信**。

## 二、优化路径回顾

| 步骤 | 改动 | 效果 |
|------|------|------|
| 1 | 建立评估体系（20 题数据集 + Recall/MRR 指标） | 暴露真实水平：Recall@5=0.15 |
| 2 | 排查根因：阈值无误，英文 embedding 对中文向量坍缩 | 定位方向 |
| 3 | 换中文 embedding：bge-small-zh-v1.5（ModelScope 下载，本地 transformers 推理） | 纯向量 Recall@5 0.15 → 0.70 |
| 4 | 加 BM25 关键词检索（jieba 分词）+ RRF 合并 | 混合后 Recall@5 → 0.95 |

## 三、剩余短板（继续优化的方向）

1. **跨语言检索**：1 题未命中（"流式回复" → "SSE streaming reply"），中文问题对英文原文。
   候选方案：检索前中英同义词扩展、或 rerank 阶段用 cross-encoder 补。
2. **无 rerank**：当前 top-20 直接 RRF 排序取前 5，未做交叉编码器重排。
   影响：中位命中排名还有提升空间（MRR 0.749 未到 0.9）。
3. **评估集 20 题偏小**：后续补到 50+ 题，覆盖更多提问方式。
4. **生成质量评估未做**：本文件只覆盖检索层（Recall/MRR）。生成层（RAGAS 的
   faithfulness / answer_relevancy / context_precision）尚未落地——需要少量 API 调用，
   是"检索层已量化、生成层待补"的决策点（面试表述见 `text/interview/面试准备与项目补全指南.md`）。
   （2026-08-14 已解决：见 `text/rag/rag-generation-eval.md`）
5. **检索参数配置化**：✅ 已完成（2026-08-14）——`k/vector_k/bm25_k` 默认值
   已迁移到 `backend/config.py` 的 `RAG_TOP_K / RAG_VECTOR_K / RAG_BM25_K`，
   调参实验只需改环境变量/.env，不用改代码（显式传参仍优先）。

## 四、环境与依赖说明

- `rank_bm25` / `jieba` 已加入 `backend/requirements.txt`（运行时必需）
- `bge-small-zh-v1.5` 模型放 `model_assets/embeddings/`（已 gitignore），
  需要 `transformers` + `torch`（可选依赖，不装则自动回退英文 embedding）
- 重建索引：`python -c "from backend.agent.rag_service import KnowledgeBase; KnowledgeBase().index_directory('docs')"`
