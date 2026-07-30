---
name: read-before-code
description: 编码前强制读取数据源、配置文件、官方文档/Sample。Use when writing code that depends on external data — model files, API responses, config schemas, SDK samples, third-party data formats.
---

# 先读后写

**原则**：写代码之前，先回答三个问题：
1. 我依赖的数据源在哪里？（模型文件 / API 响应 / 配置文件 / 官方 Sample）
2. 我确认过它的真实结构了吗？（不是臆测，是实际读出来的）
3. 我的假设和实际一致吗？

**核心信念**：代码中每出现一个"我以为……"的假设，就是藏了一个 bug。消除假设的方法只有一个——实际读取数据源。

## 步骤

1. **定位所有数据源**
   列出代码将要依赖的每一个外部数据：`.json` / `.yaml` / `.xml` / API 响应 schema / SDK Sample 代码 / 第三方库的类型定义。

2. **逐文件读取，提取关键结构**
   对每个数据源，用脚本或手动提取：
   - 字段名/参数名的真实拼写（不是文档里的描述，是实际键名）
   - 枚举值/索引的实际含义（不是猜测，是每一条都验证）
   - 默认值的真实数值（不是 0，是数据源里的初始值）
   - 可选/必选的实际情况

3. **对照检查**
   将提取出的结构与代码中的引用逐项对照。任何不一致的地方必须在写代码之前修正理解。

4. **写断言兜底**
   对可能变化的数据源，在代码中加运行时校验。

## 反模式

- **凭文档写代码** — 文档里写的参数名 ≠ 文件里的实际键名
- **猜想索引映射** — "exp_02 应该是 happy 吧" → 不读文件永远不知道
- **只看初始化不看每帧调用链** — SDK 的 `init()` 代码正常 ≠ 管线完整
- **"默认值应该是 0"** — 模型的默认值由设计师在数据文件中定义。眼睛中性值是 1.0 不是 0
- **用通用参数名假设模型** — "Live2D 嘴型参数应该叫 ParamMouthOpenY" → 实际叫 ParamA

## 实战案例

### 案例 1：Live2D 表情全部失效
- **假设**：模型使用 `ParamMouthOpenY`、`ParamAngleX` 等标准名
- **实际**：`mao_pro` 模型使用 `ParamA`、`ParamBrowLY`、`ParamEyeLOpen`
- **根因**：未读 `.exp3.json` 文件，凭文档编参数名
- **修复**：逐文件读取 8 个 `.exp3.json`，提取非零参数后重新映射

### 案例 2：模型重影
- **假设**：渲染管线只有 Expression 就够了
- **实际**：Cubism SDK 参数系统分层——Expression/Pose/Physics/EyeBlink/Breath/Motion
- **根因**：未对照官方 Sample 每帧 `update()` 调用链，漏掉了 `CubismUpdateScheduler.onLateUpdate()`
- **修复**：加载 Physics + Pose，注册 updater，在渲染循环中调用 scheduler

### 案例 3：表情索引全错
- **假设**：exp_05 = sad, exp_08 = angry
- **实际**：逐一验证后 exp_05 = angry, exp_08 = sad
- **根因**：表情索引映射凭空猜测
- **修复**：读每个 `.exp3.json` 非零参数判断实际视觉效果

## 适用场景

- 对接任何第三方 SDK（读官方 Sample 全部调用链）
- 解析外部数据格式（读真实样例文件而非文档）
- 调用新 API（用 curl 实际请求看响应结构）
- 读取配置文件（读实际 config 文件而非 example）
