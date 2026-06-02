"""
Obsidian 笔记导出为 HTML（图片内嵌 base64，公式由 KaTeX 渲染）。
适用于：本地预览、浏览器中查看完整效果。

用法:
    python export_for_csdn_html.py                              # 自动搜索最近修改的笔记
    python export_for_csdn_html.py D:\path\to\note.md           # 指定文件
"""

import os
import sys
import re
import base64
import glob
import fitz  # PyMuPDF

VAULT_PAPERS = r"D:\study\obsidian\20_Research\Papers"


# ── 图片处理 ──

def pdf_to_png_base64(pdf_path, dpi=200):
    doc = fitz.open(pdf_path)
    page = doc[0]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    png_bytes = pix.tobytes("png")
    doc.close()
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def image_to_base64(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return pdf_to_png_base64(path)
    elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    return None


# ── Markdown → HTML ──

def md_to_html(md_text):
    """Markdown → HTML，数学公式先保护再转换，最后恢复由 KaTeX 渲染。"""

    # 1) 保护数学公式
    math_blocks = []
    def save_math(m):
        math_blocks.append(m.group(0))
        return f'MATHPLACEHOLDER{len(math_blocks)-1}ENDMATH'

    md_text = re.sub(r'\$\$([\s\S]+?)\$\$', save_math, md_text)
    md_text = re.sub(r'(?<!\$)\$(?!\$)([^\$\n]+?)(?<!\$)\$(?!\$)', save_math, md_text)

    # 2) Obsidian 特殊语法
    md_text = re.sub(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', r'\1', md_text)
    md_text = re.sub(
        r'>\s*\[!(\w+)\]\s*(.+?)(?=\n(?![>])|\Z)',
        lambda m: f'<div class="callout callout-{m.group(1).lower()}">'
                  f'<strong>{m.group(1)}</strong>: {m.group(2)}</div>',
        md_text, flags=re.DOTALL
    )
    md_text = re.sub(r'^>\s?(.+)$', r'<blockquote>\1</blockquote>', md_text, flags=re.MULTILINE)

    # 3) 图片 → <img>
    def replace_img(m):
        alt = m.group(1).split('|')[0] if '|' in m.group(1) else m.group(1)
        src = m.group(2)
        return f'<img src="{src}" alt="{alt}" style="max-width:100%">'
    md_text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_img, md_text)

    # 4) 代码块
    md_text = re.sub(r'```(\w*)\n([\s\S]*?)```', r'<pre><code>\2</code></pre>', md_text)

    # 5) 表格
    def convert_table(m):
        rows = m.group(0).strip().split('\n')
        html_rows = []
        for i, row in enumerate(rows):
            cells = [c.strip() for c in row.strip('|').split('|')]
            if all(set(c.strip()) <= set('-: ') for c in cells):
                continue
            tag = 'th' if i == 0 else 'td'
            html_rows.append('<tr>' + ''.join(f'<{tag}>{c}</{tag}>' for c in cells) + '</tr>')
        return '<table border="1" cellpadding="6" cellspacing="0">' + ''.join(html_rows) + '</table>'
    md_text = re.sub(r'(\|.+\|(?:\n\|[-: |]+\|)*(?:\n\|.+\|)+)', convert_table, md_text)

    # 6) 标题
    for i in range(6, 0, -1):
        md_text = re.sub(rf'^{"#" * i}\s+(.+)$', rf'<h{i}>\1</h{i}>', md_text, flags=re.MULTILINE)

    # 7) 粗体/斜体
    md_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', md_text)
    md_text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', md_text)

    # 8) 行内代码
    md_text = re.sub(r'`([^`]+)`', r'<code>\1</code>', md_text)

    # 9) 水平线
    md_text = re.sub(r'^---+$', '<hr>', md_text, flags=re.MULTILINE)

    # 10) 段落
    md_text = re.sub(r'\n{2,}', '\n</p>\n<p>\n', md_text)
    md_text = '<p>' + md_text + '</p>'

    # 11) 恢复数学公式
    for i, math in enumerate(math_blocks):
        md_text = md_text.replace(f'MATHPLACEHOLDER{i}ENDMATH', math)

    return md_text


# ── 主流程 ──

def process(md_path, output_path=None):
    if output_path is None:
        note_stem = os.path.splitext(os.path.basename(md_path))[0]
        output_path = os.path.join(os.path.dirname(md_path), f"{note_stem}.html")

    note_dir = os.path.dirname(md_path)

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 清理
    content = re.sub(r'^---\n[\s\S]*?\n---\n', '', content)
    content = re.sub(r'%%[\s\S]*?%%', '', content)

    # 替换图片为 base64
    count = 0
    def replace_image(m):
        nonlocal count
        alt, rel_path = m.group(1), m.group(2)
        if rel_path.startswith("data:"):
            return m.group(0)
        abs_path = os.path.normpath(os.path.join(note_dir, rel_path))
        if not os.path.exists(abs_path):
            return m.group(0)
        count += 1
        print(f"  [{count}] {os.path.basename(abs_path)}")
        data_url = image_to_base64(abs_path)
        return f"![{alt}]({data_url})" if data_url else m.group(0)

    content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_image, content)

    html_body = md_to_html(content)

    full_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{os.path.splitext(os.path.basename(md_path))[0]}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
    onload="renderMathInElement(document.body, {
        delimiters: [
            {left: '$$', right: '$$', display: true},
            {left: '$', right: '$', display: false},
            {left: '\\\\(', right: '\\\\)', display: false},
            {left: '\\\\[', right: '\\\\]', display: true}
        ],
        throwOnError: false
    });"></script>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif; max-width: 900px; margin: 20px auto; padding: 20px; line-height: 1.8; color: #333; }
