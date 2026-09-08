---
name: paper-analyze-multi
description: 批量深度分析论文：读取一个 txt 文件（每行一个论文链接），全自动依次处理——每篇论文在独立子代理的新上下文中执行 paper-analyze 完整流程（下载、深度分析、笔记、图片上传、知识图谱），主会话只回收摘要，实现每篇自动上下文重置；进度持久化可续 / Batch deep-analyze papers from a txt list (one link per line); each paper runs in an isolated subagent's fresh context (paper-analyze full pipeline), main session only collects summaries — automatic per-paper context reset, no manual /clear; progress persisted and resumable
allowed-tools: Read, Write, Bash, Edit, Agent
---

# paper-analyze-multi

批量论文分析**编排器**。读取一个 txt 文件（每行一个论文链接），**全自动依次**对每篇论文完成 `paper-analyze` 的完整流程（下载 PDF / 提取源码、深度分析、写图文笔记、上传图片到 OSS、更新知识图谱）。

本 skill 是 `paper-analyze` 的批量编排层，**不重复实现单篇分析逻辑**——每篇论文由一个**独立子代理**读取并执行 `paper-analyze` 的 skill.md。原 `paper-analyze` skill 保持不变，不被覆盖。

# 上下文重置策略（核心）

为避免多篇论文的分析内容累积导致上下文膨胀，本 skill 采用 **「子代理隔离」** 模式实现**全自动的每篇上下文重置**：

- **每篇论文在一个独立子代理的新上下文中执行**（用 Agent 工具派生）。
- 子代理读取 `paper-analyze/skill.md` 并完整执行其流程：PDF 文本、深度分析、整篇笔记的生成**全部发生在子代理自己的上下文里**。
- 子代理结束后，**只把一段摘要 JSON 返回主会话**；那篇论文的完整内容随之销毁，等价于自动 reset。
- 主会话只累积 N 条小摘要，不累积任何论文正文，因此可全自动跑完整批而无需 `/clear`。

> 平台约束：skill 无法通过工具自行清空主会话上下文（`/clear` 是用户侧命令）。子代理隔离是唯一能在**全自动**前提下实现"每篇后 reset"的机制——每个子代理=一个临时的新上下文，结束即销毁。

# 语言设置

与 `paper-analyze` 一致。子代理执行 skill.md 时会自行读取配置：

```bash
LANGUAGE=$(grep -E "^\s*language:" "$OBSIDIAN_VAULT_PATH/99_System/Config/research_interests.yaml" | awk '{print $2}' | tr -d '"')
[ -z "$LANGUAGE" ] && LANGUAGE="zh"
```

# 输入

调用方式：

```
/paper-analyze-multi <txt文件路径> [输出文件夹(可选)]
```

- **txt 文件路径**（必填）：每行一个论文链接。支持格式：
  - `https://arxiv.org/abs/2402.12345`
  - `https://arxiv.org/pdf/2402.12345v2`
  - `https://arxiv.org/e-print/2402.12345`
  - `https://huggingface.co/papers/2410.12345`
  - `arXiv:2402.12345`
  - `2402.12345`（纯 ID）
  - 老式 ID：`cs.AI/0703001`
  - 「链接<TAB>标题」格式（如 `pwc-paper-list` 产出的 txt）：解析时只读行首链接 token，标题不参与匹配
  - 空行与 `#` 开头的注释行自动忽略
- **输出文件夹**（可选）：所有论文统一保存到该子文件夹（相对于 `20_Research/Papers/`，可多级如 `大模型/LLM_Training`）。不指定则每篇由 `paper-analyze` 自动推断领域。
  - 首次执行时记录到 `progress.json`；后续重新执行若不传，自动沿用首次记录的值。

# 工作流程

## 步骤0：初始化环境

