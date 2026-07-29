#!/usr/bin/env bash
# ============================================================
# 全量 CI 验证脚本 — 与 .github/workflows/ci-cd.yml 完全一致
# 每次声称"没问题了"之前必须先跑，全部 PASS 才能提交
# ============================================================
cd "$(dirname "$0")/.."

PASS=0
FAIL=0

check() {
    local name="$1"
    shift
    echo "--- $name ---"
    if "$@" > /tmp/verify_out.txt 2>&1; then
        tail -3 /tmp/verify_out.txt
        echo "  ✓ PASS"
        PASS=$((PASS + 1))
    else
        tail -5 /tmp/verify_out.txt
        echo "  ✗ FAIL"
        FAIL=$((FAIL + 1))
    fi
    echo ""
}

echo "============================="
echo " Ruoxue CI 全量验证"
echo "============================="
echo ""

# ---- 后端 ----
check "ruff"        ruff check backend/
check "mypy"        mypy backend/ --ignore-missing-imports --explicit-package-bases
check "pytest"      python -m pytest backend/tests/ -q --asyncio-mode=auto

# ---- 前端 ----
check "eslint"      bash -c "cd frontend && npm run lint"

# ---- 结果 ----
echo "============================="
echo " PASS: $PASS  FAIL: $FAIL"
echo "============================="

if [ "$FAIL" -gt 0 ]; then
    echo "✗ 有失败项，禁止提交。"
    exit 1
else
    echo "✓ 全部通过，可以提交。"
fi
