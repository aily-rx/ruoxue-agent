---
name: verify
description: 提交前全量验证——本地跑一遍 CI 所有步骤，全部通过才能声称没问题。Use before git push, after changes, or when claiming "should work"/"没问题了"/"ALL PASSED".
---

# 提交前验证

**原则**：说"没问题了"之前，先跑一遍。不是"应该能过"，是"实际跑过了"。

**核心信念**：你本地没跑过的命令，CI 也不会帮你跑过。

## 步骤

### 1. 找到当前项目的 CI 配置

项目可能用不同的 CI 系统，按优先级查找：

1. `.github/workflows/` — GitHub Actions，找 `ci*.yml`
2. `.gitlab-ci.yml` — GitLab CI
3. `Makefile` — 如果有 `test`/`lint` 目标
4. `package.json` — 如果有 `scripts.test`/`scripts.lint`

### 2. 提取所有验证命令

从 CI 配置中提取每个 `run:` 后面的命令。不要用"等价的"命令，要用完全一样的。

### 3. 逐条执行并记录结果

每条命令执行完后明确报告 PASS/FAIL。如果有 warning，确认 CI 会不会因 warning 阻断。

### 4. 全部通过才算过

有一步失败 → 修 → 重跑全部（不是只重跑修过的那步）。修 A 可能破坏 B。

## 反模式

- **"本地跑过了"但命令不一样** — `pytest` vs `python -m pytest` 结果可能不同
- **"后端全过了，前端应该也没问题"** — CI 不区分前后端，前端挂了整个 job 挂
- **"改动太小，不用跑全量"** — 改一行 ESLint 配置可能影响 50 个文件
- **跳过本地直接在 CI 里调试** — 本地 5 秒能发现的，推到 CI 等 2 分钟
- **批量替换后不验证** — sed 可能删错行、破坏缩进、漏掉匹配

## 适用场景

本项目、React 项目、Python 项目、任何有 CI 配置的项目——skill 本身不绑定具体命令，到哪都能用。