```bash
SKILL_DIR="$HOME/.claude/skills/paper-analyze-multi"
PAPER_ANALYZE_SKILL="$HOME/.claude/skills/paper-analyze/skill.md"
INPUT_TXT="[用户提供的 txt 文件路径]"
CUSTOM_OUTPUT_DIR="[用户提供的输出文件夹，可为空]"

# 载入 paper-analyze 的本地配置（本 skill 依赖 paper-analyze，配置同源，不另设配置文件）。
# 真实环境变量优先于文件；env 文件不存在说明 paper-analyze 未配置，步骤0 一并报错。
if [ -f "$HOME/.claude/skills/paper-analyze/config/paper-analyze.env" ]; then
    set -a
    . "$HOME/.claude/skills/paper-analyze/config/paper-analyze.env"
    set +a
fi

# 批次状态目录：按 txt 绝对路径的 hash 稳定命名，跨多次执行（含中断续跑）保持一致
INPUT_ABS="$(cd "$(dirname "$INPUT_TXT")" && pwd)/$(basename "$INPUT_TXT")"
# 跨平台 hash：Linux/Git Bash 用 md5sum，macOS 用 md5 -q（两者输出前 12 位一致）
if command -v md5sum >/dev/null 2>&1; then
    BATCH_HASH="$(echo -n "$INPUT_ABS" | md5sum | cut -c1-12)"
else
    BATCH_HASH="$(echo -n "$INPUT_ABS" | md5 -q | cut -c1-12)"
fi
STATE_DIR="$HOME/.cache/paper-analyze-multi/${BATCH_HASH}"
mkdir -p "${STATE_DIR}"
PROGRESS_FILE="${STATE_DIR}/progress.json"
PARSED_FILE="${STATE_DIR}/parsed.json"
```

> `STATE_DIR` 位于用户主目录下，存放进度与解析缓存。**批次全部完成后不自动删除**（保留作完成记录与防误重跑；如需强制重跑整批，删除该目录即可）。

## 步骤1：解析论文列表（解析与业务分离）

若 `PARSED_FILE` 已存在则直接复用（避免重复解析）；否则用专用脚本解析 txt：

```bash
python "${SKILL_DIR}/scripts/parse_paper_list.py" "${INPUT_TXT}" --output "${PARSED_FILE}"
```

读取 `parsed.json`，得到 `valid` / `duplicates` / `invalid` 三个列表。

**处理规则（fail fast，不静默兜底）**：
- 若 txt 文件不存在 → 脚本直接报错退出，停止。
- 若 `valid` 为空 → 停止，向用户展示 `invalid` 列表请其修正。
- `duplicates` 与 `invalid` 行**不阻塞**批次，但必须向用户明示（不静默丢弃）。
- 若 txt 内容有变化需重新解析，删除 `PARSED_FILE` 后重跑（或修改脚本支持 `--force`，此处保持最小实现）。

## 步骤2：加载或初始化进度

```bash
if [ -f "${PROGRESS_FILE}" ]; then
    # 读取已有进度（续跑）
    PROGRESS=$(cat "${PROGRESS_FILE}")
else
    # 首次执行：初始化
    # （started 时间戳由主会话生成，避免子代理各自生成不一致）
    cat > "${PROGRESS_FILE}" <<'EOF'
{
  "input": "<INPUT_ABS>",
  "output_dir": "<CUSTOM_OUTPUT_DIR 或空>",
  "total": <valid 篇数>,
  "started": "<主会话生成的 ISO 时间>",
  "done": [],
  "failed": []
}
EOF
fi
```

`progress.json` 结构：

```json
{
  "input": "<txt 绝对路径>",
  "output_dir": "<输出文件夹或空>",
  "total": <N>,
  "started": "<ISO 时间>",
  "done":   [{"arxiv_id","title","score","summary","note_path","steps_done"}],
  "failed": [{"arxiv_id","reason"}]
}
```

**output_dir 一致性**：若 `progress.json` 已存在，沿用其中记录的 `output_dir`（保证整批保存位置一致）。若用户本次传了不同的 `output_dir`，向用户警告并仍沿用历史值，避免同一批次散落不同目录。

## 步骤3：计算待处理列表

从 `parsed.json` 的 `valid` 列表（按 txt 原顺序）中，剔除已 `done` 和已 `failed` 的 arXiv ID，得到 `pending` 列表（保持原顺序）：

```
done_ids    = { p.arxiv_id for p in progress.done }
failed_ids  = { p.arxiv_id for p in progress.failed }
pending     = [ v for v in valid if v.arxiv_id not in done_ids ∪ failed_ids ]
```

- 若 `pending` 为空 → 跳到 **步骤5（批次完成报告）**。
- 否则进入步骤 4，对 `pending` 中的每篇**顺序**处理。

## 步骤4：顺序处理每篇论文（核心 —— 子代理隔离）

