---
name: verify
description: 提交前全量验证——本地跑一遍 CI 的所有步骤，全部通过才能声称"没问题"。Use before git push, after making changes, or when claiming something "should work".
---

# 提交前验证

**原则**：说"没问题了"之前，先跑一遍。不是"应该能过"，是"实际跑过了"。

**核心信念**：你本地没跑过的命令，CI 也不会帮你跑过。

## 步骤

### 1. 逐条对照 CI 命令

打开 `.github/workflows/ci-cd.yml`，把每个 `run:` 后面的命令复制出来，在本地逐条执行——不要用"等价的"命令，要用完全一样的命令。

```
后端:
  ruff check backend/
  mypy backend/ --ignore-missing-imports --explicit-package-bases
  python -m pytest backend/tests/ -q --asyncio-mode=auto     ← 注意是 python -m pytest 不是 pytest

前端:
  cd frontend && npm run lint
```

### 2. 每步必须有输出

不是"没报错 = 过了"，是"明确打印了 PASS/Success/0 errors"。如果有 warning，确认 CI 会不会因此阻断。

### 3. 全部通过才算过

有一步失败 → 修 → 重跑全部（不是只重跑修过的那步）。因为修 A 可能破坏了 B。

### 4. 确认无误后提交

```bash
./scripts/verify.sh  # 跑全量验证
git push             # 全部通过后再推
```

## 反模式

- **"本地跑过了"但实际上跑的命令不一样** — `pytest` vs `python -m pytest` 在 Windows 上结果可能不同
- **"后端全过了，前端应该也没问题"** — CI 不区分前后端，前端 lint 挂了整个 job 就挂
- **"这个改动太小了，不用跑全量"** — 你改了一行 ESLint 配置，可能影响 50 个文件
- **跳过步骤直接在 CI 里调试** — 本地 5 秒能发现的问题，推到 CI 要等 2 分钟
- **sed/批量替换后不验证** — 命令可能删错行、破坏缩进、漏掉第二个匹配

## 快速命令

如果你有 `scripts/verify.sh`，一条命令跑完全量：

```bash
./scripts/verify.sh
```
