#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将单个子代理返回的结果追加到 progress.json。

职责：只做"提取 JSON + 追加 + 落盘 + 报告下一步"，不含业务逻辑。
子代理的最终消息可能带有额外文字（如"以下是 JSON："），本脚本从中稳健地
提取第一个 JSON 对象；提取失败则按 failed 记录，并保留原始文本用于排查。

用法：
  python append_result.py --progress <progress.json> --result <result.txt> [--parsed <parsed.json>]

输出：done/failed/pending 计数，以及下一篇待处理 arXiv_id（若有）。
"""

import sys
import re
import json
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def strip_ver(arxiv_id):
    """去除 arXiv ID 的版本后缀（如 2508.07917v3 → 2508.07917），用于版本无关的去重匹配。

    parsed.json 保留版本后缀（与用户 txt 一致），而子代理返回的 arxiv_id 通常已去掉版本；
    二者必须按"去掉版本"的方式比较，否则同一篇会被反复判定为 pending。
    """
    if not arxiv_id:
        return arxiv_id
    return re.sub(r'v\d+$', '', arxiv_id)


def extract_json(text):
    """从可能含杂质的文本中提取第一个顶层 JSON 对象。失败返回 None。"""
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    # 截取第一个 { 到最后一个 } 之间
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception as e:
            logger.warning("JSON 解析失败: %s", e)
            return None
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--progress', required=True, help='progress.json 路径')
    p.add_argument('--result', required=True, help='子代理返回的文本文件')
    p.add_argument('--parsed', default=None, help='parsed.json 路径（用于计算 pending）')
    args = p.parse_args()

    progress_path = Path(args.progress)
    if not progress_path.exists():
        logger.error("progress.json 不存在: %s", progress_path)
        sys.exit(1)

    progress = json.loads(progress_path.read_text(encoding='utf-8'))
    raw = Path(args.result).read_text(encoding='utf-8')
    result = extract_json(raw)

    if result is None:
        # 无法解析 → 记 failed，保留原始文本片段
        entry = {"arxiv_id": "unknown", "reason": "子代理返回非 JSON: " + raw[:200]}
        progress["failed"].append(entry)
        logger.warning("无法解析子代理返回，记为 failed（未知 arxiv_id）")
    else:
        status = result.get("status", "failed")
        if status == "success":
            entry = {
                "arxiv_id": result.get("arxiv_id"),
                "title": result.get("title"),
                "score": result.get("score"),
                "summary": result.get("summary"),
                "note_path": result.get("note_path"),
                "steps_done": result.get("steps_done", {}),
            }
            progress["done"].append(entry)
        else:
            progress["failed"].append({
                "arxiv_id": result.get("arxiv_id"),
                "reason": result.get("reason") or "子代理报告 failed",
            })

    progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding='utf-8')

    done_n = len(progress["done"])
    failed_n = len(progress["failed"])
    total = progress.get("total", 0)

    # 计算 pending 与下一篇
    next_id = None
    pending_n = None
    if args.parsed and Path(args.parsed).exists():
        parsed = json.loads(Path(args.parsed).read_text(encoding='utf-8'))
        valid_ids = [v["arxiv_id"] for v in parsed["valid"]]
        done_ids = {strip_ver(d["arxiv_id"]) for d in progress["done"]}
        failed_ids = {strip_ver(f["arxiv_id"]) for f in progress["failed"]}
        pending = [vid for vid in valid_ids if strip_ver(vid) not in done_ids and strip_ver(vid) not in failed_ids]
        pending_n = len(pending)
        next_id = pending[0] if pending else None

    print(json.dumps({
        "done": done_n,
        "failed": failed_n,
        "total": total,
        "pending": pending_n,
        "next_arxiv_id": next_id,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
