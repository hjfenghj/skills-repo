#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
论文列表解析脚本 - 从 txt 文件中提取 arXiv ID 列表。

职责：只做"解析 + 校验"，不做任何下载/分析/写笔记。
配置解析与业务逻辑分离（见 CLAUDE.md 工程规范），本脚本输出结构化 JSON，
上层 skill 据此决定如何处理，不在下游重复解析原始字符串。

输入 txt 格式：每行一个论文链接，支持：
  - https://arxiv.org/abs/2402.12345
  - https://arxiv.org/pdf/2402.12345v2
  - https://arxiv.org/e-print/2402.12345
  - https://huggingface.co/papers/2402.12345
  - arXiv:2402.12345
  - 2402.12345（纯 ID）
  - 老式 ID：cs.AI/0703001
  - 「链接<TAB>标题」格式（如 pwc-paper-list 产出）：只识别行首链接 token，
    其后的标题不参与匹配（标题中的 arXiv 风格数字不会干扰）。
空行与 # 开头的注释行自动忽略。

输出 JSON：
  {
    "input": "...",
    "valid":      [{line_no, arxiv_id, raw}, ...],   # 待处理（已去重）
    "duplicates": [{line_no, arxiv_id, raw}, ...],   # 重复 arXiv ID
    "invalid":    [{line_no, raw, reason}, ...]      # 无法识别
  }
"""

import sys
import re
import json
import argparse
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 新式 arXiv ID：2402.12345 / 2402.12345v2
_ARXIV_NEW_RE = re.compile(r'(\d{4}\.\d{4,5}(?:v\d+)?)')
# 老式 arXiv ID：cs.AI/0703001 / math.PR/0501234
_ARXIV_OLD_RE = re.compile(r'([a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)')


def parse_line(line):
    """解析单行文本，返回 arXiv ID 字符串；无法识别返回 None。

    支持两种行格式：
      - 纯链接行（如 `https://arxiv.org/abs/2402.12345`）
      - 「链接<TAB>标题」行（如 pwc-paper-list 产出）：只取行首第一个空白分隔
        的 token（即链接部分）做识别，其后的标题/备注不参与匹配。这样标题中
        出现的 arXiv 风格数字（如 `2402.12345`）不会误匹配到标题。
    对非法输入 fail-fast：调用方据此归类到 invalid，不在此处静默兜底。
    """
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    # 只识别行首的链接 token，忽略其后可能跟的标题/备注。
    link_token = line.split(None, 1)[0]
    m = _ARXIV_NEW_RE.search(link_token)
    if m:
        return m.group(1)
    m = _ARXIV_OLD_RE.search(link_token)
    if m:
        return m.group(1)
    return None


def parse_file(path):
    """解析整个 txt 文件，返回 (valid, duplicates, invalid) 三个列表。"""
    valid = []
    duplicates = []
    invalid = []
    seen = set()

    p = Path(path)
    if not p.exists():
        logger.error("论文列表文件不存在: %s", p)
        sys.exit(1)

    with p.open('r', encoding='utf-8') as f:
        for i, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            arxiv_id = parse_line(line)
            if not arxiv_id:
                invalid.append({"line_no": i, "raw": line, "reason": "未识别到 arXiv ID"})
                continue
            if arxiv_id in seen:
                duplicates.append({"line_no": i, "arxiv_id": arxiv_id, "raw": line})
                continue
            seen.add(arxiv_id)
            valid.append({"line_no": i, "arxiv_id": arxiv_id, "raw": line})

    return valid, duplicates, invalid


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    parser = argparse.ArgumentParser(description="从 txt 论文列表中提取 arXiv ID（解析+校验）")
    parser.add_argument("input", help="论文列表 txt 文件路径")
    parser.add_argument("--output", default=None,
                        help="输出 JSON 文件路径（默认打印到 stdout）")
    args = parser.parse_args()

    valid, duplicates, invalid = parse_file(args.input)
    result = {
        "input": str(Path(args.input).resolve()),
        "valid": valid,
        "duplicates": duplicates,
        "invalid": invalid,
    }
    out = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(out, encoding='utf-8')
        logger.info("解析完成：有效 %d 篇，重复 %d 行，无效 %d 行 → %s",
                    len(valid), len(duplicates), len(invalid), args.output)
    else:
        print(out)

    if duplicates:
        logger.warning("跳过 %d 行重复 arXiv ID", len(duplicates))
    if invalid:
        logger.warning("存在 %d 行无法解析，详见 invalid 字段", len(invalid))


if __name__ == "__main__":
    main()
