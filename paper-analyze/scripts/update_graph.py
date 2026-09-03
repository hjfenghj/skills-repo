#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新知识图谱脚本
"""

import json
import os
import sys
import argparse
import logging
from datetime import datetime

# 共享配置加载器（同目录）：集中解析 env 文件与 OBSIDIAN_VAULT_PATH
from pa_config import get_vault_path, load_env_file

logger = logging.getLogger(__name__)


def main():
    load_env_file()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
    )

    parser = argparse.ArgumentParser(description='更新知识图谱 / Update knowledge graph')
    parser.add_argument('--paper-id', type=str, required=True, help='论文 arXiv ID / Paper arXiv ID')
    parser.add_argument('--title', type=str, required=True, help='论文标题 / Paper title')
    parser.add_argument('--domain', type=str, required=True, help='论文领域 / Paper domain')
    parser.add_argument('--score', type=float, default=0.0, help='质量评分 / Quality score')
    parser.add_argument('--related', type=str, nargs='*', default=[], help='相关论文ID列表 / Related paper IDs')
    parser.add_argument('--vault', type=str, default=None, help='Obsidian vault 路径 / Obsidian vault path')
    parser.add_argument('--language', type=str, default='zh', choices=['zh', 'en'], help='语言 / Language: zh (中文) or en (English)')
    args = parser.parse_args()

    vault_root = get_vault_path(args.vault)
    date = datetime.now().strftime("%Y-%m-%d")

    graph_dir = os.path.join(vault_root, "20_Research", "PaperGraph")
    os.makedirs(graph_dir, exist_ok=True)
    graph_path = os.path.join(graph_dir, "graph_data.json")

    try:
        with open(graph_path, 'r', encoding='utf-8') as f:
            graph = json.load(f)
    except FileNotFoundError:
        graph = {
            "nodes": [],
            "edges": [],
            "last_updated": date
        }

    try:
        year = int(date[:4])
    except (ValueError, IndexError):
        year = datetime.now().year

    # Language-aware tags
    if args.language == "zh":
        tags = ["论文笔记", args.domain]
    else:
        tags = ["paper-notes", args.domain]

    paper_node = {
        "id": args.paper_id,
        "title": args.title,
        "year": year,
        "domain": args.domain,
        "quality_score": args.score,
        "tags": tags,
        "analyzed": True
    }

    # 兼容 dict 格式和 list 格式的 nodes
    nodes_container = graph.get("nodes", {})
    if isinstance(nodes_container, dict):
        # dict 格式：key 为 paper_id，value 为节点数据
        node_key = f"arXiv:{args.paper_id}" if not args.paper_id.startswith("arXiv:") else args.paper_id
        if node_key in nodes_container:
            nodes_container[node_key].update(paper_node)
        else:
            nodes_container[node_key] = paper_node
        graph["nodes"] = nodes_container
        node_count = len(nodes_container)
    elif isinstance(nodes_container, list):
        # list 格式
        existing_nodes = {
            node.get("id"): i
            for i, node in enumerate(nodes_container)
            if isinstance(node, dict) and node.get("id")
        }
        if args.paper_id in existing_nodes:
            nodes_container[existing_nodes[args.paper_id]].update(paper_node)
        else:
            nodes_container.append(paper_node)
        graph["nodes"] = nodes_container
        node_count = len(nodes_container)
    else:
        # 未知格式，重新初始化为 dict
        node_key = f"arXiv:{args.paper_id}" if not args.paper_id.startswith("arXiv:") else args.paper_id
        graph["nodes"] = {node_key: paper_node}
        node_count = 1

    if args.related:
        # 安全构建边索引（跳过无 source/target 的边）
        existing_edges = {
            (edge.get("source"), edge.get("target"))
            for edge in graph["edges"]
            if edge.get("source") and edge.get("target")
        }
        for related_id in args.related:
            # 防止自引用
            if related_id and related_id != args.paper_id and (args.paper_id, related_id) not in existing_edges:
                graph["edges"].append({
                    "source": args.paper_id,
                    "target": related_id,
                    "type": "related",
                    "weight": 0.7
                })

    graph["last_updated"] = date

    try:
        with open(graph_path, 'w', encoding='utf-8') as f:
            json.dump(graph, f, ensure_ascii=False, indent=2)
    except (IOError, TypeError) as e:
        logger.error("写入图谱失败: %s", e)
        sys.exit(1)

    if args.language == "zh":
        print(f"图谱已更新: {graph_path}")
        print(f"节点数: {node_count}")
        print(f"边数: {len(graph.get('edges', []))}")
    else:
        print(f"Graph updated: {graph_path}")
        print(f"Nodes: {node_count}")
        print(f"Edges: {len(graph.get('edges', []))}")


if __name__ == '__main__':
    main()
