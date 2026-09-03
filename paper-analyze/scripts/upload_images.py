#!/usr/bin/env python3
"""
Upload specified images to Alibaba Cloud OSS for Obsidian notes.
Converts PDF images to PNG, uploads to OSS, and prints URL mappings.

Usage:
    # Upload only specific files
    python upload_images.py --dir <images_dir> --files head.pdf action_grids.pdf

    # Upload all images in directory
    python upload_images.py --dir <images_dir>

Reads OSS config (priority: OSS_* env vars > PicGo's data.json, cross-platform):
    Windows: %APPDATA%/picgo/data.json
    macOS:   ~/Library/Application Support/picgo/data.json
    Linux:   ~/.config/picgo/data.json
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# 共享配置加载器（同目录）：集中解析 env 文件与 OSS 配置
from pa_config import get_oss_config, load_env_file


def convert_pdf_to_png(pdf_path, dpi=200):
    """Convert a PDF page to PNG using PyMuPDF."""
    import fitz

    doc = fitz.open(pdf_path)
    images = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=dpi)
        png_path = tempfile.mktemp(suffix=".png")
        pix.save(png_path)
        images.append((page_num, png_path, pix.width, pix.height))
    doc.close()
    return images


def upload_to_oss(file_path, oss_key, config):
    """Upload a file to Alibaba Cloud OSS."""
    import oss2

    auth = oss2.Auth(config["accessKeyId"], config["accessKeySecret"])
    bucket = oss2.Bucket(
        auth,
        f"https://{config['area']}.aliyuncs.com",
        config["bucket"],
    )

    with open(file_path, "rb") as f:
        bucket.put_object(oss_key, f)

    area = config["area"]
    bucket_name = config["bucket"]
    url = f"https://{bucket_name}.{area}.aliyuncs.com/{oss_key}"
    return url


def upload_single_file(filepath, oss_path_prefix, config):
    """Upload a single file (PDF or image) to OSS. Returns {filename: URL}."""
    url_map = {}
    ext = filepath.suffix.lower()
    img_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    base_stem = filepath.stem

    if ext == ".pdf":
        try:
            pages = convert_pdf_to_png(str(filepath))
            for page_num, png_path, w, h in pages:
                timestamp = f"{now}_{base_stem}"
                if len(pages) > 1:
                    timestamp += f"_p{page_num}"
                oss_key = f"{oss_path_prefix}{timestamp}.png"
                url = upload_to_oss(png_path, oss_key, config)
                map_key = str(filepath.name)
                if len(pages) == 1:
                    url_map[map_key] = url
                else:
                    url_map[f"{map_key}[p{page_num}]"] = url
                os.unlink(png_path)
                print(f"  Uploaded: {filepath.name} (page {page_num}) -> {url}")
        except Exception as e:
            print(f"  SKIP (PDF conversion failed): {filepath.name} - {e}", file=sys.stderr)

    elif ext in img_exts:
        try:
            timestamp = f"{now}_{base_stem}"
            oss_key = f"{oss_path_prefix}{timestamp}{ext}"
            url = upload_to_oss(str(filepath), oss_key, config)
            url_map[str(filepath.name)] = url
            print(f"  Uploaded: {filepath.name} -> {url}")
        except Exception as e:
            print(f"  SKIP (upload failed): {filepath.name} - {e}", file=sys.stderr)

    else:
        print(f"  SKIP (unsupported format): {filepath.name}", file=sys.stderr)

    return url_map


def process_images(images_dir, filenames=None, prefix=None):
    """Process images: convert PDFs, upload to OSS, return URL mappings.

    Args:
        images_dir: Directory containing images
        filenames: Optional list of specific filenames to upload.
                   If None, uploads all supported images in the directory.
        prefix: OSS path prefix override
    """
    config = get_oss_config()
    oss_path_prefix = config.get("path", "obsidian-img/")
    if prefix:
        oss_path_prefix = prefix

    url_map = {}
    images_dir = Path(images_dir)

    if filenames:
        # Upload only specified files
        for fname in filenames:
            filepath = images_dir / fname
            if not filepath.exists():
                print(f"  SKIP (not found): {fname}", file=sys.stderr)
                continue
            url_map.update(upload_single_file(filepath, oss_path_prefix, config))
    else:
        # Upload all supported files in directory
        img_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
        for filepath in sorted(images_dir.iterdir()):
            if filepath.is_dir():
                continue
            if filepath.suffix.lower() not in img_exts | {".pdf"}:
                continue
            url_map.update(upload_single_file(filepath, oss_path_prefix, config))

    return url_map


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Upload images to OSS for Obsidian notes")
    parser.add_argument("--dir", required=True, help="Directory containing images")
    parser.add_argument("--files", nargs="*", default=None,
                        help="Specific filenames to upload (default: upload all)")
    parser.add_argument("--prefix", default=None, help="OSS path prefix (default: from PicGo config)")
    parser.add_argument("--output", default=None, help="Output JSON file for URL mappings (default: print to stdout)")
    args = parser.parse_args()

    if not os.path.isdir(args.dir):
        print(f"ERROR: Directory not found: {args.dir}", file=sys.stderr)
        sys.exit(1)

    if args.files:
        print(f"Uploading {len(args.files)} specified images from: {args.dir}")
    else:
        print(f"Uploading all images from: {args.dir}")

    url_map = process_images(args.dir, args.files, args.prefix)

    if not url_map:
        print("No images uploaded.", file=sys.stderr)
        sys.exit(0)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(url_map, f, indent=2, ensure_ascii=False)
        print(f"\nURL mappings saved to: {args.output}")
    else:
        print("\n--- URL Mappings ---")
        print(json.dumps(url_map, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