对 `pending` 列表**按顺序**逐篇处理（一篇子代理完全返回后再启动下一篇，**不并行**）。当前篇为第 `i` 篇（共 `N = total` 篇），arXiv ID 记为 `<ID>`。

### 4.1 用 Agent 工具派生子代理

`subagent_type`: `general-purpose`（拥有全部工具：Read/Write/Bash/Edit/WebFetch 等，可执行完整 paper-analyze 流程）。

子代理 prompt（主会话填入 `<ID>` 与 `<OUTPUT_DIR>` 后传入）：

```
你是 paper-analyze 工作流的执行者。请在你当前的独立上下文中完整执行单篇论文的深度分析。

任务：对 arXiv 论文 <ID> 执行 paper-analyze 完整流程。
输出文件夹（可选，留空则自动推断领域）：<OUTPUT_DIR>

执行方式：
1. 用 Read 工具读取完整指令文件：~/.claude/skills/paper-analyze/skill.md
2. 严格按该文件中的"工作流程"步骤 1~8 执行（识别论文 → 获取内容 → 深度分析 → 复制图片 → 生成笔记 → 上传引用图片并替换为OSS URL → 更新知识图谱 → 展示摘要），并遵循其中的"写作风格要求""事实性约束""严格路径规则""公式输出规范"等所有约束。
3. 关键必做项（不可跳过）：
   - 下载 PDF 与 arXiv 源码包，提取真实图片到 images/
   - 写图文笔记到 20_Research/Papers/<领域或输出文件夹>/<论文标题>/[未读]<论文标题>.md（三层路径不可省略，写入前校验层数）
   - 步骤6：用 $HOME/.claude/skills/paper-analyze/scripts/upload_images.py 上传笔记中引用的图片，并用 Edit 把本地 images/xxx 路径替换为 OSS URL
   - 步骤7：用 update_graph.py 更新知识图谱
   - 步骤8.1：清理本次 /tmp 工作目录
4. 环境变量 OBSIDIAN_VAULT_PATH 已继承自父会话，直接使用。
5. 严禁编造论文未提及的实验数据、虚假相关论文或不存在的链接；无法确认的信息标注"论文未提及"。

完成后，你的最终消息【只】输出下面这个 JSON（不要任何额外文字、不要 markdown 代码围栏）：
{
  "arxiv_id": "<ID>",
  "title": "<论文标题>",
  "score": "<X.X/10 或 null>",
  "summary": "<一句话总结，大白话>",
  "note_path": "<笔记相对 vault 的路径，如 20_Research/Papers/大模型/X/[未读]X.md>",
  "status": "success 或 failed",
  "reason": "<失败原因；成功则留空>",
  "steps_done": {
    "downloaded": true/false,
    "note_written": true/false,
    "images_uploaded": true/false,
    "graph_updated": true/false
  }
}
```

### 4.2 收集子代理结果

子代理的最终消息即为返回值（主会话不展示子代理过程）。解析其中的 JSON：

- `status == "success"` → 追加到 `progress.done`（含 title/score/summary/note_path/steps_done）。
- `status == "failed"` 或 JSON 解析失败 → 追加到 `progress.failed`（含 reason）。
- 用 Write 覆写 `progress.json`（每篇返回后立即落盘，保证中断可续）。

### 4.3 打印单篇进度（主会话只保留摘要）

```
[i/N] arXiv:<ID> ✅ 8.5/10 — <一句话总结>
      笔记：[[<note_path>]]  图片上传:✅ 图谱更新:✅
```

失败或某步骤未完成时如实标注：

```
[i/N] arXiv:<ID> ❌ 失败 — <失败原因>
[i/N] arXiv:<ID> ✅ 8.5/10 — <总结>  ⚠️ 图片上传:❌ 图谱更新:✅（见子代理返回）
```

> 主会话上下文只累积上面这种一行摘要 + progress.json 状态，**不接收论文正文**。如批次很大（>30 篇）导致主会话上下文偏长，可在循环中阶段性用一句话总结已完成批次（遵循 CLAUDE.md 上下文管理要求）。

处理完当前篇后，取 `pending` 下一篇回到 4.1，直到 `pending` 耗尽。

## 步骤5：批次完成 —— 生成报告

当 `pending` 为空时，输出汇总报告，并将副本写入 `${STATE_DIR}/batch_report.md`：

