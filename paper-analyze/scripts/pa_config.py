#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paper-analyze 共享配置加载器 / Shared config loader for the paper-analyze skill.

集中处理所有环境变量与配置文件解析，供 generate_note.py / update_graph.py /
upload_images.py 共用。解析优先级（高 → 低）：

1. CLI 参数（各脚本自行处理）
2. 进程环境变量（shell 已导出，或 Claude Code 注入）
3. skill 目录下的 config/paper-analyze.env 文件（install.sh 生成）

这样无论 skill 是被 /paper-analyze 调用（skill.md 会先 source 该 env 文件），
还是脚本被单独手动调用，配置都一致，且真实环境变量始终优先于文件。
"""

import json
import os
import sys
from pathlib import Path

# skill 根目录 = 本文件所在 scripts/ 的上一级
SKILL_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = SKILL_DIR / "config" / "paper-analyze.env"


def load_env_file():
    """若存在 config/paper-analyze.env，则将其中的 KEY=VALUE 载入 os.environ。

    - 已存在于环境中的变量不会被覆盖（真实环境变量优先）。
    - 忽略空行与 # 注释；去除值两侧的成对引号。
    - 非注释、非空但缺少 '=' 的行视为格式错误，打印警告并跳过（不中断）。
    """
    if not ENV_FILE.exists():
        return
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                print(f"[pa_config] 跳过格式错误的行 ({ENV_FILE}:{lineno}): {raw!r}",
                      file=sys.stderr)
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            if key:
                os.environ.setdefault(key, value)


def get_vault_path(cli_vault=None):
    """返回 Obsidian vault 根路径。优先 CLI 参数，其次环境变量，最后 fail-fast 退出。"""
    if cli_vault:
        return cli_vault
    env_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    if env_path:
        return env_path
    print(
        "[pa_config] 未指定 Obsidian vault 路径。\n"
        "  请在 config/paper-analyze.env 中设置 OBSIDIAN_VAULT_PATH，\n"
        "  或通过 --vault 参数 / 环境变量提供。",
        file=sys.stderr,
    )
    sys.exit(2)


def _picgo_config_path():
    """跨平台定位 PicGo 的 data.json。可用 PICGO_CONFIG_PATH 环境变量显式覆盖。"""
    override = os.environ.get("PICGO_CONFIG_PATH")
    if override:
        return Path(override)
    home = Path.home()
    if sys.platform == "darwin":
        # PicGo 在 macOS 上的目录名大小写因版本而异，两个都试一下
        for cand in (home / "Library" / "Application Support" / "picgo" / "data.json",
                     home / "Library" / "Application Support" / "PicGo" / "data.json"):
            if cand.exists():
                return cand
        return home / "Library" / "Application Support" / "picgo" / "data.json"
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "picgo" / "data.json"
    return home / ".config" / "picgo" / "data.json"


def get_oss_config():
    """返回阿里云 OSS 配置字典，键与 PicGo 的 aliyun 配置一致：
    accessKeyId / accessKeySecret / bucket / area / path。

    优先级：
    1. OSS_* 环境变量（显式覆盖，推荐跨机器迁移时使用）
    2. PicGo data.json 中的 aliyun 配置（自动跨平台定位）
    3. 都没有则 fail-fast 退出。
    """
    ak = os.environ.get("OSS_ACCESS_KEY_ID")
    sk = os.environ.get("OSS_ACCESS_KEY_SECRET")
    bucket = os.environ.get("OSS_BUCKET")
    area = os.environ.get("OSS_AREA")
    path = os.environ.get("OSS_PATH", "obsidian-img/")
    if ak and sk and bucket and area:
        return {
            "accessKeyId": ak,
            "accessKeySecret": sk,
            "bucket": bucket,
            "area": area,
            "path": path,
        }

    picgo_path = _picgo_config_path()
    if picgo_path.exists():
        try:
            with open(picgo_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"[pa_config] 读取 PicGo 配置失败 ({picgo_path}): {e}",
                  file=sys.stderr)
            config = {}
        aliyun = config.get("picBed", {}).get("aliyun", {})
        if aliyun.get("accessKeyId"):
            aliyun.setdefault("path", "obsidian-img/")
            return aliyun

    print(
        "[pa_config] 未找到 OSS 配置。图片上传（步骤6）需要 OSS 凭证。\n"
        "  方式一：在 config/paper-analyze.env 中设置\n"
        "    OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET / OSS_BUCKET / OSS_AREA [/ OSS_PATH]\n"
        "  方式二：安装并配置 PicGo（阿里云图床），脚本会自动读取其 data.json。",
        file=sys.stderr,
    )
    sys.exit(3)
