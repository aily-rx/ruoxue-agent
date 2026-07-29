# Ruoxue — 前后端开发流程规范

> 总结自 Lira Avtart 数字人项目开发经验 | 日期: 2026-07-24

---

## 核心原则

> 需求文档 -> 原型设计 -> 架构设计 -> 编码实现。**前三步没对齐之前不写代码。**

Lira 项目的教训：跳过原型设计直接编码，返工时间翻倍。

```
时间分配建议：
  需求对齐 + PRD      20%
  原型 + 架构设计      30%   <- 最容易被跳过，但最重要
  编码实现            40%
  联调修正            10%

如果跳过前两步：
  编码实现            60%
  反复修改 + 返工      25%   <- 翻倍
```

---

## 一、正式开发前的检查清单

每个 Phase 启动前，逐项确认：

```
□ 需求 PRD 已写好并确认（docs/backend/prd-xxx.md）
□ 该 Phase 涉及的技术栈已选定（参考 docs/AI_Agent_数字人助手技术栈学习笔记.md）
□ 项目目录结构已更新（docs/project-structure.md）
□ 后端 API 接口已定义（docs/backend/api.md）
□ 前端原型/布局已画好（如果是新页面）
□ 依赖清单已列出（requirements.txt / package.json）
□ 前后端数据协议已对齐（SSE 事件格式、JSON schema）
```

---

## 二、后端开发流程

### 2.1 Phase 启动

```
1. 写 PRD
   确定要做什么功能、输入输出、验收标准
   输出: docs/backend/prd-xxx.md

2. 定义 API
   确定接口路径、请求格式、响应格式、错误码
   输出: 更新 docs/backend/api.md

3. 设计模块
   确定需要哪些 .py 文件、类/函数签名、模块间依赖
   输出: 更新 docs/backend/architecture.md 中的模块表
```

### 2.2 编码阶段

按**依赖方向从下往上**写，保证每个模块写完就能测：

```
正确顺序（以 Phase 1 为例）:
  1. config.py             配置（无依赖）
  2. agent/emotional_agent.py   Agent 核心（依赖 LLM API）
  3. agent/memory.py            记忆管理（依赖 emotional_agent）
  4. routes.py                  路由（依赖上面所有模块）
  5. main.py                    入口（依赖 routes）

错误顺序:
  先写 main.py -> 发现缺 routes -> 写 routes -> 发现缺 agent -> ...
```

### 2.3 自测

每个模块写完，先在本地自测再进入联调：

```bash
# 测试 LLM 调用
python -c "from agent.emotional_agent import generate_reply; ..."

# 测试 API 接口
curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"text":"你好"}'

# 测试 SSE 流
curl -N http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"text":"你好"}'
```

---

## 三、前端开发流程

### 3.1 Phase 启动

```
1. 画原型
   确定页面布局、组件层级、交互状态
   输出: docs/frontend/prototype-xxx.md（ASCII 布局图 + 组件树）

2. 定协议
   和后台对齐 SSE 事件格式、HTTP 请求格式
   输出: 更新 docs/backend/api.md 中的前端接收示例

3. 拆组件
   确定 React 组件树、每个组件的 props/state
   输出: 组件树图（ASCII 即可）
```

### 3.2 原型设计要点（来自 Lira 经验）

**每个页面状态画一张图：**

```
必须覆盖的状态:
  ✅ 默认状态      用户第一眼看到的样子
  ✅ 加载状态      等待数据时的过渡
  ✅ 空状态        无数据时的占位
  ✅ 错误状态      网络异常/服务不可用
  ✅ 展开状态      面板/弹窗打开时
  ✅ 移动端状态    响应式布局变化（<768px）
```

**标注规范：**

```
标注内容:
  L1 结构: 组件名、DOM id、CSS class
  L2 尺寸: px、vh、%、calc()
  L3 交互: 点击/拖拽/键盘快捷键、动画方向

示例:
┌──────────────────────────────────────┐
│ ChatPanel                    [麦克风] │ <- Header (56px)
├──────────────────────────────────────┤
│                                      │
│  [AI 气泡]  你好！今天我能帮你什么？   │
│                                      │
│              你好，我想问个问题 [用户] │ <- 消息区 (flex:1, overflow-y:auto)
│                                      │
├──────────────────────────────────────┤
│ [输入框___________________] [发送]   │ <- InputBar (60px)
└──────────────────────────────────────┘
```

