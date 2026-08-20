---
name: html-cover-epub
description: 把 WordPress 博客 XML 导出 / HTML 文档集转换为标准 EPUB3 电子书 — 去除失效媒体、自动段落化、XML 合法化、生成带分类两级目录的电子书
argument-hint: ["<xml或html> [-o 输出.epub] [-t 书名] [-a 作者]"]
---

# /html-cover-epub

将 WordPress WXR XML 博客导出（或 HTML 博客文档集）转换为标准 EPUB3 电子书，按分类生成两级目录，去除已失效的图片和嵌入媒体。

## 使用方式

```bash
# 从 WordPress XML 导出直接转换（推荐，含完整分类/日期元数据）
python3 ~/.claude/skills/html-cover-epub/scripts/html_cover_epub.py \
    blog-export.xml -t "书名" -a "作者"

# 指定输出路径
python3 ~/.claude/skills/html-cover-epub/scripts/html_cover_epub.py \
    blog-export.xml -o /path/to/输出.epub -t "书名" -a "作者"
```

### 参数

| 参数 | 说明 |
|------|------|
| `xml` | WordPress WXR 导出 XML 文件（必填） |
| `-o, --out` | 输出 epub 路径，默认与 xml 同名 `.epub` |
| `-t, --title` | 书名，默认取文件名 |
| `-a, --author` | 作者名 |
| `--no-verify` | 跳过打包后结构校验（默认自动校验） |

## 处理流程（核心经验）

### 1. XML 解析前先清理非法控制字符

WordPress 导出正文常含 `\x00-\x08`、`\ud800-\udfff` 等非法字符，直接 `ElementTree.parse` 会报错。先整体替换：

```python
ILLEGAL = re.compile(u'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f\ud800-\udfff￾￿]')
root = ET.fromstring(ILLEGAL.sub('', text))
```

### 2. 去除失效媒体

博客图片/Flash/音频已丢失，正文里的 `<img>`、`<object>`、`<embed>`、`<iframe>`、`<audio>`、`<video>`、`<noscript>` 全部移除，同时清理空链接和空块（详见脚本 `clean_content()`）。

### 3. 段落化（关键）

WordPress 博客正文多数是**纯文本 + 空行分段，没有 `<p>` 标签**。直接输出会在阅读器里挤成一行。用 `fix_paragraphs()`：

- 正文已有块级元素（p/div/ul/ol/li/blockquote/pre/table/h1-6 等）→ 只规范化空行，不重复包裹
- 否则把空行分隔的文本块包成 `<p>…</p>`，块内换行转 `<br>`

### 4. XML 合法化（最容易踩的坑）

HTML 片段转 XHTML 时必须满足 XML 严格语法，三类问题：

| 问题 | 现象 | 修复 |
|------|------|------|
| 空元素未自闭合 | `<br>` → `mismatched tag` 报错 | 正则改 `<br/>`（img/hr/embed 等所有 void 标签） |
| 未定义实体 | `&nbsp;` → `undefined entity` | 转数字实体 `&#160;`（HTML 实体 XML 里只有 5 个预定义） |
| 标签不配对 | 正文有漏闭合/多余闭合标签 | 用 `HTMLParser` 重新配对：空元素自闭合、栈跟踪闭合、丢弃多余闭合标签 |

用脚本里的 `repair_fragment()` 一次处理全部，产出 100% 合法 XML。

### 5. EPUB 打包要点

- **mimetype 必须是 zip 的第一个条目且不压缩**（`ZIP_STORED`），内容 `application/epub+zip`，否则阅读器不识别
- `META-INF/container.xml` → `OEBPS/content.opf`（EPUB3 定位文件）
- **spine 引用的是 manifest 的 `id`，不是 href**——spine 写 `p-170`、`cat-0`，manifest 里 `<item id="p-170" href="p/170.xhtml"/>`
- **NCX navPoint 嵌套闭合必须用栈跟踪**：分类 navPoint 嵌套文章 navPoint，每个分类结束要闭合。用 `while stack` 先闭所有当前栈再开新分类，避免多出/漏掉 `</navPoint>`（曾出现多 15 个闭合标签导致 XML 报错）
- 每篇文章独立 xhtml，每个分类一个章目录页（文章链接列表），封面页含书名/作者/篇数统计

## 生成结构

```
输出.epub
├── mimetype                    # application/epub+zip，ZIP_STORED
├── META-INF/container.xml
└── OEBPS/
    ├── content.opf             # manifest + spine
    ├── toc.ncx                 # 两级目录：分类 → 文章
    ├── css/epub.css
    ├── cover.xhtml             # 封面页
    ├── ch/cat-0.xhtml …        # 每分类一个章目录页（文章链接）
    └── p/{post_id}.xhtml …     # 每篇文章一页
```

## 验证

脚本默认自动校验：全部 xhtml 为合法 XML、spine 全部命中 manifest、无媒体/脚本残留。手工转换时也应做同等检查（`xml.etree.ElementTree` 逐个解析所有 xhtml）。

## 脚本位置

`~/.claude/skills/html-cover-epub/scripts/html_cover_epub.py`

单文件无依赖（仅标准库），可独立调用。

## 适用场景

- 博客导出（WordPress XML）转电子书归档
- 文章集合按分类整理成书
- 需要剔除失效图片/媒体的文章合集
