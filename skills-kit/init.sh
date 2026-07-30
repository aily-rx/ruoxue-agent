#!/usr/bin/env bash
# ============================================================
# skills-kit 安装脚本
# 用法:
#   ./init.sh /path/to/project           # 首次安装
#   ./init.sh --update /path/to/project   # 更新已有项目
#   ./init.sh --self                      # 安装到 kit 所在上级项目
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
UPDATE=false

if [ "$1" = "--update" ]; then
    UPDATE=true
    TARGET="$(cd "$2" && pwd)"
elif [ "$1" = "--self" ]; then
    TARGET="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    TARGET="$(cd "$1" && pwd)"
fi

echo "skills-kit init -> $TARGET"
echo "mode: $([ "$UPDATE" = true ] && echo 'update' || echo 'install')"

# ── helper: generate skills index table ──────────────────
gen_index() {
    local dir="$1"
    echo "<!-- SKILLS:START -->"
    echo ""
    echo "| Skill | 触发关键词 | 位置 |"
    echo "|-------|-----------|------|"
    for yaml_file in "$dir"/engineering/*/deepseek.yaml "$dir"/productivity/*/deepseek.yaml; do
        [ -f "$yaml_file" ] || continue
        local name display keywords rel_path
        name=$(grep '^name:' "$yaml_file" | head -1 | sed 's/name: *//')
        display=$(grep 'display_name:' "$yaml_file" | head -1 | sed 's/display_name: *"//;s/"$//')
        keywords=$(grep -A1 'trigger_keywords:' "$yaml_file" | tail -1 | sed 's/^ *- *"//;s/"$//')
        rel_path="${yaml_file#$dir/}"
        rel_path="$(dirname "$rel_path")"
        [ -n "$name" ] && echo "| $name | $display ($keywords...) | \`skills/$rel_path/\` |"
    done
    echo ""
    echo "<!-- SKILLS:END -->"
}

# ── helper: extract hard constraints from kit's CLAUDE.md ─
extract_hard_constraints() {
    awk '/^## 硬约束/{found=1} found{print} /^## 项目信息/{exit}' "$SCRIPT_DIR/CLAUDE.md"
}

# ── helper: insert constraints + index into target CLAUDE.md ─
patch_claude() {
    local target_md="$1"
    local skills_dir="$2"
    local tmp_idx tmp_out

    # Check if constraints already exist
    if ! grep -q '## 硬约束' "$target_md"; then
        echo "       插入硬约束块..."
        tmp_out="$(mktemp)"
        extract_hard_constraints > "$tmp_out"
        echo "" >> "$tmp_out"
        cat "$target_md" >> "$tmp_out"
        mv "$tmp_out" "$target_md"
    else
        echo "       硬约束块已存在，跳过"
    fi

    # Generate index
    tmp_idx="$(mktemp)"
    gen_index "$skills_dir" > "$tmp_idx"

    # Replace or append SKILLS block
    if grep -q '<!-- SKILLS:START -->' "$target_md"; then
        echo "       更新 SKILLS 索引..."
        tmp_out="$(mktemp)"
        awk -v idx_file="$tmp_idx" '
            BEGIN { print_skills = 0 }
            /<!-- SKILLS:START -->/ { print_skills = 1; while ((getline line < idx_file) > 0) print line; close(idx_file); next }
            /<!-- SKILLS:END -->/   { print_skills = 0; next }
            !print_skills
        ' "$target_md" > "$tmp_out"
        mv "$tmp_out" "$target_md"
    else
        echo "       追加 SKILLS 索引..."
        cat "$tmp_idx" >> "$target_md"
    fi
    rm -f "$tmp_idx"
}

# ── 1. 复制 skills 目录 ────────────────────────────────
echo "[1/4] 复制 skills/ ..."
if [ -d "$TARGET/skills" ]; then
    rm -rf "$TARGET/skills"
fi
cp -r "$SCRIPT_DIR/skills" "$TARGET/skills"
echo "       skills/ -> $TARGET/skills/"

# ── 2. 复制 CORE_RULES.md ──────────────────────────────
echo "[2/4] 复制 CORE_RULES.md ..."
cp "$SCRIPT_DIR/CORE_RULES.md" "$TARGET/skills/CORE_RULES.md"
echo "       CORE_RULES.md -> $TARGET/skills/CORE_RULES.md"

# ── 3. 合并 CLAUDE.md ─────────────────────────────────
echo "[3/4] 合并 CLAUDE.md ..."

if [ -f "$TARGET/CLAUDE.md" ]; then
    cp "$TARGET/CLAUDE.md" "$TARGET/CLAUDE.md.bak"
    patch_claude "$TARGET/CLAUDE.md" "$TARGET/skills"
else
    cp "$SCRIPT_DIR/CLAUDE.md" "$TARGET/CLAUDE.md"
    echo "       从模板创建 CLAUDE.md"
    patch_claude "$TARGET/CLAUDE.md" "$TARGET/skills"
fi

# ── 4. 验证脚本 ─────────────────────────────────────────
echo "[4/4] 检查 CI 验证脚本 ..."
if [ -f "$SCRIPT_DIR/verify.sh" ] && [ ! -f "$TARGET/scripts/verify.sh" ]; then
    mkdir -p "$TARGET/scripts"
    cp "$SCRIPT_DIR/verify.sh" "$TARGET/scripts/verify.sh"
    chmod +x "$TARGET/scripts/verify.sh"
    echo "       verify.sh -> $TARGET/scripts/verify.sh"
else
    echo "       跳过（已存在或无模板）"
fi

echo ""
echo "========================================="
echo " skills-kit 安装完成"
echo "========================================="
echo ""
echo "已安装到: $TARGET"
echo "  $TARGET/skills/         # 11 个 skill 文件"
echo "  $TARGET/CORE_RULES.md   # 行为准则"
echo "  $TARGET/CLAUDE.md       # 硬约束已合并"
echo ""
echo "下次对话开始时 CLAUDE.md 中的硬约束即自动生效。"
