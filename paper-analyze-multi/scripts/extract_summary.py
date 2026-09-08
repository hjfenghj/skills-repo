#!/usr/bin/env python
"""Extract a note's own one-line summary (一句话总结) from a paper note.

The orchestrator must not compose --summary from the paper title: the title
alone is not enough to describe the contribution, and a wrong guess ends up in
progress.json / the batch report. The writer subagent already produced an
accurate summary from the full text inside the note's callout block, so read
that back instead.

Usage:
  python extract_summary.py <note.md>            # print summary
  python extract_summary.py <note.md> --score    # also print quality_score
"""
import argparse
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def extract(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()

    summary = ""
    # the note template puts the summary in a callout:
    #   > [!abstract] 一句话总结
    #   > <text>
    m = re.search(r">\s*\[!abstract\][^\n]*\n((?:\s*>[^\n]*\n?)+)", text)
    if m:
        lines = []
        for line in m.group(1).splitlines():
            line = re.sub(r"^\s*>\s?", "", line).strip()
            if line:
                lines.append(line)
        summary = " ".join(lines).strip()

    score = ""
    m = re.search(r'^quality_score:\s*"?\[?([0-9.]+)\]?/10"?', text, re.M)
    if m:
        score = m.group(1)

    return summary, score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("note")
    ap.add_argument("--score", action="store_true", help="also print score on line 2")
    args = ap.parse_args()

    summary, score = extract(args.note)
    if not summary:
        print("ERROR: no 一句话总结 callout found in note", file=sys.stderr)
        return 1
    print(summary)
    if args.score:
        print(score)
    return 0


if __name__ == "__main__":
    sys.exit(main())
