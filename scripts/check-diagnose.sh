#!/usr/bin/env bash
# diagnose-bugs 硬约束：
# 检查 commit message 中 fix 类型是否包含根因关键词

cd "$(dirname "$0")/.."
MSG=$(git log -1 --pretty=%B 2>/dev/null)

if echo "$MSG" | grep -qi "^fix:"; then
    if ! echo "$MSG" | grep -qi "根因\|root cause\|因为\|修复\|原因\|导致"; then
        echo "✗ diagnose-bugs: fix commit 缺少根因描述"
        echo "  请在 commit message 中说明 bug 根因"
        exit 1
    fi
fi
echo "diagnose-bugs: commit 信息完整 ✓"
