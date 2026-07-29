#!/usr/bin/env bash
# defensive-output 硬约束：
# 检查 TTS 调用点之前是否有过滤管道（_strip_emoji/_strip_action/_strip_symbols）

cd "$(dirname "$0")/.."
TTS_CALLS=$(grep -n "synthesize\|Communicate\|edge_tts" backend/routes.py | grep -v "^#\|^ *\"" | grep -v test_)
FILTER_GUARD=$(grep -c "_strip_emoji\|_strip_action\|_strip_symbols\|_filter_" backend/routes.py)

if [ "$(echo "$TTS_CALLS" | wc -l)" -gt 0 ] && [ "$FILTER_GUARD" -eq 0 ]; then
    echo "✗ defensive-output: TTS 调用缺少过滤管道"
    echo "  在 routes.py 中找到 TTS 调用，但未找到 _strip_* 过滤函数"
    exit 1
fi
echo "defensive-output: TTS 过滤管道 ✓"
