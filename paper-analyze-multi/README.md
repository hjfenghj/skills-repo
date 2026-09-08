# paper-analyze-multi（可迁移版）

批量论文深度分析**编排器**：读取一个 txt 文件（每行一个论文链接），全自动依次处理——每篇论文在一个**独立子代理**的新上下文中执行 `paper-analyze` 完整流程（下载、深度分析、笔记、图片上传、知识图谱），主会话只回收摘要 JSON，实现每篇自动上下文重置；进度持久化可续（中断后重跑自动跳过已完成）。

详细工作流程见 [skill.md](skill.md)。

---

## 依赖关系（重要）

本 skill 是 [`paper-analyze`](../paper-analyze/) 的批量编排层，**不重复实现单篇分析逻辑**——每篇论文的子代理直接读取并执行 `~/.claude/skills/paper-analyze/skill.md`。

因此：

1. **必须先安装 `paper-analyze`**（同仓库 `../paper-analyze/`，先跑它的 `install.sh`）
2. **没有自己的配置文件**——直接复用 `~/.claude/skills/paper-analyze/config/paper-analyze.env`（`OBSIDIAN_VAULT_PATH` 及可选的 `OSS_*`），单一配置源
3. 图片上传依赖（`oss2` + `PyMuPDF`）也就是 `paper-analyze/requirements.txt`，装一次即可

与 [`pwc-paper-list`](../pwc-paper-list/) 的衔接：它产出的 `链接<TAB>标题` txt 可直接作为本 skill 的输入。

---

## 快速开始

```bash
# 前置：paper-analyze 已安装并配好 ~/.claude/skills/paper-analyze/config/paper-analyze.env

# 在本仓库根目录：
bash paper-analyze-multi/install.sh

# 启动 Claude Code，运行：
#   /paper-analyze-multi /path/to/papers.txt [输出文件夹(可选)]
```

txt 每行一个论文链接，支持格式：

```
# 注释行
https://arxiv.org/abs/2402.12345
https://arxiv.org/pdf/2305.20050v2
https://huggingface.co/papers/2410.12345
1706.03762
链接<TAB>标题   # pwc-paper-list 产出格式，只读行首链接
```

---

## 配置接口

本 skill 无独立配置，全部复用 paper-analyze 的（见 `../paper-analyze/README.md`）：

| 变量 | 用途 |
|------|------|
| `OBSIDIAN_VAULT_PATH` | 子代理写笔记/图谱的 vault 根目录（继承给子代理） |
| `OSS_*` / `PICGO_CONFIG_PATH` | 子代理上传图片到 OSS 用 |

优先级与 paper-analyze 一致：真实 shell 环境变量 > `paper-analyze.env` 文件 > 默认值。

---

## 运行时状态（进度持久化）

- 批次状态目录：`~/.cache/paper-analyze-multi/<hash>/`（hash = txt 绝对路径 MD5 前 12 位）
  - `progress.json`：每篇完成后立即落盘，中断重跑自动续
  - `parsed.json`：列表解析缓存；txt 内容变了删除它重跑
  - `batch_report.md`：批次完成报告
- 批次全部完成后状态目录**保留**（防误重跑）；强制重跑整批 → 删除对应 hash 目录
- hash 计算跨平台：Linux/Git Bash 用 `md5sum`，macOS 用 `md5 -q`

---

## 平台说明

- **Windows**：Git Bash（Claude Code 自带）。注意本 skill 的 bash 与 Python 脚本都假设 `python` 命令可用。
- **macOS**：系统 bash 即可；hash 已自动适配 `md5`。若 `python` 不存在（只有 `python3`），需要 pyenv/conda 提供 `python` 别名。
- Python 脚本仅标准库，无 pip 依赖。

---

## 更新

```bash
git pull && bash paper-analyze-multi/install.sh
```

`install.sh` 只同步 `skill.md` 与 `scripts/`，不碰任何状态/配置数据。

---

## 已知边界（如实说明）

- 子代理单篇生成的笔记很大时（平均 40KB+），一次性 Write 可能触发输出截断。当前部署版 skill.md 未内置分块写入策略，运行期曾用临时脚本（writer 拆分 + prep/finish）绕过；若批量跑时遇到笔记 0 字节/截断，按同样思路临时处理，或把每篇笔记拆成多次 Edit 追加。
- 顺序处理（不并行），避免知识图谱并发写冲突。
