# text/ — 过程性与准备性文档仓库

> **规则**：面试准备、评估数据、补全过程复盘等**过程性/准备性/复盘类**文档一律放本目录并按分类存放。
> `docs/` 只保留正式设计文档（PRD、架构、API 协议、阶段总结）。

## 分类规则

| 分类目录 | 放什么 | 命名建议 |
|---|---|---|
| `text/interview/` | 面试准备、知识点图谱、简历叙事、模拟问答 | `xxx.md` 或按主题命名 |
| `text/rag/` | RAG 评估基线、实验数据、优化记录、指标对比 | `rag-xxx.md` |
| `text/retrospective/` | 短板补全过程复盘（含"怎么补 + 面试怎么讲"） | `短板N-xxx复盘.md` |

新增分类需在 AGENTS.md「文档归属约定」同步登记。

## 生成流程（新建文档时遵守）

1. 判断文档类型，放进对应分类目录（不新建分类除非确有需要）
2. 更新本文档索引表（下表）
3. 文档间相互引用时使用相对 `text/` 路径（如 `text/rag/rag-eval.md`）
4. **每个短板补全完成后，必须落盘复盘文档**：按 `retrospective/短板1-评估体系补全过程复盘.md` 的固定格式（30 秒版 / 背景 / 步骤详解 / 思维模式 / 概念词典 / 下一步 / 文件清单），存为 `retrospective/短板N-xxx补全过程复盘.md`，并登记到本索引

## 索引

| 文档 | 分类 | 说明 | 更新日期 |
|---|---|---|---|
| `rag/rag-eval.md` | rag | RAG 检索质量评估基线（Recall@k / MRR），三配置对比 0.15→0.95 | 2026-08-13 |
| `rag/rag-generation-eval.md` | rag | RAG 生成质量评估基线（RAGAS 三指标：faithfulness 0.905 / relevancy 0.595 / precision 0.781） | 2026-08-14 |
| `rag/rag-real-chain-claim-audit.md` | rag | 真实链路 claim 级抽检：faithfulness 0.176 低分构成拆解（支撑率 0.369 / 检索传导实证 / 三类归因） | 2026-08-17 |
| `retrospective/短板1-评估体系补全过程复盘.md` | retrospective | 建立 RAG 评估体系的完整过程复盘（含排查思维链） | 2026-08-13 |
| `retrospective/短板2-混合检索补全过程复盘.md` | retrospective | BM25 + 中文 embedding + RRF 混合检索补全过程复盘 | 2026-08-13 |
| `retrospective/短板3-测试覆盖率补全过程复盘.md` | retrospective | 测试覆盖率 14%→74% 补全过程复盘（mock 手法/断言教训） | 2026-08-14 |
| `retrospective/短板4-错误处理与容错补全过程复盘.md` | retrospective | 四层容错补全过程复盘（循环上限/LLM 重试/防幻觉/文件上限） | 2026-08-14 |
| `retrospective/短板5-可观测性补全过程复盘.md` | retrospective | 全链路 JSON 日志与 request_id 追踪补全过程复盘 | 2026-08-14 |
| `retrospective/短板6-并发缓存与成本补全过程复盘.md` | retrospective | 单例/embedding 缓存/回复缓存三边界/usage 记账补全过程复盘 | 2026-08-14 |
| `retrospective/短板7-安全与Prompt注入防护补全过程复盘.md` | retrospective | 白名单沙箱/防注入隔离/输出护栏补全过程复盘（7 短板收官） | 2026-08-14 |
| `retrospective/收尾1-评估集扩充与评估方法学验证复盘.md` | retrospective | 评估集 20→50 题（0.95→0.78 修正）+ 真实链路对照推翻"合成=下限"假设 | 2026-08-14 |
| `retrospective/收尾2-Human-in-the-loop复盘.md` | retrospective | LangGraph interrupt 工具确认闭环（三个时序坑/测试设计） | 2026-08-14 |
| `retrospective/收尾3-项目优化项审查与P0处置复盘.md` | retrospective | 全项目优化项审查（14 项分级）+ P0 处置：工具按需绑定实测推翻/健康检查真实化/print→logger | 2026-08-15 |
