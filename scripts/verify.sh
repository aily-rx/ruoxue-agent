#!/usr/bin/env bash
# ============================================================
# 全量 CI 验证脚本 — 与 .github/workflows/ci-cd.yml 对齐
# 每次声称"没问题了"之前必须先跑，全部 PASS 才能提交
#
# 用法:
#   bash scripts/verify.sh              # 默认: 自动检测 RAG 改动决定是否含 eval
#   bash scripts/verify.sh --with-eval  # 强制包含 eval 深度评估（30+ 分钟, 真调 API）
# ============================================================
cd "$(dirname "$0")/.."

WITH_EVAL=0
[ "${1:-}" = "--with-eval" ] && WITH_EVAL=1

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
# --exclude .*venv.*: 与 CI 一致（本地 backend/venv 是运行时产物，mypy 扫描会误报第三方文件）
check "mypy"        mypy backend/ --ignore-missing-imports --explicit-package-bases --exclude ".*venv.*"

# ---- pytest: RAG 链路改动才含 eval 深度评估 ----
# eval（backend/tests/eval/）依赖真实 faiss_data/ + DEEPSEEK_API_KEY，本地跑 30+ 分钟。
# 未改 RAG 链路时只跑 unit+integration 快速体检——与 CI 实际执行一致
# （CI 上 eval 因无知识库/无 Key 自动跳过，等价于只跑 unit+integration）。
# 改 RAG 代码后手动深检: python -m pytest backend/tests/eval/ -v
RAG_PATTERNS='backend/agent/rag_service\.py|backend/agent/reranker\.py|backend/tests/eval/|text/rag/'
CHANGED="$(git diff HEAD --name-only 2>/dev/null || true)"

RAG_CONFIG_CHANGED=0
if echo "$CHANGED" | grep -q '^backend/config\.py$'; then
    # config.py 仅按 diff 行判断——改 TTS/ASR 等配置不触发，只有 RAG_ 配置行才触发
    git diff HEAD -- backend/config.py 2>/dev/null | grep -q '^[+-].*RAG_' && RAG_CONFIG_CHANGED=1
fi

if [ "$WITH_EVAL" -eq 1 ]; then
    echo "（--with-eval: 强制包含 eval 深度评估，预计 30+ 分钟）"
    check "pytest"  python -m pytest backend/tests/ -q --asyncio-mode=auto
elif echo "$CHANGED" | grep -Eq "$RAG_PATTERNS" || [ "$RAG_CONFIG_CHANGED" -eq 1 ]; then
    echo "（检测到 RAG 链路改动，包含 eval 深度评估，预计 30+ 分钟）"
    check "pytest"  python -m pytest backend/tests/ -q --asyncio-mode=auto
else
    echo "（未改 RAG 链路，跳过 eval；如需深检: bash scripts/verify.sh --with-eval）"
    check "pytest"  python -m pytest backend/tests/unit backend/tests/integration -q --asyncio-mode=auto
fi

# ---- 前端 ----
check "eslint"      bash -c "cd frontend && npm run lint"

# ---- Docker 构建（对应 CI 的 build-and-push job）----
check "docker-backend"   docker build -q -f backend/Dockerfile backend/
check "docker-frontend"  docker build -q -f frontend/Dockerfile frontend/

# ---- 技能硬约束（构建时，pre-push 专用）----
# 开发时约束（tdd/read-before/prototype/codebase-design/grill/diagnose）已移到 pre-commit
check "defensive-output"    bash scripts/check-defensive.sh
check "implement"           bash scripts/check-implement.sh

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