### 3.3 编码阶段

按**组件树从外到内**写：

```
正确顺序（以 Phase 1 为例）:
  1. App.tsx                   根布局（CSS Grid / Flexbox）
  2. components/ChatPanel.tsx  聊天面板容器
  3. components/ChatBubble.tsx 单条消息气泡
  4. chat/ChatClient.ts        SSE 连接管理
  5. hooks/useChat.ts          状态管理 Hook

错误顺序:
  先写 ChatBubble -> 不知道 props 怎么传 -> 改 props -> ...
```

### 3.4 自测

```bash
# 启动前端
cd frontend && npm run dev

# 检查项:
□ 页面能正常渲染
□ 发送消息 -> 输入框清空 -> 消息出现在气泡
□ AI 回复流式逐字显示
□ 联网断开 -> 有错误提示
□ 移动端 (<768px) 布局正常
```

---

## 四、联调流程

```
1. 后端先自测通过（curl 验证 API 正常）
2. 后端先跑起来（python main.py）
3. 前端连后端（配置 API base URL）
4. 前端发消息 -> 检查 SSE 流是否正常
5. 有问题 -> 看浏览器 DevTools Network 面板 + 后端日志
```

**联调检查项：**

```
□ SSE 连接建立成功（Network 面板看到 event stream）
□ emotion 事件 -> 正确解析
□ token 事件 -> 逐字显示
□ audio 事件 -> 音频播放（Phase 2+)
□ viseme 事件 -> 口型同步（Phase 3+)
□ done 事件 -> 光标移除、状态重置
□ 网络中断 -> 前端有提示、不崩溃
□ 快速连发多条 -> 队列正确处理
```

---

## 五、每个 Phase 的开发顺序（总览）

```
Phase 1 文字聊天:
  1. 后端: config -> emotional_agent -> memory -> routes -> main
  2. 前端: App -> ChatPanel -> ChatBubble -> ChatClient -> useChat
  3. 联调

Phase 2 语音:
  1. 后端: asr_service -> tts_service -> 更新 routes (新增 /api/asr)
  2. 前端: MicRecorder -> AudioManager -> ASRClient -> VoiceButton -> useVoice
  3. 联调

Phase 3 数字人:
  1. 后端: g2p_service -> viseme_mapper -> 更新 routes (新增 emotion/viseme 事件)
  2. 前端: CubismManager -> EmotionDriver -> LipSyncDriver -> Live2DCanvas
  3. 联调

Phase 4 Agent:
  1. 后端: tools -> graph -> memory(Chroma升级) -> 更新 routes
  2. 前端: ToolCallBubble -> MemoryPanel
  3. 联调
```

---

## 六、文档同步机制

参考 `Agent.md` 的规范，以下情况需同步经验文档：

```
触发条件:
  1. 大功能完成（如 Phase 1 的 SSE 流式对话联调通过）
  2. 重要 Bug 修复（>30min 或暴露系统性设计问题）
  3. 关键技术决策（如"为什么选 SenseVoice 而不是 Whisper"）
  4. 性能优化（如 TTS 缓存方案）

同步动作:
  1. 按 _TEMPLATE.md 模板写经验文档
  2. 放到 docs/frontend/experience/ 或 docs/backend/experience/
  3. 更新 Agent.md 的索引表
  4. 关联文档加交叉引用
```

---

## 七、Git 提交规范

```
feat: 新功能       feat: add SSE chat endpoint
fix: 修 bug        fix: emotion event not firing on first message
docs: 文档更新     docs: update API spec for viseme format
refactor: 重构     refactor: extract AudioManager from ChatClient
test: 测试相关     test: add unit test for viseme_mapper
chore: 工程配置    chore: add ruff config
```

---

*最后更新: 2026-07-24*
