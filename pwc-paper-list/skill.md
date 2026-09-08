---
name: pwc-paper-list
description: 抓取 paperswithcode.co 会议论文列表的 arXiv 链接与标题，逐行写入 txt 文件（链接<TAB>标题，仅含 arXiv 论文，按网页 trending 默认顺序）。输入一个会议/任务链接，输出一个 txt / Crawl a paperswithcode.co conference paper list and write each paper's arXiv link + title (one per line, tab-separated, arXiv-only, website trending order) to a txt file. Input: one conference/task URL; Output: one txt file.
allowed-tools: Bash, Read
---

# pwc-paper-list

抓取 **paperswithcode.co** 上某个会议（可带任务/方向）的论文列表，把每篇论文的 **arXiv 链接 + 标题**逐行写进一个 txt 文件（格式：`arxiv链接<TAB>标题`，仅保留有 arXiv 版本的论文，顺序与网页一致）。

> 与 `conference-papers`（OpenReview 抓取 + 生成简述）和 `paper-analyze-multi`（读 txt 批量深度分析）职责不同：本 skill 只负责**把网页论文列表落盘成 txt**，可直接作为 `paper-analyze-multi` 的输入。

# 调用方式

```
/pwc-paper-list <paperswithcode 会议链接>
```

示例：
```
/pwc-paper-list https://paperswithcode.co/conferences/icra-2026/robotics
/pwc-paper-list https://paperswithcode.co/conferences/icra-2026
/pwc-paper-list https://paperswithcode.co/conferences/icra-2026/robotics?order_by=date_published
/pwc-paper-list https://paperswithcode.co/conferences/iclr-2026/oral
```

第二段路径既可以是 **任务**（如 `robotics`、`agents`、`world-models`），也可以是 **展示类型**（`oral`/`spotlight`/`outstanding`/`best-paper-finalists`/`all`）。脚本会自动区分：任务发 `task=` 参数，展示类型发 `presentation=` 参数（与网页 `ConferenceTaskView` 逻辑一致）。

# 输出位置（环境变量控制）

输出根目录由环境变量 **`PAPER_LIST_ROOT`** 控制，解析优先级（高 → 低）：

1. shell 里已 `export` 的 `PAPER_LIST_ROOT`（临时覆盖）
2. `~/.claude/skills/pwc-paper-list/config/pwc-paper-list.env` 里的 `PAPER_LIST_ROOT=`（永久设置，install.sh 生成）
3. 默认 `~/paper-list`

- 有 task：`$PAPER_LIST_ROOT/<conf>_<task>.txt`，如 `~/paper-list/icra-2026_robotics.txt`
- 无 task：`$PAPER_LIST_ROOT/<conf>.txt`，如 `~/paper-list/icra-2026.txt`

临时覆盖（当前会话）：
```bash
export PAPER_LIST_ROOT="/path/to/paper-list"
```
永久覆盖：编辑 `~/.claude/skills/pwc-paper-list/config/pwc-paper-list.env`。

# 执行步骤

调用本 skill 时，**直接运行脚本**（脚本本身完成 env 加载、URL 解析、抓取、写文件，无需额外编排）：

```bash
python "$HOME/.claude/skills/pwc-paper-list/scripts/crawl_pwc.py" "<用户给的URL>"
```

脚本：
1. 从 URL 解析 `conf` / `task`（以及可选的 `?order_by=` / `?order_dir=`）。
2. 调内部 JSON API `https://paperswithcode.co/api/v1/conferences/<conf>/papers`，按网页默认 `order_by=trending&order_dir=desc&page_size=12` 翻页抓取（与网页顺序一致；URL 带 `?order_by=` 时优先用 URL 的）。
3. 只保留有 arXiv 版本的论文，去重，按网页顺序写 `链接<TAB>标题` 每行一条。
4. 进度打印到 stderr，**最终 txt 路径打印到 stdout 最后一行**。

可选 CLI 参数（一般不需要）：
- `--order-by {trending|date_published|citation_count}`：覆盖排序（trending=热门默认，date_published=最新，citation_count=最多引用）
- `--order-dir {desc|asc}`：覆盖方向
- `-o <路径>`：自定义输出文件路径（覆盖默认命名）
- `--page-size N`、`--delay <秒>`：分页/限速调节

# 输出格式

每行一条，tab 分隔，便于人读与下游解析：

```
https://arxiv.org/abs/2508.07917	MolmoAct: Action Reasoning Models that can Reason in Space
https://arxiv.org/abs/2509.15212	RynnVLA-001: Using Human Demonstrations to Improve Robot Manipulation
```

下游兼容性：`paper-analyze-multi` 的 `parse_paper_list.py` 用 `re.search` 在整行抓 arXiv ID，行尾追加标题不影响识别，可直接喂给 `/paper-analyze-multi <此txt>`。

# 完成后向用户报告

1. 抓取的会议/任务、排序方式、论文总数与写入条数（非 arXiv 过滤、去重数量）。
2. 输出 txt 的**绝对路径**。
3. 一句提示：可直接 `/paper-analyze-multi <路径>` 进入批量深度分析。

# 注意事项

- 该网站是 JS 单页应用，**不能抓 HTML**；必须走内部 JSON API（脚本已处理）。
- 无 arXiv 版本的论文（`url_abs` 指向 IEEE papercept）会被过滤，不写入 txt。
- 排序默认 trending（与网页默认一致）；如用户在网页切换过排序，把带 `?order_by=` 的完整链接贴进来即可复现顺序。
- 对非法 URL / 0 篇结果 fail fast，向用户报错而非静默写空文件。
