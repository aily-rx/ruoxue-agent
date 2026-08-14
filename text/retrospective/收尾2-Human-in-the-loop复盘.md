# 收尾② 补全过程复盘 — Human-in-the-loop：工具调用人工确认

> 日期: 2026-08-14 | 耗时: 约 3 小时
> 读者对象: 初学者（第一次接触"给 Agent 加人工审批"的人）
> 配套文件: `backend/agent/agent_graph.py`、`backend/routes.py`、`frontend/src/components/ChatPanel.tsx`、`backend/tests/unit/test_hitl.py`、`docs/frontend/prototype-chatpanel.md`

---

## 0. 这段路到底干了什么（30 秒版）

给 Agent 加上了"工具调用前人工确认"的完整闭环：

1. **后端**：`ConfirmingToolNode` 用 LangGraph 的 `interrupt()` 在工具执行前挂起 graph → SSE 发 `tool_request` 事件 → 用户经 `POST /api/hitl-confirm` 回复允许/拒绝 → `Command(resume)` 恢复执行（**超时默认拒绝**）
2. **前端**：ChatPanel 出现确认条（"若雪想调用工具：search_web，是否允许？" + 允许/拒绝按钮）
3. **测试**：5 个测试覆盖允许/拒绝/超时/未知 id/关闭开关，全量 124 测试全绿

**核心收获：HITL 不是"加个 if"，而是三个时序问题的叠加**——interrupt 怎么检测（流模式不产出 item）、确认 future 什么时候注册（必须先注册再发事件）、graph 状态怎么隔离（thread_id 必须每请求唯一）。三个坑都是"先实验验证框架行为"才能避开的。

---

## 1. 背景：为什么 Agent 需要"人工确认"

### 问题在哪

项目从 Phase 4 起就标注"Human-in-the-loop 待做"。补之前，Agent 调用工具是**全自动**的：

- 用户说"帮我搜索一下"，Agent 直接调 `search_web`
- 用户说"读一下这个文件"，Agent 直接调 `read_file`
- **没有任何人工确认环节**——如果 LLM 被诱导或误判，工具会直接执行

为什么需要确认？三个理由：
1. **安全**：工具是有副作用的操作（读文件、发请求），执行前确认是"可控 Agent"的基本要求（技术栈笔记里规划的安全设计）
2. **面试高频**："Agent 调工具失控怎么办？"——循环上限（短板④）防"停不下来"，HITL 防"不该调却调了"，两个答案都备着
3. **产品体验**：危险/重要操作让用户拍板，是 AI 应用从 demo 走向产品的分水岭

### 类比：给"爱自作主张的助手"加审批流

之前助手想干什么直接干（全自动）；现在重要操作要先问老板（用户）："我要打这个电话，可以吗？"——老板说可以才打，说不行就不打，**一直没回复默认不打**（超时拒绝）。

---

## 2. 步骤详解（每一步：干什么 / 为什么 / 类比）

---

### 步骤 1：选方案——LangGraph 的 interrupt 是标准答案

**在干什么：** 调研 HITL 的实现路径，选定 LangGraph 官方机制 `interrupt()`：
- 工具节点里调 `interrupt(payload)` → **graph 挂起**，状态保存在 checkpointer
- 外部通过 `Command(resume=值)` 恢复 → graph 从挂起点继续
- payload 可通过 `get_state()` 读取

**为什么这么选：**
1. 这是 LangGraph 的**官方 HITL 模式**（文档标准做法），比自建"确认队列"更可靠
2. interrupt 天然支持"挂起任意久 + 恢复继续"——SSE 场景正好需要（用户思考几秒甚至更久）
3. 面试能讲"用了 LangGraph 官方的 interrupt 机制实现 Human-in-the-loop"——标准答案

**类比：** 不自己发明"暂停键"，用框架官方自带的暂停/恢复机制。

---

### 步骤 2：实验验证——interrupt 在 messages 流模式下不产出任何 item

**在干什么：** 写最小实验脚本验证 interrupt 行为。**关键发现：** `stream_mode="messages"` 下 interrupt 不产出 item（流直接结束，无任何输出）。

**为什么这个发现决定架构：** 项目用 messages 模式做流式（token 逐字输出），如果以为"interrupt 会作为 item 出现"就会写错检测逻辑。正确方案：
1. 第一轮 `astream(..., stream_mode="messages")` 正常消费
2. **流结束后**用 `agent_graph.get_state(config)` 检测 `snap.tasks[0].interrupts` 是否非空
3. 有 interrupt → 发 `tool_request` 事件 → 等确认 → `astream(Command(resume=approved), ...)` 恢复

**类比：** 先看说明书（实验）再组装机器——不实验直接写，大概率写错检测方式。

---

### 步骤 3：checkpointer——interrupt 的前提条件

