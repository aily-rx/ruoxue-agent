# Ruoxue — Agent 智能体 PRD

> 版本: v1.0 | 日期: 2026-07-24 | 状态: Phase 4 设计

---

## 一、需求概述

让数字人从"聊天机器人"升级为"AI 助手"——能调用工具、检索知识库、记住用户偏好。

---

## 二、Agent 架构

```
LangGraph StateGraph
|
+-- agent_node      LLM 推理 -> 决定是否需要工具
|       |
|       +-- DeepSeek/Ollama
|       +-- System Prompt (人设 + 工具说明)
|
+-- should_continue  判断是否需要调用工具
|       |
|       +-- yes -> tools_node
|       +-- no  -> END
|
+-- tools_node      执行工具调用
        |
        +-- search_web    网页搜索
        +-- read_file     文件读取
        +-- get_weather   天气查询
        +-- run_code      Python 执行 (沙箱)
```

---

## 三、工具清单

### Phase 4 实现:

| 工具 | 功能 | 实现 |
|------|------|------|
| search_web | 网页搜索 | Tavily API / DuckDuckGo |
| read_file | 读取本地文件 | pathlib + PyPDF |
| get_weather | 天气查询 | wttr.in / OpenWeather |
| list_dir | 列出目录文件 | pathlib |

### Phase 5 扩展:

| 工具 | 功能 | 实现 |
|------|------|------|
| run_code | Python 代码执行 | AstrBot Agent Sandbox |
| send_email | 发送邮件 | smtplib |
| calendar | 日程管理 | 本地 SQLite |

---

## 四、安全机制

**Human-in-the-loop:** 以下操作需用户确认后才执行:

- 删除文件
- 执行系统命令
- 发送邮件
- 修改配置

```
LangGraph interrupt_before=["tools_node"]
    |
    v
前端弹出确认框: "AI 要删除 xxx，确认吗？"
    |
    +-- 确认 -> Command(resume=...)
    +-- 取消 -> Command(goto="END")
```

---

## 五、记忆系统

### 短期记忆 (Phase 1)
- SQLite 存储当前会话历史
- 滑动窗口: 最近 20 轮对话

### 长期记忆 (Phase 4)
- Chroma 向量数据库
- Embedding: text-embedding-3-small
- 自动提取用户偏好和重要信息
- 检索: 相似度 > 0.7 的历史记忆

---

## 六、RAG 知识库 (Phase 4)

```
文档 (PDF/MD/TXT)
    |
    v
切片 (chunk_size=500, overlap=50)
    |
    v
Embedding
    |
    v
FAISS 向量索引
    |
    v
用户提问 -> 检索相关片段 -> LLM 回答
```

---

*最后更新: 2026-07-24*
