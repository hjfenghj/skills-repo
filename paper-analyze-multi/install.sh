#!/usr/bin/env bash
# paper-analyze-multi skill 部署脚本
# 前置依赖：paper-analyze 已安装（本 skill 是其批量编排层，无独立配置）。
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$HOME/.claude/skills/paper-analyze-multi"

echo "[install] 安装目标: $SKILL_DIR"

# --- 0. 前置检查：paper-analyze 必须已安装 ---
if [ ! -f "$HOME/.claude/skills/paper-analyze/skill.md" ]; then
    echo "[install] ERROR: 未找到 ~/.claude/skills/paper-analyze/skill.md" >&2
    echo "          本 skill 依赖 paper-analyze（子代理执行其 skill.md）。" >&2
    echo "          请先运行本仓库 paper-analyze/install.sh 并配置其 env 文件。" >&2
    exit 1
fi
if [ ! -f "$HOME/.claude/skills/paper-analyze/config/paper-analyze.env" ]; then
    echo "[install] WARN: paper-analyze 的配置文件不存在。" >&2
    echo "          请编辑 ~/.claude/skills/paper-analyze/config/paper-analyze.env 填入 OBSIDIAN_VAULT_PATH，" >&2
    echo "          否则 /paper-analyze-multi 无法写入笔记。" >&2
fi

# --- 1. 复制 skill 文件 ---
mkdir -p "$SKILL_DIR/scripts"
cp "$REPO_DIR/skill.md" "$SKILL_DIR/skill.md"
cp "$REPO_DIR"/scripts/*.py "$SKILL_DIR/scripts/"
rm -rf "$SKILL_DIR/scripts/__pycache__" 2>/dev/null || true
echo "[install] 已复制 skill.md 与 scripts/*.py"

cat <<EOF

[install] 完成。
下一步：
  1. 确认 paper-analyze 已配置（~/.claude/skills/paper-analyze/config/paper-analyze.env）
  2. 启动 Claude Code，运行：
       /paper-analyze-multi <txt文件路径> [输出文件夹]

提示：本 skill 无独立配置文件（复用 paper-analyze 的）；
      批次状态在 ~/.cache/paper-analyze-multi/<hash>/，install 不触碰。
EOF
