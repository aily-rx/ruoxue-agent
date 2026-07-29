---
name: verify
description: 提交前全量验证——本地跑一遍 CI 所有步骤，全部通过才能声称没问题。Use before git push, after changes, or when claiming "should work"/"没问题了"/"ALL PASSED".
---

# 提交前验证

**原则**：说"没问题了"之前，先跑一遍。不是"应该能过"，是"实际跑过了"。

**核心信念**：你本地没跑过的命令，CI 也不会帮你跑过。

## 步骤

### 1. 第一次使用：初始化验证环境

到这个新项目的第一件事——生成验证脚本和 git hook：

```bash
# 创建 scripts/verify.sh
# 内容：从项目 CI 配置中提取所有 run: 命令，逐条执行并报告 PASS/FAIL
# 示例模板见下方"脚本模板"

# 安装 git pre-push hook（硬拦截，不过不给推）
cat > .git/hooks/pre-push << 'HOOK'
#!/usr/bin/env bash
cd "$(git rev-parse --show-toplevel)"
bash scripts/verify.sh
HOOK
chmod +x .git/hooks/pre-push
```

### 2. 日常使用：提交前自动验证

每次 `git push` 时 hook 自动触发，不需要手动记得跑。

### 3. 如果项目还没有 CI 配置

先帮用户建立最基础的 CI（ruff/mypy/pytest 或 eslint/vitest），然后再生成 verify.sh。

## 验证脚本模板

根据项目技术栈自动生成，核心逻辑：逐条执行 CI 命令 → 报告结果 → 有失败就 exit 1。

```bash
#!/usr/bin/env bash
cd "$(dirname "$0")/.."
PASS=0; FAIL=0
check() { echo "--- $1 ---"; if "${@:2}" > /tmp/out 2>&1; then tail -3 /tmp/out; echo "  ✓ PASS"; PASS=$((PASS+1)); else tail -5 /tmp/out; echo "  ✗ FAIL"; FAIL=$((FAIL+1)); fi; echo; }

# 以下命令从 CI 配置自动提取，不是手写的——包括 lint/test/构建
check "ruff"           ruff check .
check "pytest"         python -m pytest tests/ -q
check "docker-backend" docker build -q -f backend/Dockerfile backend/

echo "PASS: $PASS  FAIL: $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
```

## 执行

现在就开始——声明"没问题了"/"要提交"/"准备 push"之前：

1. 如果项目还没有 `scripts/verify.sh` → 先生成它
2. 跑一遍验证
3. 全部通过才能继续

## 反模式

- **"本地跑过了"但命令不一样** — `pytest` vs `python -m pytest` 结果可能不同
- **"后端全过了，前端应该也没问题"** — CI 不区分前后端，前端挂了整个 job 挂
- **"改动太小，不用跑全量"** — 改一行 ESLint 配置可能影响 50 个文件
- **跳过本地直接在 CI 里调试** — 本地 5 秒能发现的，推到 CI 等 2 分钟
- **批量替换后不验证** — sed 可能删错行、破坏缩进、漏掉匹配
- **只跑 lint/test 不跑 docker build** — 改了 Dockerfile 或依赖版本，lint 全过但构建时 FROM 镜像版本不兼容，到 CI 才暴露

## 适用场景

本项目、React 项目、Python 项目、任何有 CI 配置的项目——skill 本身不绑定具体命令，到哪都能用。
