#!/usr/bin/env bash
# paper-analyze skill 一键部署脚本 / one-shot deployer
#
# 把本仓库的 skill 文件安装到 ~/.claude/skills/paper-analyze/，并准备好配置文件。
# 适用于 Windows (Git Bash) / macOS / Linux。幂等，可重复运行。
#
# 用法：
#   bash install.sh                              # 生成配置模板，提示手动编辑
#   OBSIDIAN_VAULT_PATH=/path bash install.sh     # 直接把 vault 路径写进配置
set -e

# --- 解析仓库目录（脚本所在目录）---
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$HOME/.claude/skills/paper-analyze"
CONFIG_DIR="$SKILL_DIR/config"
ENV_FILE="$CONFIG_DIR/paper-analyze.env"
EXAMPLE_FILE="$REPO_DIR/config/paper-analyze.env.example"

echo "[install] 仓库目录  : $REPO_DIR"
echo "[install] 安装目标  : $SKILL_DIR"

# --- 1. 复制 skill 文件到 Claude Code 的 skill 目录 ---
mkdir -p "$SKILL_DIR/scripts" "$CONFIG_DIR"
cp "$REPO_DIR/skill.md" "$SKILL_DIR/skill.md"
cp "$REPO_DIR"/scripts/*.py "$SKILL_DIR/scripts/"
echo "[install] 已复制 skill.md 与 scripts/*.py"

# --- 2. 准备配置文件（不覆盖已有配置）---
if [ ! -f "$ENV_FILE" ]; then
    cp "$EXAMPLE_FILE" "$ENV_FILE"
    echo "[install] 已生成配置模板: $ENV_FILE"

    # 若调用方通过环境变量提供了 vault 路径，直接写入（就地替换该行）
    if [ -n "$OBSIDIAN_VAULT_PATH" ]; then
        if command -v sed >/dev/null 2>&1; then
            sed -i.bak "s|^OBSIDIAN_VAULT_PATH=.*|OBSIDIAN_VAULT_PATH=\"$OBSIDIAN_VAULT_PATH\"|" "$ENV_FILE"
            rm -f "$ENV_FILE.bak"
            echo "[install] 已写入 OBSIDIAN_VAULT_PATH=$OBSIDIAN_VAULT_PATH"
        else
            echo "[install] 警告: 未找到 sed，请手动编辑 $ENV_FILE 填入 OBSIDIAN_VAULT_PATH"
        fi
    fi
else
    echo "[install] 配置已存在，跳过（如需重置请删除 $ENV_FILE 后重跑）"
fi

# --- 3. 清理可能存在的 __pycache__ ---
rm -rf "$SKILL_DIR/scripts/__pycache__" 2>/dev/null || true

# --- 4. 提示下一步 ---
cat <<EOF

[install] 完成。
下一步：
  1. 编辑配置文件填入你的 Obsidian vault 路径：
       $ENV_FILE
     （设 OBSIDIAN_VAULT_PATH；若需上传图片到 OSS，再填 OSS_* 或安装 PicGo）
  2. 安装 Python 依赖（仅图片上传步骤需要）：
       pip install -r "$REPO_DIR/requirements.txt"
  3. 启动 Claude Code，运行：
       /paper-analyze <arXiv ID 或论文链接>

提示：以后 git pull 更新本仓库后，重新运行 bash install.sh 即可同步 skill。
EOF