**在干什么：** graph 编译加 `MemorySaver()` checkpointer，每次请求用唯一 `thread_id`（`chat-{request_id}`）。

**为什么这么干：**
1. **interrupt/resume 依赖 thread 状态持久化**——没有 checkpointer，`get_state` 直接报错 "No checkpointer set"（实验 2 踩的坑）
2. **thread_id 每请求唯一**——MemorySaver 按 thread 存状态，复用 thread 会串状态（测试里差点踩：两个测试共用同一 request_id → 状态污染，全部改为唯一 id 后通过）

**类比：** interrupt 像"暂停录像"，checkpointer 是录像带（thread_id 是录像带编号）——没有录像带存不下暂停点，编号重复会串台。

---

### 步骤 4：ConfirmingToolNode——允许/拒绝/超时三分支

**在干什么：** 自定义工具节点替代 prebuilt `ToolNode`：

```python
def __call__(self, state):
    tool_calls = getattr(state["messages"][-1], "tool_calls", []) or []
    if not HITL_ENABLED or not tool_calls:
        return self._tool_node.invoke(state)          # 分支 1: 直通（默认行为不变）
    approved = interrupt({"tool_calls": [...]})        # 分支 2: 挂起等确认
    if approved:
        return self._tool_node.invoke(state)          # 允许 → 执行
    return {"messages": [ToolMessage("用户拒绝...")]}   # 拒绝 → 注入说明让 LLM 转述
```

**两个工程细节：**
1. **`HITL_ENABLED` 默认关闭**——环境变量开关，关闭时行为与旧版完全一致（现有测试零改动验证了这点）
2. **拒绝时不执行工具**，而是注入一条 `ToolMessage`（"工具调用被用户取消，请告知用户"）——**让 LLM 决定怎么措辞告知用户**，而不是后端硬编码回复（沿用短板④"错误让 LLM 决策"的设计哲学）
3. **踩坑：ToolNode 1.2.9 API 变化**——实例不可直接调用（`ToolNode(state)` 报 "not callable"），新版要用 `.invoke(state)`

**类比：** 门卫的三种放行逻辑：没装门禁（HITL 关）→ 直接进；装了门禁 → 老板同意（允许）才进；老板拒绝 → 让来客自己转述"老板不让进"。

---

### 步骤 5：run_agent_stream 确认循环——时序是核心

**在干什么：** run_agent_stream 重构为"消费一轮流 → 检测 interrupt → 发事件等确认 → 恢复继续"的循环，同时把流解析逻辑抽成 `_consume` 内部生成器。

**三个时序坑（本步骤的精华）：**

| 坑 | 现象 | 解法 |
|---|---|---|
| **确认注册在 yield 之后** | 前端收到 `tool_request` 事件时确认端点还找不到待确认请求（confirm 返回 False） | **先注册 asyncio.Future 再 yield 事件**——事件到达前端时 future 已就绪 |
| **interrupt 检测时机** | messages 模式不产出 item | 流结束后 `get_state` 检查 `tasks[0].interrupts` |
| **FakeLLM 产出完整 AIMessage** | 现有检测只认 `AIMessageChunk.tool_call_chunks`，完整消息带 `tool_calls` 被漏掉 | 检测兼容两种形态（`is_chunk ? tool_call_chunks : tool_calls`）——顺带修复了一个潜在盲区 |

**类比：** 客服热线的"请按 1 确认"——按键登记必须在播报语音**之前**完成（先注册再 yield），否则用户按了 1 没人接。

---

### 步骤 6：routes 端点 + 前端确认条

**在干什么：**
- 后端 `POST /api/hitl-confirm {request_id, approved}` → `confirm_tool_call()` 设置 future（未知 id 返回 404）
- 前端：ChatClient 透传 `tool_request` 事件 → useChat `confirmToolCall()` → ChatPanel 显示确认条（工具名 + 允许/拒绝按钮，样式走设计令牌）

**为什么这么干：** SSE 是单向流，确认必须走**独立端点**（HTTP 请求可以随时发，不受 SSE 挂起影响）。前端确认条是"对话过程中的一次确认"——不阻塞输入、点击即收起（乐观更新）、404 只 console.warn 不打扰用户。

**类比：** 电话通话中（SSE 流挂起），老板用对讲机（独立 HTTP 端点）回复"同意"——不需要挂断电话。

---

### 步骤 7：测试——5 个用例覆盖全部分支

**在干什么：** `test_hitl.py` 用真实编译的 graph + ScriptedLLM（第一轮返回工具调用、第二轮正常回复）：

| 测试 | 验证 |
|---|---|
| 允许 | `tool_request` 事件含 request_id/工具名/超时 → confirm(True) → **FakeTavily 真的被调用** → 回复继续 |
| 拒绝 | confirm(False) → 工具不执行 → LLM 转述取消 |
| 超时 | 不确认 → 1 秒后自动拒绝 → 工具不执行 → 流程继续 |
| 未知 id | confirm_tool_call("不存在") → False（端点 404） |
| HITL 关闭 | 无 tool_request 事件，工具直接执行（旧行为不变） |

