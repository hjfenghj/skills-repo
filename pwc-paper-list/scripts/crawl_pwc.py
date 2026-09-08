#!/usr/bin/env python3
"""
Crawl a paperswithcode.co conference paper list and write each paper's
arXiv link + title (one per line, tab-separated) to a txt file.

paperswithcode.co is a JS-rendered SPA, so the paper list is fetched from
its internal JSON API instead of scraping HTML:

    GET https://paperswithcode.co/api/v1/conferences/<conf>/papers
        ?page=<N>&task=<task>&order_by=trending&order_dir=desc&page_size=12

The sort params mirror the website's `ConferenceTaskView` defaults
(no `?order_by=` in the URL -> "trending", desc), so the output order
matches what you see on the page. If the input URL carries `?order_by=`
/ `?order_dir=` (set by the website's sort dropdown), those are honored.

Output root directory is controlled by the environment variable
`PAPER_LIST_ROOT`. Resolution order (highest first):
    1. PAPER_LIST_ROOT already in the shell environment
    2. ~/.claude/skills/pwc-paper-list/config/pwc-paper-list.env  (KEY=VALUE)
    3. Default: ~/paper-list
The output file is named `<conf>_<task>.txt` (or `<conf>.txt` when no task
is given).

Usage:
    python crawl_pwc.py <paperswithcode_url> [options]

Examples:
    python crawl_pwc.py https://paperswithcode.co/conferences/icra-2026/robotics
    python crawl_pwc.py https://paperswithcode.co/conferences/icra-2026
    python crawl_pwc.py https://paperswithcode.co/conferences/icra-2026/robotics?order_by=date_published
"""

import argparse
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests

API_BASE = "https://paperswithcode.co/api/v1/conferences"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
# Match the website's ConferenceTaskView defaults so output order equals
# what you see when browsing the page with no ?order_by= in the URL.
DEFAULT_ORDER_BY = "trending"
DEFAULT_ORDER_DIR = "desc"
DEFAULT_PAGE_SIZE = 12
# Cross-platform default output root (user home), overridable via
# PAPER_LIST_ROOT env var or the skill's config/pwc-paper-list.env.
DEFAULT_OUTPUT_ROOT = os.path.join(str(Path.home()), "paper-list")
SKILL_ENV_FILE = (Path.home() / ".claude" / "skills" / "pwc-paper-list"
                  / "config" / "pwc-paper-list.env")


