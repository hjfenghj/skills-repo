# paper-analyze（可迁移版）

把单篇 arXiv 论文深度分析成**图文并茂的中文技术长文笔记**并写入 Obsidian，融合知乎技术解读风格与学术评分体系，自动上传图片到阿里云 OSS、更新知识图谱。

本仓库是 `~/.claude/skills/paper-analyze` 的**可迁移源**：克隆到任意 Windows / macOS 机器，跑一次 `install.sh` 即可装好 skill，再编辑一个配置文件填入你自己的 Obsidian 路径与 OSS 凭证。

---

## 你得到什么

- `skill.md`：skill 主体（写作风格、笔记模板、评分细则、流程定义）
- `scripts/`
  - `generate_note.py`：生成笔记骨架
  - `update_graph.py`：更新知识图谱
  - `upload_images.py`：图片上传到阿里云 OSS（PDF 自动转 PNG）
  - `pa_config.py`：**集中式配置加载器**（所有环境变量 / 配置文件解析只在这里发生一次）
- `config/paper-analyze.env.example`：配置模板
- `install.sh`：一键部署脚本
- `requirements.txt`：图片上传所需 Python 依赖

---

## 环境要求

- **Claude Code**（提供 `/paper-analyze` 这个 slash command）
- **bash**：Windows 用 Git Bash（Claude Code 自带）；macOS / Linux 用系统自带 bash
- **Python 3.8+**
- **（仅图片上传步骤）** `pip install -r requirements.txt` → `oss2` + `PyMuPDF`
- **（仅图片上传步骤，二选一）** 阿里云 OSS 凭证：直接写进配置文件，或安装 PicGo 配好阿里云图床

> 不配 OSS 也能用：笔记照常生成并保存到 Obsidian，只是图片保持本地路径、不替换成 OSS URL。

---

## 快速开始

```bash
# 1. 克隆（或拷贝）本仓库到任意位置
git clone <your-repo-url> ~/github_skill
cd ~/github_skill

# 2. 一键安装：把 skill 复制到 ~/.claude/skills/paper-analyze/ 并生成配置模板
bash install.sh
#   也可以直接把 vault 路径传进去：
#   OBSIDIAN_VAULT_PATH="/Users/you/ObsidianVault" bash install.sh

# 3. 编辑配置文件，填入你的 Obsidian vault 路径（必填）和 OSS 凭证（可选）
#    Windows: C:\Users\you\.claude\skills\paper-analyze\config\paper-analyze.env
#    macOS:   ~/.claude/skills/paper-analyze/config/paper-analyze.env

# 4.（可选）装图片上传依赖
pip install -r requirements.txt

# 5. 启动 Claude Code，运行
#    /paper-analyze 2402.12345
```

---

## 配置接口（唯一的配置文件）

所有可配置项集中在一个文件：

```
~/.claude/skills/paper-analyze/config/paper-analyze.env
```

由 `install.sh` 从 `config/paper-analyze.env.example` 复制而来。**该文件已被 `.gitignore` 排除，密钥不会进仓库。**

| 变量 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `OBSIDIAN_VAULT_PATH` | 是 | — | Obsidian 仓库根目录绝对路径。笔记写入 `<vault>/20_Research/Papers/`，知识图谱写入 `<vault>/20_Research/PaperGraph/`，语言/领域配置读取自 `<vault>/99_System/Config/research_interests.yaml` |
| `OSS_ACCESS_KEY_ID` | 否 | — | 阿里云 OSS AccessKey ID。留空则回退到 PicGo 配置 |
| `OSS_ACCESS_KEY_SECRET` | 否 | — | 阿里云 OSS AccessKey Secret |
| `OSS_BUCKET` | 否 | — | OSS bucket 名，例 `my-obsidian-bucket` |
| `OSS_AREA` | 否 | — | OSS 区域，例 `oss-cn-beijing` |
| `OSS_PATH` | 否 | `obsidian-img/` | OSS 对象前缀 |
| `PICGO_CONFIG_PATH` | 否 | — | 高级：显式指定 PicGo 的 `data.json` 路径，不在默认位置时用 |

### 优先级（高 → 低）

1. **真实 shell 环境变量**（你在终端 `export` 过的，或启动 Claude Code 时就存在的）
2. **`paper-analyze.env` 文件**里的值
3. **脚本默认值** / PicGo 配置回退（仅 OSS）

