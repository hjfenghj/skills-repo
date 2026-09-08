# pwc-paper-list（可迁移版）

抓取 **paperswithcode.co** 会议论文列表的 arXiv 链接与标题，逐行写入 txt（`链接<TAB>标题`，仅含 arXiv 论文，按网页 trending 默认顺序）。作为 [`paper-analyze-multi`](../paper-analyze-multi/) 的标准输入源。

详细用法与 API 细节见 [skill.md](skill.md)。

---

## 快速开始

```bash
# 在本仓库根目录：
bash pwc-paper-list/install.sh

# （可选）设置输出目录（默认 ~/paper-list）：
#   编辑 ~/.claude/skills/pwc-paper-list/config/pwc-paper-list.env

# 启动 Claude Code，运行：
#   /pwc-paper-list https://paperswithcode.co/conferences/icra-2026/robotics
```

依赖：Python 3.8+ 与 `pip install requests`（见 `requirements.txt`）。

---

## 配置接口（唯一的配置文件）

```
~/.claude/skills/pwc-paper-list/config/pwc-paper-list.env
```

由 `install.sh` 从 `config/pwc-paper-list.env.example` 复制而来，已被 `.gitignore` 排除。

| 变量 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `PAPER_LIST_ROOT` | 否 | `~/paper-list` | 输出 txt 的根目录，文件名 `<conf>_<task>.txt` / `<conf>.txt` |

### 优先级（高 → 低）

1. **真实 shell 环境变量**（`export PAPER_LIST_ROOT=...`，临时覆盖）
2. **`pwc-paper-list.env` 文件**里的值（永久设置）
3. **脚本默认值** `~/paper-list`

env 文件的解析只发生在 `scripts/crawl_pwc.py` 的 `load_env_file()` 一处（单一解析点）。

---

## 与其他 skill 的衔接

```
/pwc-paper-list <会议链接>          → 产出 ~/paper-list/<conf>_<task>.txt
/paper-analyze-multi <该txt>        → 逐篇深度分析（每篇独立子代理）
                                       ↳ 依赖 paper-analyze（单篇分析核心）
```

- txt 格式（`链接<TAB>标题`）与 `paper-analyze-multi` 的 `parse_paper_list.py` 兼容（只读行首链接）
- `paper-analyze-multi` 需先装好 `paper-analyze` 并配置 vault（见各自 README）

---

## 平台说明

- **Windows**：Git Bash。配置文件里路径用正斜杠：`D:/study/paper-list`
- **macOS**：系统 bash 即可
- 脚本只依赖 `requests`，无其他 pip 依赖

---

## 更新

```bash
git pull && bash pwc-paper-list/install.sh
```

`install.sh` 只同步 `skill.md` 与 `scripts/`，不会覆盖已编辑的 `pwc-paper-list.env`。

---

## 排错

| 现象 | 处理 |
|------|------|
| 抓取 429/超时 | 脚本默认页间延迟 0.5s，可用 `--delay 2` 限速重试 |
| 输出到了意外的目录 | `export PAPER_LIST_ROOT` 临时指定，或检查 env 文件与 `--output-root` |
| `ModuleNotFoundError: requests` | `pip install requests` |
| 想复现网页切过的排序 | 把带 `?order_by=` 的完整链接贴给 skill |