```markdown
## 批次分析完成

**输入文件**：<txt 路径>
**输出文件夹**：<输出文件夹或"自动推断">
**总计**：N 篇 ｜ ✅ 成功 X 篇 ｜ ❌ 失败 Y 篇

| # | arXiv ID | 状态 | 评分 | 一句话总结 | 笔记位置 | 图片 | 图谱 |
|---|----------|------|------|-----------|----------|------|------|
| 1 | 2402.12345 | ✅ | 8.5/10 | ... | [[...]] | ✅ | ✅ |
| 2 | 2305.20050 | ❌ | - | — | 失败原因：... | — | — |

**失败明细**：
- arXiv:2305.20050 — <失败原因>
```

> `STATE_DIR` 保留作完成记录与防误重跑。若需保留 `batch_report.md` 到 vault，用 Read/Write 复制到 `20_Research/Papers/_batch_reports/batch_<时间>.md`。若需强制重跑整批，删除 `~/.cache/paper-analyze-multi/<hash>/` 后重新执行。

# 错误处理

- **txt 文件不存在** → 解析脚本报错退出，停止。
- **0 篇有效论文** → 停止，展示 `invalid` 列表请用户修正。
- **单篇子代理失败**（下载/分析报错或 JSON 解析失败）→ 记入 `failed`（含原因），继续下一篇，不中断批次。
- **单篇某步骤未完成**（如图片上传失败）→ 仍按 success/failed 归类，但在 `steps_done` 与进度输出中如实标注未完成项，不静默掩盖。
- **`paper-analyze/skill.md` 不存在** → 步骤 0 检查并报错停止。
- **中断续跑** → 重新执行同一命令，从 `progress.json` 读取已 done/failed，自动跳过、从下一篇继续。
- **图片上传 / 图谱更新失败** → 由子代理在执行 skill.md 时按其错误处理规定处理（图谱失败则继续不更新）；本层只如实记录，不重复处理。

# 使用说明

当用户调用 `/paper-analyze-multi <txt文件路径> [输出文件夹]` 时：

## 参数说明

- **txt 文件路径**（必填）：每行一个论文链接的文本文件
- **输出文件夹**（可选）：统一保存子文件夹（相对于 `20_Research/Papers/`）。不指定则每篇自动推断领域。首次指定后被记录，后续可省略。

## 用法示例

```bash
# 全自动跑完整批（每篇在独立子代理中执行，自动上下文重置，无需 /clear）
/paper-analyze-multi /path/to/papers.txt

# 统一保存到指定文件夹
/paper-analyze-multi /path/to/papers.txt 大模型

# 多级文件夹
/paper-analyze-multi /path/to/papers.txt 大模型/LLM_Training
```

## txt 文件示例

```
# 今日待读论文
https://arxiv.org/abs/2402.12345
https://arxiv.org/pdf/2305.20050v2
https://huggingface.co/papers/2410.12345
1706.03762
```

# 重要规则

- **不覆盖原 `paper-analyze` skill**：本 skill 仅做编排，单篇分析由子代理读取 `paper-analyze/skill.md` 执行，不重复实现逻辑。
- **子代理隔离 = 自动 reset**：每篇论文在独立子代理的新上下文中执行，结束即销毁；主会话只回收摘要 JSON。这是"每篇后 reset 上下文"的全自动实现，无需手动 /clear。
- **顺序处理**：一篇子代理返回后再启动下一篇，不并行（满足"依次阅读"且避免知识图谱并发写冲突）。
- **进度持久化可续**：`progress.json` 在磁盘上，中断后重新执行自动从下一篇继续；批次完成后保留 `STATE_DIR` 防误重跑。
- **单篇失败不中断批次**：记录失败原因后继续下一篇；某步骤未完成如实标注，不静默掩盖。
- **解析与业务分离**：链接解析只在 `parse_paper_list.py` 一处完成，下游只消费结构化 arXiv ID。
- **对非法输入 fail fast**：文件缺失 / 0 有效篇立即停止；重复与无效行明示用户，不静默丢弃。
- **不编造**：遵循 `paper-analyze` 的事实性约束，不编造论文数据、虚假链接或未提及的实验。
- **主上下文只保留摘要**：每篇详细笔记落盘到文件，主会话只保留一行进度与 progress 状态，避免堆积。
