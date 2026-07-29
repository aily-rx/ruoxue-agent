#!/usr/bin/env bash
# tdd 硬约束：
# 检查非测试目录的源码变更是否有对应测试文件

cd "$(dirname "$0")/.."
CHANGED=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null || git diff --name-only 2>/dev/null)
SRC_FILES=$(echo "$CHANGED" | grep -E "backend/(agent|tts|asr)/.*\.py$" | grep -v "__init__\|test_\|conftest" || true)

if [ -z "$SRC_FILES" ]; then
    echo "tdd: 无源码变更，跳过 ✓"
    exit 0
fi

MISSING_TESTS=false
for src in $SRC_FILES; do
    src_dir=$(dirname "$src")
    src_name=$(basename "$src" .py)
    test_dir=$(echo "$src_dir" | sed 's/backend/backend\/tests\/unit/')
    test_file="$test_dir/test_${src_name}.py"
    
    if [ ! -f "$test_file" ]; then
        # 也检查 integration tests 目录
        test_dir2=$(echo "$src_dir" | sed 's/backend/backend\/tests\/integration/')
        test_file2="$test_dir2/test_${src_name}.py"
        if [ ! -f "$test_file2" ]; then
            echo "  $src 缺少测试文件: $test_file"
            MISSING_TESTS=true
        fi
    fi
done

if [ "$MISSING_TESTS" = true ]; then
    echo "✗ tdd: 以上文件缺少对应测试"
    exit 1
fi
echo "tdd: 测试覆盖齐全 ✓"
