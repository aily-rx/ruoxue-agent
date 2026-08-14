# ChatPanel — HITL 工具确认条 ASCII 原型

> 版本: v1.0 | 日期: 2026-08-14 | 对应: Human-in-the-loop 工具调用人工确认
> 前置条件: 后端 `HITL_ENABLED=true`（否则后端不会发 `tool_request` 事件，本 UI 不出现）

---

## 一、组件树（仅展示本次新增/改动部分）

```
<footer .input-bar>                    <- 输入栏 (flex column 化: 确认条 + 原控件行)
├── <div .hitl-bar>                    <- [新增] 工具确认条 (pendingTool != null 时显示)
│   ├── <span>🤖 若雪想调用工具：search_web，是否允许？</span>
│   ├── <button .hitl-btn.allow>允许</button>
│   └── <button .hitl-btn.deny>拒绝</button>
└── (原有 VoiceButton / 上传 / textarea / 发送 一行)
```

数据流:
```
后端 SSE 事件 tool_request {request_id, tool_calls:[{name}], timeout_s}
  → ChatClient.dispatch → useChat.onToolRequest → ChatPanel.setState(pendingTool)
  → 用户点 [允许/拒绝] → confirmToolCall(request_id, approved)
  → POST /api/hitl-confirm → 后端 Command(resume=approved) 恢复被 interrupt 挂起的 graph
  → SSE 流继续 → token 正常输出
```

---

## 二、确认条出现（HITL 开启 + Agent 决定调用工具）

```
┌──────────────────────────────────────────────────────────────┐
│  💬 [AI] 让我先查一下资料...                                    │
├──────────────────────────────────────────────────────────────┤
│  🤖 若雪想调用工具：search_web，是否允许？  [允许] [拒绝]        │  ← hitl-bar
│  [🎤] [📎] [输入你想问的...                    ] [发送]         │  ← 原输入栏
└──────────────────────────────────────────────────────────────┘
```

---

## 三、状态与行为

| 状态 | 触发 | 行为 |
|---|---|---|
| 显示确认条 | 收到 `tool_request` 事件 | 显示工具名列表；SSE 流在后端挂起等待 |
| 点 [允许] | 用户同意 | POST `{request_id, approved:true}` → 工具执行 → 流继续 |
| 点 [拒绝] | 用户不同意 | POST `{request_id, approved:false}` → 工具不执行 → LLM 转述取消 |
| 超时（60s 未操作） | 后端超时 | 默认拒绝，确认条自动消失（下一次事件流继续） |
| HITL 关闭 | 后端不发事件 | 确认条永不出现（与旧行为一致） |

---

## 四、边界与交互细节

1. **确认条出现在输入栏内部顶部**（不是独立层）——不遮挡消息区，且与输入控件同容器，视觉上属于"对话过程中的一次确认"
2. 确认期间**不阻塞输入**：用户仍可打字/发送下一条（后端对旧请求的确认仍有效）
3. 点击后立即收起确认条（乐观更新）——后端确认失败（404）只 console.warn，不打扰用户
4. 设计令牌：颜色/圆角全部走 `:root` CSS 变量（`--primary`/`--surface-alt`/`--radius`），无硬编码
