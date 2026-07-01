---
name: md-to-epub-book
description: |
  将目录中的 Markdown 文件合并转换为一本带目录的 EPUB 电子书。
  当用户提到"把md文件做成书"、"md转epub"、"整理文章成电子书"、"把博客做成书"、"md文件合并成epub"、"把md文件整理成书"时触发。
  也适用于：用户有一个包含多篇 markdown 文章的目录（按年份/分类组织），想整理成一本带章节和目录的电子书时。
  注意：这是中文博客/文章合集转 EPUB 的专用 skill，有完整的中文处理流程和 Word 导出文档清理逻辑。
compatibility:
  require-tools:
    - pandoc
    - python3
---

# MD to EPUB Book

将散落的 Markdown 文件合并成一本书，生成带层级目录的 EPUB。

此 skill 的 scripts/ 目录下有合并和清理脚本，直接调用即可，无需重写。

## 工作流

### 第 1 步：了解目录结构

```bash
# 查看目录层级
find "<目标目录>" -type d | sort
# 统计文件
find "<目标目录>" -name "*.md" -type f | wc -l
du -sh "<目标目录>"
```

### 第 2 步：确定层级映射

根据目录结构确定书籍的层级：

| 目录结构 | H1 章节 | H2 文章 |
|----------|---------|---------|
| `年份/文章.md` | `# 年份` | `## 标题` |
| `分类/文章.md` | `# 分类` | `## 标题` |
| `分类/子分类/文章.md` | `# 分类` → `## 子分类` | `### 标题` |
| `0分类/子分类/年份/文章.md` | `# 分类` → `## 子分类` → `### 年份` | 文件标题 |
| 无子目录 | 无 H1 | `## 标题` |

> **经验**：Apple Notes/iCloud 导出的笔记通常有 3-4 层嵌套（如 `4Mind/改变/2025年/文章.md`），
> 需要使用 `merge_generic.py` 递归处理，不可用仅支持 2 层的 `merge_md_to_book.py`。

### 第 3 步：检查源文件格式

```bash
head -5 "<示例文件路径>"
```

注意观察：
- 标题在第 1 行还是文件名中
- **是否有 md 文件没有 `#` 标题，直接以正文开头**（此类文件会用文件名作为目录标题，正文首段不会入目录）
- 是否有 `作者：`、`tag：` 等元数据
- 是否有 `#` 标题前缀
- 是否有 `[]{#_Toc...}` Pandoc anchor
- 是否有 Word 导出的 `目录 {#目录 .TOC}` 和 `====` 下划线
- **是否有 HTML 标签残留**：`<span style="font-family:PingFangSC-Regular;">` 等（Apple Notes 导出常见）
- **文件名是否超长**：AI 对话导出文件名常为完整首句（如 `"很需要钱但不想赚钱"看似矛盾...`），建议先缩短

#### ⚠️ 关键检查：单换行段落文件

中文博客/文章的 md 文件常使用**单个 `\n`** 分隔段落（每行一段，行间无空行），
而 Markdown 规范要求 `\n\n`（双换行）才构成段落分隔，单 `\n` 会被渲染为空格，
导致 EPUB 中段落文字全部粘连在一起。

**检查方法**：

```bash
# 统计有多少文件只有单换行（无 \n\n 段落分隔）
cd "<目标目录>"
for f in *.md; do
  if ! grep -q $'^\n' "$f" 2>/dev/null && grep -q $'\n' "$f" 2>/dev/null; then
    echo "单换行: $f"
  fi
done
```

**处理方式**：合并脚本已内置自动检测和修复，无需手动处理（见第 4 步说明）。

#### 检查文件编码

```bash
# 确认所有文件都是 UTF-8 编码
find "<目标目录>" -name "*.md" -exec file --mime-encoding {} \; | grep -v utf-8
```

如果有非 UTF-8 文件，需先用 `iconv` 转换：
```bash
iconv -f GBK -t UTF-8 "原文件.md" > "转换后.md"
```

#### 检查文件名规范化

如果文件名有统一前缀（如 `Blog：`、`Book：`），检查是否一致：
```bash
# 查看文件名前缀分布
ls *.md | sed 's/[^：： ]*//' | sort | uniq -c | sort -rn
```

不一致时需先统一命名（见常见问题表中的说明）。

### 第 4 步：执行合并

#### 场景 A：纯年份目录结构

```bash
# 年份目录 → H1，文章 → H2
python3 <skill_path>/scripts/merge_md_to_book.py <目标目录> <输出路径>/combined.md
```

适用于 `2005/文章.md`, `2006/文章.md` 这种结构。

**自动修复**：脚本已内置单换行段落检测，自动将只有单 `\n` 的文件转为 `\n\n` 段落分隔。

#### 场景 B：多级分类目录结构（新增）

```bash
# 自动递归所有子目录，目录名 → H1/H2/H3，文件名 → 下一级 heading
python3 <skill_path>/scripts/merge_generic.py <目标目录> <输出路径>/combined.md

# 如果年份子目录不想保留数字排序前缀（2015年 → 2015年），用默认即可

# 如果不剥离排序数字前缀（0Plan 保持原样）
python3 <skill_path>/scripts/merge_generic.py <目标目录> <输出路径>/combined.md --no-strip-prefix
```

