#!/usr/bin/env bash
# tdd 硬约束：只检查本次提交中新增的源文件是否有对应测试

cd "$(dirname "$0")/.."

# 只检查首次添加的文件（A），不检查已有文件的白空格修改（M）
CHANGED=$(git diff --cached --name-only --diff-filter=A 2>/dev/null || true)
SRC_FILES=$(echo "$CHANGED" | grep -E "backend/(agent|tts|asr)/.*\.py$" | grep -v "__init__\|test_\|conftest" || true)

if [ -z "$SRC_FILES" ]; then
    echo "tdd: 无新增源文件，跳过"
    exit 0
fi

MISSING=false
for src in $SRC_FILES; do
    src_name=$(basename "$src" .py)
    src_dir=$(dirname "$src")
    test_file="${src_dir}/tests/test_${src_name}.py"
    test_file2="${src_dir}/../../tests/unit/${src_dir##*/}/test_${src_name}.py"

    if [ ! -f "$test_file" ] && [ ! -f "$test_file2" ]; then
        echo "  ${src} -> 缺少测试文件"
        MISSING=true
    fi
done

if [ "$MISSING" = true ]; then
    echo "✗ tdd: 新增文件必须包含对应测试"
    exit 1
fi
echo "tdd: 测试覆盖齐全"
