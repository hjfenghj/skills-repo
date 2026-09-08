#!/usr/bin/env python3
"""Replace local images/xxx refs in a paper note with uploaded OSS URLs.

Companion to paper-analyze's upload_images.py. Doing the substitution here
rather than via many Edit calls avoids the response output-token limit that
truncates large-note edits.

Usage:
    python replace_image_urls.py --note <note.md> --urls <mapping.json>

Exits non-zero if any local images/ ref remains unmapped (fail fast).
"""
import argparse
import json
import os
import re
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--note", required=True, help="Path to the note .md file")
    ap.add_argument("--urls", required=True,
                    help="JSON mapping {filename: oss_url} from upload_images.py")
    args = ap.parse_args()

    with open(args.urls, encoding="utf-8") as f:
        mapping = json.load(f)

    with open(args.note, encoding="utf-8") as f:
        text = f.read()

    original = text
    replaced = {}
    for fname, url in mapping.items():
        # match images/<fname> inside a markdown link, tolerating ./ prefix
        pattern = re.compile(r"(?:\./)?images/" + re.escape(fname))
        text, n = pattern.subn(url, text)
        if n:
            replaced[fname] = n

    # PDF figures are converted to .png on upload; the note may still cite .pdf
    for fname, url in mapping.items():
        stem, ext = os.path.splitext(fname)
        if ext.lower() != ".png":
            continue
        for alt_ext in (".pdf", ".jpg", ".jpeg"):
            pattern = re.compile(r"(?:\./)?images/" + re.escape(stem + alt_ext))
            text, n = pattern.subn(url, text)
            if n:
                replaced[stem + alt_ext] = replaced.get(stem + alt_ext, 0) + n

    leftover = sorted(set(re.findall(r"(?:\./)?images/([^\s)\]\"']+)", text)))

    if text != original:
        # atomic write: avoids a truncated note if this is interrupted
        tmp = args.note + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, args.note)

    for fname, n in sorted(replaced.items()):
        print(f"  replaced {n}x: images/{fname}")
    print(f"total refs replaced: {sum(replaced.values())}")

    if leftover:
        print(f"ERROR: unmapped local image refs remain: {leftover}", file=sys.stderr)
        return 1
    print("OK: no local images/ refs remain")
    return 0


if __name__ == "__main__":
    sys.exit(main())