适用于任意深度的目录结构。特性：
- **数字排序前缀智能剥离**：`0Plan` → `Plan`，但 `2015年` 保留 `2015年`
- **HTML 样式污染清理**：自动剥离 `<span style="...">`, `<a>`, `<u>`, `<div>`, `<br>` 等标签
- **XML 非法字符剥离**：自动去除 `\x08` 等控制字符（否则 pandoc 报 PCDATA error）
- **日常日志粗体处理**：日期前缀的文件名（如 `2025.1.10工作备忘.md`）用 `**粗体**` 而非 heading
- **正文标题自动提升**：文件内部的 `##`/`###` 等标题自动增加层级，嵌套在结构标题之下，不会污染 TOC
- **单换行段落自动修复**：检测只有单 `\n` 的文件，自动转为 `\n\n` 段落分隔，避免 EPUB 中段落粘连

#### 场景 C：其他自定义结构

如果以上都不满足，参考 `scripts/merge_md_to_book.py` 或 `scripts/merge_generic.py` 的逻辑编写自定义脚本。

### 第 5 步：清理污染

合并后的文件可能包含 Word 导出的 markdown 语法污染：

```bash
# 基本清理
python3 <skill_path>/scripts/clean_combined_md.py <合并文件.md> <清理后文件.md>

# 严格模式（推荐用于 Apple Notes 等多级内容）
python3 <skill_path>/scripts/clean_combined_md.py <合并文件.md> <清理后文件.md> --strict
```

清理范围：
- `====` 和 `----` setext 标题 → ATX 格式
- `[[text]{.underline} N](#link)` Word 目录条目 → 删除
- `[]{#...}` Pandoc anchor → 删除
- `{#目录 .TOC}` 等 Pandoc 属性 → 删除
- XML 非法控制字符 → 剥离
- YAML front matter → 保护不处理

> **注意**：`--strict` 模式会将正文中 `====` 转换来的 H1 降级为 H2，
> 避免文章内分隔线被误当成章节标题。如果不使用 `--strict`，清理后需手动检查并降级多余的 H1。

### 第 6 步：添加元数据并生成 EPUB

确保文件开头有 YAML front matter：

```markdown
---
title: "书名"
author: "作者"
language: zh-CN
---
```

```bash
pandoc --toc --toc-depth=3 --epub-chapter-level=1 \
  -f markdown+east_asian_line_breaks \
  -o "书名.epub" "清理后文件.md"
```

**关键参数**：
- `--toc`：生成目录导航
- `--toc-depth=3`：目录显示到 H3（多级结构建议 3，简单结构 2 即可）
- `--epub-chapter-level=1`：按 H1 分章节（务必指定）；如果是 H1=分类、H2=文章的两级结构，设为 `--epub-chapter-level=2` 使每篇文章独立成页
- `-f markdown+east_asian_line_breaks`：中文换行扩展，正确处理中日韩文字间的换行

### 第 7 步：验证

```bash
# 检查各章节 H1
for i in $(seq -w 1 19); do
  unzip -p "书名.epub" "EPUB/text/ch$(printf '%03d' $i).xhtml" 2>/dev/null \
    | python3 -c "import sys,re; m=re.search(r'<h1[^>]*>([^<]+)</h1>',sys.stdin.read()); print(m.group(1) if m else '-')"
done

# 检查各章节是否有实质内容（不应为 0 bytes）
for i in $(seq -w 1 19); do
  size=$(unzip -p "书名.epub" "EPUB/text/ch$(printf '%03d' $i).xhtml" 2>/dev/null | wc -c)
  echo "Chapter $i: $size bytes"
done

# 检查目录条目数
unzip -p "书名.epub" "EPUB/toc.ncx" 2>/dev/null | grep -c '<text>'
```

## 常见问题

| 现象 | 原因 | 解决 |
|------|------|------|
| 章节缺失 | `# 目录` 行污染了章节结构 | 运行 clean 脚本清理 setext 标题 |
| 多出"目录"章节 | 文章内嵌 Word 目录 | clean 脚本自动处理 |
| 正文首段被误作目录标题 | md 文件无 `#` 标题，首行是正文 | 已修复：`merge_md_to_book.py` 改用文件名作回退标题 |
| 图片找不到警告 | 博客远程图片链接 | 不影响正文，可忽略 |
| `language:` 变成标题 | YAML 被 setext 误处理 | 运行 clean 脚本（含 YAML 保护） |
| **PCDATA invalid Char value 8** | 源文件含 ASCII 控制字符 (\x08) | 确保 merge 脚本含 `CONTROL_CHAR_RE` 剥离逻辑，或手动 `sed` 清理 |
| **EPUB 极小（如 52KB），各章节几乎为空** | `get_title_from_file` 收到目录路径而非文件路径 | 修复 `collect_files` 中存 `os.path.join(root, f)` 而非 `(root, f)` |
| **年份目录名变成"年"** | 数字前缀剥离过于激进 `r'^\d+'` | 使用 `r'^\d+(?=[A-Z])'` 仅剥离排序前缀，保留 `2015年` |
| **多出 8 个 H1 章节（社会层级、100万等）** | 正文 `====` 被 clean 脚本转成 H1 | 使用 `--strict` 模式运行 clean，或手动将多余 H1 降级为 H2 |
| **EPUB 报错但仍有输出** | pandoc 部分处理了内容，但 XHTML 校验失败 | 检查并修复所有控制字符后重新生成 |
| **EPUB 中段落文字全部粘连无换行** | 源文件用单 `\n` 分段，Markdown 需 `\n\n` | 已修复：合并脚本自动检测并转换单换行为双换行 |
| **所有文章在目录中变成扁平列表，无分类** | 未按子目录分 H1/H2 层级 | 使用 `merge_generic.py` 或确保 H1=分类、H2=文章 |
| **文件名前缀不统一（blog/Blog/Blog：/Blog ）** | 历史文件命名不规范 | 转换前先统一文件名，重命名时检查冲突和内容是否相同 |

