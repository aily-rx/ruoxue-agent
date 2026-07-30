---
name: defensive-output
description: LLM 输出不可信，在被下游系统消费前必须做多层过滤。Use when LLM-generated text feeds into TTS, code execution, JSON parsing, database queries, or any automated pipeline.
---

# LLM 输出防护

**核心信念**：Prompt 是请求，不是保证。LLM 的输出永远不可信——它不是按规范生成，而是按概率生成。

**原则**：任何 LLM 输出在被下游消费前，必须经过显式的、可观测的过滤管道。

## 步骤

### 1. 识别下游消费者

列出所有消费 LLM 输出的系统：

| 消费者 | 风险 | 防御措施 |
|---|---|---|
| TTS 语音合成 | emoji/符号/action tag 被朗读 | 正则过滤 → 白名单字符 |
| JSON.parse() | 多余文本/注释导致解析失败 | 提取 JSON 块 → 校验 schema |
| 代码执行 | 恶意或错误代码 | sandbox + human-in-the-loop |
| 数据库查询 | SQL 注入/非法操作 | 参数化查询 + 权限限制 |

### 2. 构建过滤管道

以 LLM → TTS 为例，三层过滤：

```
LLM 原始输出
    │
    ▼
Layer 1: 去除 emoji → Unicode 范围匹配
    │
    ▼
Layer 2: 去除 action tag → 正则匹配 *(动作)*、[动作]、**动作**
    │
    ▼
Layer 3: 去除 markdown 符号 → 匹配 *#_~` 等非语音符号
    │
    ▼
清洗后文本 → TTS 合成
```

### 3. 每层加日志

每层过滤前后记录差异，方便排查：
- emoji 过滤掉了几个字符
- action tag 过滤掉了什么内容
- 符号过滤是否异常（大量文本被误杀说明规则太宽）

### 4. 加兜底

每种消费者都要有独立的故障处理：
- TTS 失败 → 仍返回文字回复（非致命附加功能）
- JSON 解析失败 → 返回错误信息，不静默吞掉
- 代码执行失败 → sandbox 超时 + 错误日志

## 反模式

- **"我在 prompt 里说了不要输出 emoji，所以肯定不会有"** — LLM 不遵守指令是常态
- **"输出看起来像 JSON，直接 parse"** — LLM 经常在 JSON 前后加解释文字
- **TTS 出乱码才加过滤** — 应该是先加过滤再喂给 TTS
- **过滤规则写死某几种 emoji** — emoji 集合不断增长，用 Unicode 范围匹配

## 实战案例

### TTS 朗读 emoji
- **问题**：用户听到"你好呀笑脸今天天气真好"
- **根因**：LLM 输出含 emoji，直接传入 Edge TTS
- **修复**：TTS 合成前增加 Unicode emoji 范围过滤

### TTS 朗读 action tag
- **问题**：用户听到"让我想想歪头思考答案是……"
- **根因**：LLM 输出含旁白标记，尽管 prompt 明确禁止
- **修复**：正则过滤 `*(...)*`、`[...]` 等模式

### TTS 卡顿在符号处
- **问题**：TTS 在 `**重要**`、`# 标题` 处停顿异常
- **根因**：LLM 输出含 markdown 格式符号
- **修复**：第三层过滤，strip 所有非语音字符

## 适用场景

- LLM → TTS 语音合成（核心场景）
- LLM → JSON 解析（提取结构化数据）
- LLM → 代码执行（Agent 工具调用）
- LLM → 数据库操作（生成的 SQL）
- 任何 LLM 输出被机器消费的场景