def load_env_file():
    """Load KEY=VALUE pairs from the skill's .env file into os.environ.

    Real environment variables always win (setdefault). This is the only
    place the .env format is parsed (single parse point).
    """
    if not SKILL_ENV_FILE.exists():
        return
    with open(SKILL_ENV_FILE, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                print(f"[warn] skipping malformed env line "
                      f"({SKILL_ENV_FILE}:{lineno}): {raw!r}", file=sys.stderr)
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            if key:
                os.environ.setdefault(key, value)

VALID_ORDER_BY = {"trending", "date_published", "citation_count"}
VALID_ORDER_DIR = {"desc", "asc"}

# The website treats some second-path-segments as a *presentation* filter
# (sent as `presentation=` to the API) rather than a task. Anything not in
# this map is treated as a normal task slug. `all` shows every paper
# (no task, no presentation). Values are the API's presentation param.
# (Mirrors ConferenceTaskView: oral/spotlight/outstanding/best-paper-finalists.)
PRESENTATION_SLUGS = {
    "oral": "oral",
    "spotlight": "spotlight",
    "outstanding": "outstanding",
    "best-paper-finalists": "best_paper_finalist",
    "all": None,
}


def parse_input_url(url: str):
    """Parse a paperswithcode.co conference URL.

    Returns (conf, segment, task, presentation, order_by, order_dir):
      - segment: raw second path segment (used for output filename), or None
      - task: API `task` param, or None
      - presentation: API `presentation` param, or None
        (segment is a presentation slug -> presentation set, task None;
         otherwise segment is a task slug -> task set, presentation None)

    Accepted shapes:
        /conferences/<conf>
        /conferences/<conf>/<task>          e.g. /icra-2026/robotics
        /conferences/<conf>/<presentation>  e.g. /iclr-2026/oral
        /conferences/<conf>/<seg>?order_by=...&order_dir=...
    """
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if "conferences" not in parts:
        raise ValueError(
            f"URL does not look like a paperswithcode conference page: {url}\n"
            f"Expected path: /conferences/<conf>[/<task-or-presentation>]"
        )
    idx = parts.index("conferences")
    if idx + 1 >= len(parts):
        raise ValueError(f"Conference slug missing in URL: {url}")
    conf = parts[idx + 1]
    segment = parts[idx + 2] if idx + 2 < len(parts) else None

    if segment is not None and segment in PRESENTATION_SLUGS:
        task = None
        presentation = PRESENTATION_SLUGS[segment]
    else:
        task = segment
        presentation = None

    qs = parse_qs(parsed.query)
    order_by = (qs.get("order_by", [DEFAULT_ORDER_BY])[0]).lower()
    order_dir = (qs.get("order_dir", [DEFAULT_ORDER_DIR])[0]).lower()
    if order_by not in VALID_ORDER_BY:
        print(f"[warn] unknown order_by={order_by!r}, falling back to "
              f"{DEFAULT_ORDER_BY!r}", file=sys.stderr)
        order_by = DEFAULT_ORDER_BY
    if order_dir not in VALID_ORDER_DIR:
        print(f"[warn] unknown order_dir={order_dir!r}, falling back to "
              f"{DEFAULT_ORDER_DIR!r}", file=sys.stderr)
        order_dir = DEFAULT_ORDER_DIR
    return conf, segment, task, presentation, order_by, order_dir


def fetch_page(conf: str, task: str | None, presentation: str | None,
               order_by: str, order_dir: str,
               page_size: int, page: int, timeout: float = 30.0) -> dict:
    params = {
        "page": page,
        "order_by": order_by,
        "order_dir": order_dir,
        "page_size": page_size,
    }
    # Exactly one of task / presentation is set (never both): a path segment
    # is either a task slug or a presentation slug, per ConferenceTaskView.
    if task:
        params["task"] = task
    if presentation:
        params["presentation"] = presentation
    resp = requests.get(f"{API_BASE}/{conf}/papers", headers=HEADERS,
                        params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def iter_all_papers(conf: str, task: str | None, presentation: str | None,
                    order_by: str, order_dir: str,
                    page_size: int, request_delay: float = 0.5):
    """Yield paper dicts from every page, following `next_page`."""
    page = 1
    total_seen = 0
    while True:
        data = fetch_page(conf, task, presentation, order_by, order_dir,
                          page_size, page)
        results = data.get("results", [])
        if not results:
            break
        for paper in results:
            yield paper
            total_seen += 1
        count = data.get("count")
        next_page = data.get("next_page")
        if count is not None:
            label = f"{conf}" + (f"/{task or presentation}" if (task or presentation) else "")
            print(f"[page {page}] {label}: got {len(results)} papers "
                  f"({total_seen}/{count})", file=sys.stderr)
        if next_page is None:
            break
        page = next_page
        if request_delay:
            time.sleep(request_delay)


def extract_arxiv_entry(paper: dict) -> tuple[str, str] | None:
    """Return (arxiv_abs_url, title) for a paper, or None if it has none.

    Papers without an arXiv version have `url_abs` pointing at the IEEE
    papercept system instead — those are filtered out here.
    """
    arxiv_id = paper.get("arxiv_id")
    if arxiv_id:
        url = f"https://arxiv.org/abs/{arxiv_id}"
    else:
        url_abs = paper.get("url_abs") or ""
        if "arxiv.org" not in url_abs:
            return None
        url = url_abs
    title = (paper.get("title") or "").strip()
    return url, title


def resolve_output_path(conf: str, segment: str | None, output_root: str,
                        output_override: str | None) -> str:
    if output_override:
        return output_override
    # `or` (not `, default`): an empty-string PAPER_LIST_ROOT (as shipped in the
    # .env template) must fall back to the default root, not the empty cwd.
    root = os.environ.get("PAPER_LIST_ROOT") or output_root
    name = f"{conf}_{segment}.txt" if segment else f"{conf}.txt"
    return os.path.join(root, name)


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", help="paperswithcode.co conference URL")
    parser.add_argument(
        "-o", "--output", default=None,
        help="Output txt file path. Overrides the default "
             "<PAPER_LIST_ROOT>/<conf>_<task>.txt naming.",
    )
    parser.add_argument(
        "--order-by", default=None, choices=sorted(VALID_ORDER_BY),
        help="Sort key — overrides the URL's ?order_by= (default: trending).",
    )
    parser.add_argument(
        "--order-dir", default=None, choices=sorted(VALID_ORDER_DIR),
        help="Sort direction — overrides the URL's ?order_dir= (default: desc).",
    )
    parser.add_argument(
        "--page-size", type=int, default=DEFAULT_PAGE_SIZE,
        help=f"Items per API page (default: {DEFAULT_PAGE_SIZE}, matches website). "
             f"Does not affect final order, only request count.",
    )
    parser.add_argument(
        "--delay", type=float, default=0.5,
        help="Seconds to sleep between page requests (default: 0.5).",
    )
    parser.add_argument(
        "--output-root", default=DEFAULT_OUTPUT_ROOT,
        help=f"Default output root if PAPER_LIST_ROOT env var is unset "
             f"(default: {DEFAULT_OUTPUT_ROOT}).",
    )
    args = parser.parse_args()

    conf, segment, task, presentation, url_order_by, url_order_dir = parse_input_url(args.url)
    order_by = args.order_by or url_order_by
    order_dir = args.order_dir or url_order_dir
    label = f"{conf}" + (f"/{task or presentation}" if (task or presentation) else "")
    print(f"[info] conference={label} order_by={order_by} order_dir={order_dir} "
          f"page_size={args.page_size}", file=sys.stderr)

    entries = []
    total_seen = 0
    for paper in iter_all_papers(conf, task, presentation, order_by, order_dir,
                                 args.page_size, args.delay):
        total_seen += 1
        entry = extract_arxiv_entry(paper)
        if entry:
            entries.append(entry)

    # De-duplicate by arXiv URL while preserving order.
    seen = set()
    unique = []
    for url, title in entries:
        if url not in seen:
            seen.add(url)
            unique.append((url, title))

    out_path = resolve_output_path(conf, segment, args.output_root, args.output)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for url, title in unique:
            clean_title = " ".join(title.split())  # keep one paper per line
            f.write(f"{url}\t{clean_title}\n")

    filtered = total_seen - len(entries)
    dupes = len(entries) - len(unique)
    print(
        f"\nDone. {label}: {total_seen} papers on the page -> "
        f"{len(unique)} arXiv links written "
        f"({filtered} non-arXiv filtered, {dupes} duplicates removed) to:\n"
        f"{out_path}",
        file=sys.stderr,
    )
    # Echo the final path on stdout for easy capture by the skill caller.
    print(out_path)


if __name__ == "__main__":
    main()