即：临时覆盖某个值，直接在 shell 里 `export` 即可，不必改文件。

### 配置如何被读取

- **skill.md 步骤0** 会 `source` 这个 env 文件，把变量导进 skill 运行时的 shell。
- **三个 Python 脚本** 启动时调用 `pa_config.load_env_file()`，把同一份文件载入 `os.environ`（已存在的环境变量不会被覆盖）。
- 所以无论 skill 被 `/paper-analyze` 调用，还是脚本被单独手动运行，配置都一致；且配置解析只在 `pa_config.py` 这一处发生。

---

## 文件布局

```
~/.claude/skills/paper-analyze/        <- install.sh 安装到这里（Claude Code 找 skill 的位置）
├── skill.md
├── scripts/
│   ├── generate_note.py
│   ├── update_graph.py
│   ├── upload_images.py
│   └── pa_config.py
└── config/
    └── paper-analyze.env              <- 你的本地配置（gitignore）

<本仓库>/                              <- 你 git clone 的位置，可放任意盘/任意目录
├── skill.md  scripts/  config/paper-analyze.env.example
├── install.sh  requirements.txt  README.md  .gitignore
```

`install.sh` 默认**复制**文件到 skill 目录。更新流程：`git pull && bash install.sh` 即可同步。

> 想让 `git pull` 后自动生效、免去重跑 install？可以用软链接代替复制：
> ```bash
> # macOS / Linux（或 Windows 开了开发者模式 + Git Bash winsymlinks）
> rm -rf ~/.claude/skills/paper-analyze
> ln -s "$PWD" ~/.claude/skills/paper-analyze
> ```
> 注意 Windows 软链接需要权限，默认还是用复制更省心。

---

## 平台说明

### Windows
- 必须用 **Git Bash** 跑 `install.sh` 与 Claude Code（Claude Code 在 Windows 上的 shell 就是 Git Bash）。
- 临时目录用 `${TMPDIR:-/tmp}`，Git Bash 里 `/tmp` 可用，无需改。
- 配置文件里路径建议用正斜杠：`C:/Users/you/ObsidianVault`。

### macOS
- 系统 bash 即可（`install.sh` 用 `#!/usr/bin/env bash`）。
- PicGo 配置自动定位到 `~/Library/Application Support/picgo/data.json`（大小写两个候选都会试，无需手动指定）。
- 临时目录用 `$TMPDIR`（macOS 默认指向 `/var/folders/...`）。

### OSS 凭证
- 推荐：直接在 `paper-analyze.env` 里填 `OSS_*`，跨机器迁移时随配置走（但别提交）。
- 或者：装 PicGo 配好阿里云图床，脚本自动读取，无需在 env 文件里填。

---

## 更新

```bash
cd ~/github_skill
git pull
bash install.sh     # 重新同步 skill 文件（不会覆盖你已编辑的 paper-analyze.env）
```

---

## 排错

| 现象 | 原因 / 处理 |
|------|------|
| `OBSIDIAN_VAULT_PATH 未设置` | 编辑 `~/.claude/skills/paper-analyze/config/paper-analyze.env` 填入 vault 路径 |
| 图片上传报 `未找到 OSS 配置` | 在 env 文件填 `OSS_*`，或安装配置 PicGo；不需要图片上云可忽略（笔记仍生成） |
| Windows 下 `/tmp` 报错 | 确认用 Git Bash 运行 Claude Code，而非 cmd/PowerShell |
| `pip install` 失败 | 仅图片上传需要 `oss2`+`PyMuPDF`；不装也能生成笔记 |
| 跑 `/paper-analyze` 没反应 | 确认 skill 已装到 `~/.claude/skills/paper-analyze/skill.md`，重启 Claude Code |

---

## 迁移到新机器的完整清单

1. `git clone` 本仓库
2. `bash install.sh`（或 `OBSIDIAN_VAULT_PATH=... bash install.sh`）
3. 编辑 `~/.claude/skills/paper-analyze/config/paper-analyze.env`：填 `OBSIDIAN_VAULT_PATH`，按需填 `OSS_*`
4. `pip install -r requirements.txt`（如需图片上传）
5. 打开 Claude Code → `/paper-analyze <arXiv ID>`
