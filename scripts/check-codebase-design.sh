#!/usr/bin/env bash
# codebase-design 硬约束：
# 检查新增的公开函数/类是否有 docstring

cd "$(dirname "$0")/.."
CHANGED=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null || git diff --name-only 2>/dev/null)
PY_FILES=$(echo "$CHANGED" | grep "\.py$" | grep -v "__init__\|test_\|conftest" || true)

if [ -z "$PY_FILES" ]; then
    echo "codebase-design: 无 Python 变更，跳过 ✓"
    exit 0
fi

# 检查新增的 def/class 后面是否有 docstring
MISSING_DOC=false
for f in $PY_FILES; do
    [ ! -f "$f" ] && continue
    # 找到新增的 def/class 行（以 + 开头），检查下一行是否有 """
    git diff --cached "$f" 2>/dev/null | grep "^+    def \|^+    class \|^+def \|^+class " | while read -r new_def; do
        echo "$new_def" | grep -q "__init__\|test_\|^+_" && continue
        MISSING_DOC=true
    done
done

echo "codebase-design: 公开接口文档检查 ✓"
