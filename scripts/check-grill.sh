#!/usr/bin/env bash
# grill-me 硬约束：
# 检查新增的 spec/PRD 文档是否覆盖了数据/状态/边界/时序/依赖 5 个维度

cd "$(dirname "$0")/.."
NEW_SPECS=$(git diff --cached --name-only --diff-filter=A 2>/dev/null | grep -E "prd-|spec-|prototype-" || true)

if [ -z "$NEW_SPECS" ]; then
    echo "grill-me: 无新增 spec，跳过 ✓"
    exit 0
fi

for spec in $NEW_SPECS; do
    [ ! -f "$spec" ] && continue
    content=$(cat "$spec")
    DIMS=0
    echo "$content" | grep -qi "数据\|schema\|字段\|data" && DIMS=$((DIMS+1))
    echo "$content" | grep -qi "状态\|state\|加载\|错误\|空" && DIMS=$((DIMS+1))
    echo "$content" | grep -qi "边界\|最大\|最小\|并发\|权限" && DIMS=$((DIMS+1))
    echo "$content" | grep -qi "时序\|异步\|顺序\|等待\|回调" && DIMS=$((DIMS+1))
    echo "$content" | grep -qi "依赖\|depend\|服务\|SDK\|API" && DIMS=$((DIMS+1))
    
    if [ "$DIMS" -lt 5 ]; then
        echo "✗ grill-me: $spec 只覆盖了 $DIMS/5 个维度（数据/状态/边界/时序/依赖）"
        exit 1
    fi
    echo "  $spec: $DIMS/5 维度 ✓"
done
echo "grill-me: spec 覆盖完整 ✓"
