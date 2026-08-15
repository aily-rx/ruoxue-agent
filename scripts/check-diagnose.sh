#!/usr/bin/env bash
# diagnose-bugs 硬约束：
# 检查 commit message 中 fix 类型是否包含根因关键词

cd "$(dirname "$0")/.."
# commit-msg 阶段: $1 是本次提交信息文件（pre-commit 阶段读不到新信息,
# git log -1 是上一条提交, 会误判）; 手动运行/无参数时回退到 git log -1
if [ -n "${1:-}" ] && [ -f "$1" ]; then
    MSG=$(cat "$1")
else
    MSG=$(git log -1 --pretty=%B 2>/dev/null)
fi

if echo "$MSG" | grep -qi "^fix:"; then
    if ! echo "$MSG" | grep -qi "根因\|root cause\|因为\|修复\|原因\|导致"; then
        echo "✗ diagnose-bugs: fix commit 缺少根因描述"
        echo "  请在 commit message 中说明 bug 根因"
        exit 1
    fi
fi
echo "diagnose-bugs: commit 信息完整 ✓"
