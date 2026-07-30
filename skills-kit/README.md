# DeepSeek Skills — AI 编程技能库

> 一套适用于 DeepSeek（及任何 OpenAI 兼容 LLM）的编程技能库。
> 技能内容源自真实工程项目实践，通用、可移植、零框架锁定。

## 设计理念

- **通用优先** — 每个 SKILL.md 是纯提示词文本，不绑定任何具体项目或框架
- **薄适配层** — `skill_loader.py` 只有 ~150 行，零外部依赖（PyYAML 可选）
- **即拷即用** — 把 `skills/` 目录和 `skill_loader.py` 拷到任何项目，3 行代码接入

## 快速开始

```python
from skill_loader import SkillLoader

loader = SkillLoader("./skills")

# 1. 根据用户输入匹配技能
name = loader.match("帮我写个登录功能的测试")
# → "tdd"

# 2. 加载技能内容
prompt = loader.load("tdd")

# 3. 注入到 DeepSeek 的 system prompt
response = deepseek_client.chat(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": base_prompt + "\n\n" + prompt},
        {"role": "user", "content": user_input}
    ]
)
```

## 技能列表

### Engineering（工程类）

| 技能 | 说明 | 来源 |
|------|------|------|
| **read-before-code** | 编码前先读数据源/配置/Sample | 实战原创 |
| **prototype-first** | 原型先行，覆盖 6 种页面状态 | 实战原创 |
| **defensive-output** | LLM 输出三层过滤，不信任下游 | 实战原创 |
| **diagnose-bugs** | 结构化 bug 诊断 + 竞态防御 | 增强版 |
| **implement** | 按依赖方向从下往上实现 + 自测 | 增强版 |
| **code-review** | 双轴审查 + 7 个反模式清单 | 增强版 |
| **tdd** | 测试驱动开发 red-green-refactor | 移植版 |
| **codebase-design** | 深模块设计，接口与实现分离 | 移植版 |

### Productivity（效率类）

| 技能 | 说明 |
|------|------|
| **grill-me** | 方案追问：5 个维度帮你想透方案 |
| **handoff** | 会话交接：压缩当前对话为可移交文档 |

## 如何添加新技能

1. 在 `skills/engineering/` 或 `skills/productivity/` 下创建目录
2. 写 `SKILL.md`（YAML frontmatter + markdown 内容）
3. 写 `deepseek.yaml`（触发关键词 + 元数据）
4. 更新对应 bucket 的 `README.md`
5. 加载器自动发现，无需修改 `skill_loader.py`

```yaml
# deepseek.yaml 格式
name: my-skill
display_name: "我的技能"
type: model-invoked        # model-invoked | user-invoked
trigger_keywords:
  - "触发词1"
  - "触发词2"
tools_required: []
priority: 5
```

## 在 LangGraph 中集成

```python
# 在 agent_graph.py 中新增 Layer 4: skill_context
from skill_loader import SkillLoader

loader = SkillLoader("./skills")

async def run_agent_stream(user_text, history):
    # Layer 4: 动态技能上下文
    skill_name = loader.match(user_text)
    skill_context = loader.load(skill_name) if skill_name else ""

    # 拼接到现有三层 prompt 之后
    parts = [system_prompt, runtime_context, memory_context]
    if skill_context:
        parts.append(skill_context)
    system_text = "\n\n".join(parts)
    # ... 其余逻辑不变
```

## 设计参考

本项目受了 [Matt Pocock Skills](https://github.com/mattpocock/skills) 的启发，借鉴了其结构设计、invocation 模型和 `writing-great-skills` 中的方法论。

差异：本项目的技能面向 DeepSeek API（OpenAI 兼容格式），通过 prompt 注入而非 Claude Code 插件系统工作。

## License

MIT
