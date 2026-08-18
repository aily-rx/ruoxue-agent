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

## 四、D+A 实验记录（2026-08-15，负结果）

### D — 11 个 miss 逐题复核

重跑 50 题基线确认数字未漂移（0.500/0.640/0.780/0.588，与 08-14 记录一致），
对 11 个 miss 逐题检查 fragment 在知识库的存在性与 top-5 检索结果：

1. **题目质量：11 题全部公平**——每题 fragment 都真实存在于唯一/少数 gold chunk，
   无需修题删题（"Edge TTS 优点""参考项目架构"两题的答案都在
   《AI_Agent_数字人助手技术栈学习笔记.md》，题面没有歧义问题）。
2. **新发现① 元文档污染**："切片参数是多少"的 top1-2 是 RAG 评估复盘文档里
   "讨论切片参数"的文本——评估方法论文档被索引进知识库后与真实答案互相竞争
   （循环污染）。属知识库索引范围治理问题，需重建索引时排除 `text/rag/`、
   `text/retrospective/` 等元文档。
3. **新发现② chunk 边界劈裂答案**："LLM 服务不可用"的 fragment 被 chunk 切分
   劈成两半（top4 是含半个 fragment 的邻居 chunk），gold 判定苛刻。检索不算
   离谱，但暴露 chunk_size=500 对短答案的切分风险。

### A — 分词细化实验（回滚）

针对"分词粒度"类 miss（ASRClient.ts 等），给 `_tokenize` 加驼峰/下划线/点号
子词拆分，两个变体实测均**差于基线**：

| 变体 | Recall@1 | Recall@3 | Recall@5 | MRR@5 | miss 数 |
|------|:---:|:---:|:---:|:---:|:---:|
| 基线（原始） | 0.500 | 0.640 | **0.780** | 0.588 | 11 |
| 对称拆分（query+doc） | 0.460 | 0.600 | 0.760 | 0.556 | 12 |
| 非对称拆分（仅 doc） | 0.460 | 0.640 | 0.760 | 0.567 | 12 |

**回滚原因（机制）**：
- query 侧子词（SenseVoice→voice/sense）全库乱匹配，制造大量假阳性；
- doc 侧子词改变**语料平均文档长度**，BM25 长度归一化是全局量，所有分数被
  微扰，边界题（"中文口型级别"）翻转。

**结论**：分词不是这三类 miss 的解药。反查类/跨语言的语义鸿沟必须靠
**cross-encoder rerank（方案 B）或查询改写（方案 C）** 解决，分词细化方向关闭。

### B 方案上限检查（2026-08-15）

rerank 只能重排候选池，救不了池外题目。11 个 miss 的 gold 是否在 top20 候选池：

- 任一路（向量∪BM25）top20 可召回 **7/11**（切片参数/口型映射链路/Edge TTS/
  WordBoundary/LLM 错误事件/ASR 上传/参考项目架构）→ rerank 的理论上限
- 两路都召不回 **4/11**（Phase 1 流式/会话记忆隔离/待机动画/ASR 完整名称）→
  必须先修召回（查询改写/跨语言索引），rerank 无用

**结论：方案 B 的预期上限是把 11 miss 收到 4（保守估计 3-5 题），
完整解决需要 B（rerank）+ C（查询改写）组合 + 元文档污染治理。**

## 五、P0 修复：分块死循环 + 索引重建（2026-08-18）

### 发现：旧索引 97% 内容重复

检查 `faiss_data/knowledge_meta.json` 发现 `_chunk_text` 死循环 bug：

- **根因**：`start = end - overlap` 不保证前进——短行文档（markdown 表格/列表）
  的 chunk 实际长度 < overlap(80) 时，`end - 80 <= start`，同一片段被反复切出，
  直到 `max_chunks=500` 强制终止。
- **证据**：13501 条索引仅 **346 唯一（2.6%）**；27/28 文件全部恰好 500 条；
  `frontend/dependencies.md`（1200 字符）500 条中 497 条完全相同。
- **影响**：重复向量淹没 FAISS 索引、BM25 IDF 失真、排序质量被重复 chunk 干扰
  （Recall@1 / MRR 被系统性低估）。

### 修复（`rag_service.py` `_chunk_text`）

```python
next_start = end - overlap
start = next_start if next_start > start else end   # 死循环防护
```

