#!/usr/bin/env bash
# prototype-first 硬约束：
# 检查新增/修改的前端组件是否有对应原型文档

cd "$(dirname "$0")/.."
NEW_COMPONENTS=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null | grep "frontend/src/components/.*\.tsx$" || true)
[ -z "$NEW_COMPONENTS" ] && NEW_COMPONENTS=$(git diff --name-only 2>/dev/null | grep "frontend/src/components/.*\.tsx$" || true)

if [ -z "$NEW_COMPONENTS" ]; then
    echo "prototype-first: 无组件变更，跳过 ✓"
    exit 0
fi

HAS_DOCS=true
for comp in $NEW_COMPONENTS; do
    comp_name=$(basename "$comp" .tsx)
    doc_path="docs/frontend/prototype-${comp_name,,}.md"
    if [ ! -f "$doc_path" ]; then
        # 也检查 experience 目录
        doc_path="docs/frontend/experience/${comp_name,,}.md"
        if [ ! -f "$doc_path" ]; then
            echo "✗ prototype-first: 组件 $comp_name 缺少原型文档"
            HAS_DOCS=false
        fi
    fi
done

if [ "$HAS_DOCS" = false ]; then
    echo "  请为每个新组件创建 docs/frontend/prototype-<组件名>.md"
    exit 1
fi
echo "prototype-first: 组件文档齐全 ✓"
