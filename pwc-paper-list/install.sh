#!/usr/bin/env bash
# pwc-paper-list skill 一键部署脚本
# 适用于 Windows (Git Bash) / macOS / Linux。幂等，可重复运行。
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$HOME/.claude/skills/pwc-paper-list"
CONFIG_DIR="$SKILL_DIR/config"
ENV_FILE="$CONFIG_DIR/pwc-paper-list.env"
EXAMPLE_FILE="$REPO_DIR/config/pwc-paper-list.env.example"

echo "[install] 安装目标: $SKILL_DIR"

# --- 1. 复制 skill 文件 ---
mkdir -p "$SKILL_DIR/scripts" "$CONFIG_DIR"
cp "$REPO_DIR/skill.md" "$SKILL_DIR/skill.md"
cp "$REPO_DIR"/scripts/*.py "$SKILL_DIR/scripts/"
rm -rf "$SKILL_DIR/scripts/__pycache__" 2>/dev/null || true
echo "[install] 已复制 skill.md 与 scripts/*.py"

# --- 2. 准备配置文件（不覆盖已有配置）---
if [ ! -f "$ENV_FILE" ]; then
    cp "$EXAMPLE_FILE" "$ENV_FILE"
    echo "[install] 已生成配置模板: $ENV_FILE"

    if [ -n "$PAPER_LIST_ROOT" ]; then
        if command -v sed >/dev/null 2>&1; then
            sed -i.bak "s|^PAPER_LIST_ROOT=.*|PAPER_LIST_ROOT=\"$PAPER_LIST_ROOT\"|" "$ENV_FILE"
            rm -f "$ENV_FILE.bak"
            echo "[install] 已写入 PAPER_LIST_ROOT=$PAPER_LIST_ROOT"
        fi
    fi
else
    echo "[install] 配置已存在，跳过（如需重置请删除 $ENV_FILE 后重跑）"
fi

cat <<EOF

[install] 完成。
下一步：
  1. （可选）编辑 $ENV_FILE 设置 PAPER_LIST_ROOT（默认 ~/paper-list）
  2. 安装 Python 依赖：pip install requests
  3. 启动 Claude Code，运行：
       /pwc-paper-list <paperswithcode 会议链接>

提示：以后 git pull 更新本仓库后，重新运行 bash install.sh 即可同步 skill。
EOF