h1 { font-size: 1.8em; border-bottom: 2px solid #eee; padding-bottom: 8px; }
h2 { font-size: 1.5em; border-bottom: 1px solid #eee; padding-bottom: 6px; margin-top: 2em; }
h3 { font-size: 1.2em; margin-top: 1.5em; }
h4 { font-size: 1.05em; }
table { border-collapse: collapse; margin: 1em 0; width: 100%; font-size: 0.95em; }
th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
th { background: #f5f5f5; font-weight: 600; }
img { max-width: 100%; height: auto; margin: 10px 0; display: block; }
blockquote { border-left: 4px solid #ddd; padding: 8px 16px; color: #555; margin: 1em 0; background: #fafafa; }
pre { background: #f6f8fa; padding: 16px; border-radius: 6px; overflow-x: auto; font-size: 0.9em; }
code { background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
pre code { background: none; padding: 0; }
strong { color: #1a1a1a; }
hr { border: none; border-top: 1px solid #eee; margin: 2em 0; }
.callout { padding: 12px 16px; margin: 1em 0; border-radius: 4px; background: #f0f7ff; border-left: 4px solid #0969da; }
.callout-abstract { background: #fff8e1; border-left-color: #f9a825; }
.callout-question { background: #fff3e0; border-left-color: #ef6c00; }
.callout-check { background: #e8f5e9; border-left-color: #2e7d32; }
.callout-tip { background: #e3f2fd; border-left-color: #1565c0; }
.callout-warning { background: #fce4ec; border-left-color: #c62828; }
.callout-success { background: #e8f5e9; border-left-color: #2e7d32; }
.callout-important { background: #ede7f6; border-left-color: #4527a0; }
</style>
</head>
<body>
""" + html_body + """
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\nDone -> {output_path}")
    print(f"Size: {size_kb:.0f} KB | Images: {count}")
    print(f"\nDouble-click to open in browser.")


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        md_path = sys.argv[1]
    else:
        pattern = os.path.join(VAULT_PAPERS, "**", "*.md")
        all_md = glob.glob(pattern, recursive=True)
        all_md = [m for m in all_md if "_csdn" not in m and "csdn_export" not in m and "index" not in m]
        if not all_md:
            print("No .md files found. Pass path as argument.")
            sys.exit(1)
        all_md.sort(key=os.path.getmtime, reverse=True)
        md_path = all_md[0]
        print(f"Auto: {md_path}")

    note_stem = os.path.splitext(os.path.basename(md_path))[0]
    output_path = os.path.join(os.path.dirname(md_path), f"{note_stem}.html")
    process(md_path, output_path)