overlap 只在 chunk 确实够长时生效，否则无重叠直接前进；`max_chunks` 500→10000。
修复后单测：表格 1506 字符→5 chunks（全唯一）、真实大文档 17255 字符→46 chunks（全唯一）。

### 重建后新基线（330 chunks，2026-08-18）

重建命令：`python -c "from backend.agent.rag_service import KnowledgeBase; KnowledgeBase().index_directory('docs')"`
（只索引 `docs/`，**顺带清除了 rag-eval.md / 短板复盘等元文档污染**）

| 配置 | Recall@1 | Recall@3 | Recall@5 | MRR@5 |
|------|:---:|:---:|:---:|:---:|
| 旧索引（13501 重复膨胀） | 0.500 | 0.640 | 0.780 | 0.588 |
| 纯向量（新索引） | 0.420 | 0.520 | 0.620 | 0.485 |
| 混合（新索引） | **0.600** | **0.740** | **0.780** | **0.662** |

**结论：Recall@1 +0.10、Recall@3 +0.10、MRR@5 +0.074（+12.6%），Recall@5 持平。
修复前评估集在重复膨胀语料上测量——top-1 精度和排序质量被重复 chunk 系统性低估，
真实检索能力比旧基线显示的更强。11 个 miss 中多题已因去重自动命中（rank 0→1）。**

## 六、Cross-encoder rerank 集成（2026-08-18）

### 背景：11 个 miss 的修复路径

§四 D 分析过：11 个 miss 中 7 个的 gold 在 top-20 候选池内（rerank 可救），
4 个在池外（rerank 救不了，需查询改写/跨语言索引——方案 C，本期未做）。

### 实现（方案 B：直接引入 rerank）

1. **bge-reranker-base**（本地 CPU，ModelScope 下载到
   `model_assets/rerankers/`，gitignore）——懒加载 + LRU 缓存（同 query 命中 2ms）；
   模型缺失/推理异常时**静默降级为 RRF 顺序**（`available()` 首次探测后只警告一次）。
2. **单路强信号保底 boost**（`RAG_RERANK_TOP_PASS=3`）：任一路 rank≤3 的 chunk
   fusion 时 +10.0——修复 RRF 固有缺陷"双路平庸 > 单路极强"
   （单路 rank=1 得 1/61=0.0164，会被 v=2/b=3 的 1/62+1/63=0.0317 挤掉）。
   若不保底，候选池会被双路平庸 chunk 占满，强信号 chunk 进不了 rerank 候选池。
3. 配置化（`backend/config.py`）：`RAG_RERANK_ENABLED` / `RAG_RERANK_CANDIDATES`
   （默认 20）/ `RAG_RERANK_TOP_PASS`（默认 3），改 .env 即可调参。

### 评估结果（330 chunks 新索引，n=50）

| 配置 | Recall@1 | Recall@3 | Recall@5 | MRR@5 | 延迟(新 query) |
|------|:---:|:---:|:---:|:---:|:---:|
| 纯 RRF+boost（无 rerank） | 0.580 | 0.780 | 0.780 | 0.673 | ~80ms |
| + rerank 10 候选 | 0.580 | 0.800 | 0.820 | 0.687 | ~1.4-1.7s |
| **+ rerank 20 候选（默认）** | **0.620** | **0.800** | **0.860** | **0.710** | ~3.2s |
| + rerank 20 候选, max_len=256 | 0.600 | 0.780 | 0.860 | 0.699 | ~2.8s |

**决策记录**：
- 默认 **20 候选 + max_length=512**（指标最优；CPU 推理确定性，256 vs 512 的
  0.02 差距经对照实验确认为真实截断损失，非噪声——长 chunk 超 256 token 被截断）。
- 延迟敏感场景可调 `RAG_RERANK_CANDIDATES=10`（R@5 0.82, ~1.7s）或
  `RAG_RERANK_ENABLED=0` 一键回到纯 RRF（0.78, ~80ms）；同 query 命中缓存仅 2ms。
- 成本核算：模型 1.1GB 磁盘 + 每 query ~3s CPU 推理（对比原 80ms）——纯本地推理
  无 API 费用；这是"延迟换 4 个点 Recall@5"的权衡，知识库问答场景可接受。

### 剩余短板（方案 C 未做，留档）

4 个池外 miss（Phase 1 流式/会话记忆隔离/待机动画/ASR 完整名称）需要
**查询改写**（query 扩写/中英翻译）或跨语言索引才能解决——本期未实现，见 §四 B 结论。
