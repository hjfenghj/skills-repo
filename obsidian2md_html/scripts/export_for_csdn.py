"""
Obsidian 笔记导出为 CSDN 就绪的 Markdown。
- PDF 图片转为 PNG 存到 csdn_images/ 文件夹
- 数学公式保持 $...$ / $$...$$ 原样，CSDN Markdown 编辑器原生支持
- YAML frontmatter、%% 注释、Obsidian 特殊语法自动清理
- 输出一个干净 .md + 一个图片文件夹

用法:
    python export_for_csdn.py                              # 自动搜索最近修改的笔记
    python export_for_csdn.py D:\path\to\note.md           # 指定文件
"""

import os
import sys
import re
import glob
import fitz  # PyMuPDF

VAULT_PAPERS = r"D:\study\obsidian\20_Research\Papers"


def pdf_to_png(pdf_path, output_path, dpi=200):
    """将 PDF 第一页转为 PNG 文件"""
    doc = fitz.open(pdf_path)
    page = doc[0]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    pix.save(output_path)
    doc.close()
    return output_path


def convert_image(src_path, dst_dir, idx):
    """将图片转为 PNG（如果需要）并复制到目标文件夹，返回新文件名"""
    ext = os.path.splitext(src_path)[1].lower()
    out_name = f"img_{idx:02d}.png"
    out_path = os.path.join(dst_dir, out_name)

    if ext == ".pdf":
        pdf_to_png(src_path, out_path)
    elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        # 直接复制，如果是非 PNG 格式也保留原名
        out_name = f"img_{idx:02d}{ext}"
        out_path = os.path.join(dst_dir, out_name)
        import shutil
        shutil.copy2(src_path, out_path)
    else:
        return None

    return out_name


def process(md_path, output_dir=None):
    """处理 Markdown 文件"""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(md_path), "csdn_export")

    note_dir = os.path.dirname(md_path)
    images_dir = os.path.join(output_dir, "csdn_images")
    os.makedirs(images_dir, exist_ok=True)

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # ── 清理 Obsidian 特殊语法 ──

    # 1) 去 YAML frontmatter
    content = re.sub(r'^---\n[\s\S]*?\n---\n', '', content)

    # 2) 去 %% 注释 %%
    content = re.sub(r'%%[\s\S]*?%%', '', content)

    # 3) Obsidian callout > [!type]\n> content → 普通引用
    def clean_callout(m):
        callout_type = m.group(1)
        body = m.group(2)
        # 把多行 > 前缀去掉
        body = re.sub(r'^>\s?', '', body, flags=re.MULTILINE)
        return f'**[{callout_type}]** {body}'
    content = re.sub(
        r'>\s*\[!(\w+)\]\s*\n((?:>.*\n?)*)',
        clean_callout, content
    )
    # 单行 callout
    content = re.sub(
        r'>\s*\[!(\w+)\]\s*(.+)',
        lambda m: f'**[{m.group(1)}]** {m.group(2)}',
        content
    )

    # 4) Obsidian wikilinks [[xxx|alias]] → alias 或 [[xxx]] → xxx
    content = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', content)
    content = re.sub(r'\[\[([^\]]+)\]\]', r'\1', content)

    # 5) Obsidian 图片 |size 语法: ![alt|800](path) → ![alt](path)
    content = re.sub(r'!\[([^\]|]+)\|([^\]]+)\]', r'![\1]', content)

    # ── 处理图片 ──
    img_count = 0
    img_map = {}  # original_rel_path -> new_filename

    def replace_image(m):
        nonlocal img_count
        alt = m.group(1)
        rel_path = m.group(2)

        # 跳过已经是绝对 URL 的
        if rel_path.startswith("http://") or rel_path.startswith("https://"):
            return m.group(0)

        abs_path = os.path.normpath(os.path.join(note_dir, rel_path))
        if not os.path.exists(abs_path):
            print(f"  [skip] not found: {rel_path}")
            return m.group(0)

        # 已处理过则复用
        if rel_path in img_map:
            return f'![{alt}](csdn_images/{img_map[rel_path]})'

        img_count += 1
        out_name = convert_image(abs_path, images_dir, img_count)
        if out_name is None:
            print(f"  [skip] unsupported format: {abs_path}")
            return m.group(0)

        img_map[rel_path] = out_name
        print(f"  [{img_count}] {os.path.basename(abs_path)} -> csdn_images/{out_name}")
        return f'![{alt}](csdn_images/{out_name})'

    content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_image, content)

    # ── 输出 ──
    note_stem = os.path.splitext(os.path.basename(md_path))[0]
    output_md = os.path.join(output_dir, f"{note_stem}.md")
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\nDone!")
    print(f"  Markdown: {output_md}")
    print(f"  Images:   {images_dir}/ ({img_count} files)")
    print(f"""
=== CSDN 发布步骤 ===
1. 打开 CSDN → 写文章 → 切换到「Markdown 编辑器」
2. 用文本编辑器打开导出的 .md 文件，Ctrl+A 全选 → Ctrl+C
3. 粘贴到 CSDN Markdown 编辑器（公式会自动渲染）
4. 图片位置会显示为 ![](csdn_images/img_XX.png)
   → 在编辑器里点击每个图片位置，拖拽对应的 PNG 文件上传
   → 或者直接把图片路径处的文字删掉，手动插入图片""")


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

    output_dir = os.path.join(os.path.dirname(md_path), "csdn_export")
    process(md_path, output_dir)
