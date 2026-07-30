---
name: implement
description: 按 spec 或设计实现功能。Use when the user wants to build a feature from a spec, PRD, or tickets, or says "开始实现"/"写代码"/"按这个方案做".
---

# 实现

## 原则

**按依赖方向从下往上写**。保证每个模块写完就能独立测试。

## 步骤

### 1. 确认前置条件

在写第一行代码之前确认：
- [ ] Spec/PRD/原型已对齐（需求明确）
- [ ] 数据协议已定义（前后端接口已定）
- [ ] 依赖清单已列出（需要哪些包/库）
- [ ] 数据源已验证（如有外部依赖，已按 `read-before-code` 确认）

### 2. 确定编码顺序

按**依赖方向从下往上**排列模块，保证写完一个就能测一个：

```
正确顺序:
  1. config.py             配置（无依赖）               ← 写完就能 import 验证
  2. service_layer.py      核心服务（依赖 config）      ← 写完就能调方法验证
  3. routes.py             路由（依赖 service）         ← 写完就能 curl 验证
  4. main.py               入口（依赖 routes）          ← 写完就能启动验证

错误顺序:
  先写 main.py → 发现缺 routes → 写 routes → 发现缺 service → ...
```

### 3. 逐模块编码 + 自测

每个模块写完立即自测，不要等所有模块写完再一起测：

```
后端自测:
  curl -X POST http://localhost:8000/api/xxx -d '{"test":"data"}'

前端自测:
  npm run dev → 页面渲染 → 发消息 → 检查流式显示 → 检查错误状态
```

### 4. 集成

- 后端先自测通过，再联调前端
- 前端连后端，逐条 SSE 事件验证
- 有问题 → 看 Network 面板 + 后端日志

### 5. 提交

- 跑完整测试套件
- 用 `/code-review` 审查 diff
- Git commit（遵循 `feat:/fix:/docs:/refactor:` 规范）

## 关键检查项

- [ ] 过滤管道已加（LLM 输出 → TTS 等下游消费前做了清洗？）
- [ ] 错误状态有 UI 提示（网络断开？服务不可用？）
- [ ] 快速连发多条消息不崩溃（队列正确处理？）
- [ ] 移动端布局正常（<768px？）

## 反模式

- **先写顶层后写底层** — 形成死循环依赖，每个模块都在等另一个模块
- **全部写完再一起测** — 10 个模块的 bug 混在一起，定位成本是逐个测的 10 倍
- **后端没自测就联调前端** — 联调时 80% 的问题出在后端没自测
- **不跑 typecheck 就提交** — 静态检查是最便宜的 bug 发现方式

## 实战经验

### 按依赖顺序的价值

在一个 4 Phase 的项目中，正确的编码顺序（config → service → routes → main）让每个模块都能在写完 5 分钟内验证。反向顺序则需要反复补写缺失的依赖。

### 模块自测的最佳实践

```bash
# 测试 LLM 调用
python -c "from agent.emotional_agent import generate_reply; print(generate_reply('你好'))"

# 测试 API 接口
curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"text":"你好"}'

# 测试 SSE 流
curl -N -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"text":"你好"}'
```
