---
name: obsidian2md_html
description: 将 Obsidian 笔记导出为 CSDN 就绪的 Markdown 或带公式渲染的 HTML 预览文件
allowed-tools: Bash, Read, Write, Glob, Grep
---

# Obsidian 笔记导出工具

将 Obsidian 笔记导出为两种格式，用于 CSDN 发布或本地预览。

## 参数格式

```
/obsidian2md_html <note_path> [--mode html|md]
```

- `note_path`：Obsidian 笔记的 .md 文件路径（必填）
- `--mode`：导出模式（可选，默认 `md`）
  - `md`：输出干净的 Markdown + PNG 图片文件夹，用于 CSDN Markdown 编辑器
  - `html`：输出单文件 HTML（图片 base64 内嵌，KaTeX 渲染公式），用于本地浏览器预览

## 脚本位置

脚本位于本 skill 的 `scripts/` 目录下：

- Markdown 模式：`scripts/export_for_csdn.py`
- HTML 模式：`scripts/export_for_csdn_html.py`

Base directory 为 `C:\Users\daolin.Qi\.claude\skills\obsidian2md_html`。

## 执行逻辑

1. 解析用户输入，提取 `note_path` 和 `--mode` 参数
2. 验证文件路径存在
3. 根据 mode 调用对应脚本（使用 skill base directory 的相对路径）：
   - `md` 模式：`python C:\Users\daolin.Qi\.claude\skills\obsidian2md_html\scripts\export_for_csdn.py <note_path>`
   - `html` 模式：`python C:\Users\daolin.Qi\.claude\skills\obsidian2md_html\scripts\export_for_csdn_html.py <note_path>`
4. 报告输出结果和后续使用方法

## 两种模式说明

### md 模式（发 CSDN）
- 输出：`csdn_export/<笔记名>.md` + `csdn_export/csdn_images/*.png`
- 输出文件名与输入笔记文件名一致（例如输入 `VLingNav.md` → 输出 `VLingNav.md`）
- 公式保持 `$...$` / `$$...$$` 原样，CSDN Markdown 编辑器原生渲染
- 图片转存为 PNG，需在 CSDN 编辑器里手动拖拽上传
- 用法：CSDN → 写文章 → Markdown 编辑器 → 粘贴 md 内容 → 拖拽上传图片

### html 模式（本地预览）
- 输出：`<笔记名>.html`（单文件，所有内容自包含）
- 输出文件名与输入笔记文件名一致（例如输入 `VLingNav.md` → 输出 `VLingNav.html`）
- 图片内嵌为 base64，公式由 KaTeX CDN 渲染（需联网）
- 双击即可在浏览器中查看完整效果
- 用法：双击 html 文件 → 浏览器中查看

## 示例

```
/obsidian2md_html D:\study\obsidian\20_Research\Papers\自动驾驶\Scaling-Award*\Scaling-Award*.md
/obsidian2md_html D:\study\obsidian\20_Research\Papers\智能体\VLingNav\VLingNav.md --mode html
```

## 错误处理

- 文件路径不存在时提示用户检查
- 脚本执行失败时显示 stderr 内容
- 中文路径会通过 glob 自动处理