**测试设计的关键：**
1. **用 `anext` 流式消费**——消费到 `tool_request` 事件后 generator 正挂起在确认等待，此时调 confirm 才是真实时序（一次性收集会等满超时，confirm 永远失败）
2. **每个测试独立 request_id**——MemorySaver 按 thread 存状态，复用会污染（实战踩坑）

**类比：** 测试像"彩排审批流"——每个用例是不同剧本（同意/拒绝/不回复/装不认识/没装门禁），都要演一遍。

---

## 3. 整个过程的思维模式（比代码更重要）

```
先实验后编码    （interrupt 行为、checkpointer 要求、ToolNode API——都是实验验证的）
  ↓
时序先行        （future 先注册再 yield; 流结束后才检测 interrupt）
  ↓
开关兜底        （HITL_ENABLED 默认关闭——新功能绝不改变旧行为）
  ↓
拒绝也优雅      （拒绝 → ToolMessage 让 LLM 转述, 不硬编码回复）
  ↓
测试还原时序    （anext 流式消费 + 唯一 thread_id——测试也要模拟真实时序）
```

这套打法通用：**任何"挂起-等待外部输入-恢复"的机制**（HITL、人工审批、二次确认）都是同一套：interrupt/挂起 → 事件通知 → 独立通道回复 → 恢复，且每一步都要先验证框架行为再写业务代码。

---

## 4. 概念词典（按出现顺序速查）

| 概念 | 一句话解释 | 类比 |
|---|---|---|
| **Human-in-the-loop** | 关键操作前插入人工确认环节 | 重要操作要老板拍板 |
| **interrupt()** | LangGraph 的挂起机制：节点里调用即暂停 graph 等恢复 | 暂停录像 |
| **checkpointer** | 持久化 graph 状态（含挂起点），resume 的前提 | 录像带 |
| **Command(resume=)** | 恢复被 interrupt 挂起的 graph，传入值回到 interrupt 调用处 | 按播放键 |
| **thread_id** | graph 状态的隔离键，每请求唯一 | 录像带编号 |
| **asyncio.Future** | 异步等待外部结果的容器（确认端点 set_result 唤醒） | 对讲机 |
| **anext()** | 手动消费 async generator 的下一项 | 一帧一帧看录像 |
| **乐观更新** | 点击后立即更新 UI，不等待后端响应 | 先斩后奏 |
| **工具副作用** | 工具执行产生的真实影响（读文件/发请求） | 打出去的电话收不回 |

---

## 5. 下一步（使用与演示）

1. **演示**：`.env` 加 `HITL_ENABLED=true` → 问"帮我搜索一下" → 确认条出现 → 允许/拒绝体验完整流程（超时 60s 默认拒绝）
2. **可扩展**：目前是所有工具都确认；后续可加"危险工具白名单"（只对 read_file 等确认），`ConfirmingToolNode` 的 payload 里按工具名过滤即可
3. **面试话术**："我用 LangGraph 的 interrupt 机制实现了 Human-in-the-loop——工具调用前 SSE 发确认事件，前端确认后 Command(resume) 恢复，超时默认拒绝；拒绝时注入 ToolMessage 让 LLM 自行转述"

---

## 附：本次实际改动的文件清单

| 文件 | 改动 | 作用 |
|---|---|---|
| `backend/config.py` | `HITL_ENABLED` / `HITL_CONFIRM_TIMEOUT` | 开关 + 超时配置 |
| `backend/agent/agent_graph.py` | `ConfirmingToolNode` + MemorySaver checkpointer + run_agent_stream 确认循环（先注册 future 再 yield）+ 工具检测兼容完整 AIMessage | HITL 核心 |
| `backend/routes.py` | `POST /api/hitl-confirm` | 确认端点 |
| `frontend/src/chat/ChatClient.ts` | `tool_request` 事件分发 | SSE 透传 |
| `frontend/src/hooks/useChat.ts` | `onToolRequest` + `confirmToolCall()` | 状态与确认请求 |
| `frontend/src/components/ChatPanel.tsx` | 确认条 UI（允许/拒绝） | 用户交互 |
| `frontend/src/style.css` | `.hitl-bar` / `.hitl-btn` 样式（设计令牌） | 视觉 |
| `backend/tests/unit/test_hitl.py` | 新建（5 个测试） | 允许/拒绝/超时/未知 id/关闭 |
| `backend/tests/unit/test_*.py` ×5 | FakeGraph.astream 加 config 参数 | 测试基建适配 |
| `docs/frontend/prototype-chatpanel.md` | 新建 | prototype-first 硬约束 |
| `CLAUDE.md` | HITL 状态更新 | 文档同步 |
