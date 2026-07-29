#!/usr/bin/env bash
# read-before-code 硬约束：
# 检查代码中显式加载的配置文件是否存在

cd "$(dirname "$0")/.."
MISSING_COUNT=0

# 只检查 open/Path/json.load/yaml.load 等显式文件加载
check_files() {
    local pattern="$1"
    while IFS= read -r match; do
        [ -z "$match" ] && continue
        # 提取路径部分
        fpath=$(echo "$match" | grep -oP '(?<=(["'"'"']))[^"'"'"']*\.(json|yaml|yml|ini|moc3|model3)[^"'"'"']*(?=["'"'"'])' | head -1)
        [ -z "$fpath" ] && continue
        # 跳过绝对路径和 URL
        [[ "$fpath" == /* ]] && continue
        [[ "$fpath" == http* ]] && continue
        # 检查文件是否存在
        if [ ! -f "$fpath" ] && [ ! -f "backend/$fpath" ] && [ ! -f "../$fpath" ]; then
            echo "  $fpath"
            MISSING_COUNT=$((MISSING_COUNT + 1))
        fi
    done < <(grep -rPn "$pattern" backend/agent/ backend/tts/ backend/asr/ --include="*.py" 2>/dev/null | grep -v test_ | grep -v "^#")
}

check_files 'open\('
check_files 'Path\('
check_files 'load_'

if [ "$MISSING_COUNT" -gt 0 ]; then
    echo "✗ read-before-code: $MISSING_COUNT 个引用文件不存在"
    exit 1
fi
echo "read-before-code: 文件引用检查 ✓"