## 关键陷阱（经验总结）

### 1. 文件路径 vs 目录路径

`collect_files` 中存储文件信息时，**必须用 `os.path.join(root, f)` 存储完整路径**。
如果存储 `(root, f)` 元组，后续 `get_title_from_file` 会打开目录路径而非文件路径，
导致文件内容全部丢失，合并结果只有标题没有正文（文件大小小几十倍）。

### 2. XML 非法控制字符

Apple Notes / iCloud 导出的文件中可能包含 ASCII 控制字符（如 `\x08` backspace）。
Pandoc 转 XHTML 时 XML 解析器无法处理这些字符，报错：
`PCDATA invalid Char value 8`

必须在合并阶段就剥离所有 `[\x00-\x08\x0b\x0c\x0e-\x1f]` 范围的字符。

### 3. 目录名数字前缀剥离

排序前缀 `0Plan` → `Plan` 是正确的，但**不能使用 `r'^\d+'` 简单匹配**，
否则 `2015年` 也会被剥离成 `年`。必须用 `r'^\d+(?=[A-Z])'` 限制为
"数字后紧跟大写字母"的模式。

### 4. Setext 标题的误转换

`clean_combined_md.py` 将 `====` 下划线转成 H1，但在 Apple Notes 等多级内容中，
文章内的 `====` 只是普通分隔线。使用 `--strict` 模式可仅保留少量已知 H1，
其余降级为 H2。

### 5. 单换行段落粘连（中文文章最常见问题）

中文博客/文章的 md 文件普遍使用**单个 `\n`** 分隔段落（每行一段，行间无空行）。
这是因为在编辑器中每行看起来是独立段落，但 Markdown 规范要求 `\n\n` 才是段落分隔，
单 `\n` 只是软换行，在 EPUB 中渲染为空格，导致所有段落文字粘连在一起。

**检测方法**：文件内容中不存在 `\n\n`（双换行），但存在 `\n`（单换行）。

**修复方法**：将所有单 `\n` 转换为 `\n\n`。合并脚本已内置此逻辑。

**注意事项**：
- 对于**诗歌**等需要保留行内换行的文件，单行变双行会将每行变成独立段落，
  但在 EPUB 中这样显示也是可接受的。
- 对于**已有 `\n\n` 段落分隔**的文件，其中的单 `\n` 是有意的软换行（如长段落的折行），
  不应转换。因此只对**完全没有 `\n\n` 的文件**执行转换。

### 6. 文件名规范化与冲突处理

转换 EPUB 前，如果目录中的文件名前缀不统一（如 `blog`、`Blog`、`Blog：`、`Blog ` 混合），
需先统一规范化。重命名时必须：

1. **检查目标文件是否已存在**：如 `blog：标题.md` → `Blog：标题.md` 时，
   `Blog：标题.md` 可能已存在。
2. **对比内容是否相同**：如果目标已存在且内容相同，删除源文件（重复文件）；
   如果内容不同，给源文件加后缀（如 `Blog：标题1.md`）保留两份。
3. **先删除重复再重命名**：避免重命名后目标文件被覆盖。

### 7. 两级目录结构（分类 + 文章）

如果源目录有子文件夹（如 `Blog/`、`Book/`、`IT/`、`Mind/`），
EPUB 应使用**H1 = 分类名、H2 = 文章标题**的两级结构，
而非将所有文章平铺在同一层级。否则目录中几百篇文章混在一起无法导航。

**pandoc 参数**：`--epub-chapter-level=2` 使 H2 每篇文章独立成页。

## 捆绑脚本

| 脚本 | 用途 | 适用场景 |
|------|------|----------|
| `scripts/merge_md_to_book.py` | 2 层合并（年份/分类 → H1，文章 → H2） | 博客、年份目录 |
| `scripts/merge_generic.py` | 通用多级合并（任意深度，含样式清理） | Apple Notes、复杂目录 |
| `scripts/clean_combined_md.py` | 清理 Word 导出污染、剥离控制字符 | 所有场景 |

三个脚本都有使用提示，直接运行可查看用法。
