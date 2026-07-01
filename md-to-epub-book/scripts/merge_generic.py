#!/usr/bin/env python3
"""
merge_generic.py - 通用目录合并脚本，支持任意深度的多级目录结构

支持:
  - 任意层级的目录嵌套（递归处理）
  - HTML 样式污染清理（<span style="...">, <a>, <u>, <p>, <div>, <br>）
  - XML 非法控制字符剥离（防止 pandoc 报 PCDATA error）
  - 数字排序前缀剥离（0Plan → Plan，保留 2015年 → 2015年）
  - 日常日志文件名检测（日期前缀文件用粗体而非 heading）
  - 目录名中数字前缀的智能剥离（仅剥离排序前缀，保留有意义数字）

用法:
    python3 merge_generic.py <源目录> <输出路径> [选项]

选项:
    --no-strip-prefix    保留目录名的数字排序前缀（默认剥离 0→9 + 大写字母 前缀）
    --daily-pattern REGEX 自定义日常日志文件名正则（默认: \\d{4}\\.\\d{1,2}\\.\\d{1,2}）
    --style-cleanup      开启 HTML 样式污染清理（默认开启）

示例:
    # 基本用法
    python3 merge_generic.py /path/to/notes /output/combined.md

    # 纯年份目录结构（不剥离数字前缀）
    python3 merge_generic.py /path/to/blog /output/combined.md --no-strip-prefix

    # 自定义日志模式
    python3 merge_generic.py /path/to/notes /output/combined.md --daily-pattern "LOG-"
"""
import os
import re
import sys

# ============================================================
# 样式污染正则 — 清理 Apple Notes / 网页导出残留的 HTML
# ============================================================
STYLE_CLEANUP_PATTERNS = [
    # <span style="font-family:PingFangSC-Regular;">内容</span> → 内容
    (re.compile(r'<span[^>]*style\s*=\s*"[^"]*"[^>]*>(.*?)</span>', re.DOTALL), r'\1'),
    # <a href="..." rel="noopener" class="..." target="_blank"><u>内容</u></a> → 内容
    (re.compile(r'<a\s[^>]*>(.*?)</a>', re.DOTALL), r'\1'),
    # <u>内容</u> → 内容
    (re.compile(r'<u>(.*?)</u>', re.DOTALL), r'\1'),
    # <p> 和 </p>
    (re.compile(r'</?p[^>]*>', re.DOTALL), ''),
    # <div> 和 </div>
    (re.compile(r'</?div[^>]*>'), ''),
    # <br> → 换行
    (re.compile(r'<br\s*/?>'), '\n'),
    # 其他残留 HTML 标签
    (re.compile(r'<[^>]+>'), ''),
    # 多余空行（3+ 连续换行 → 2 换行）
    (re.compile(r'\n{3,}'), '\n\n'),
]

# XML 非法字符 — 除 \t(0x09) \n(0x0A) \r(0x0D) 外全部剥离
CONTROL_CHAR_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def fix_single_newline_paragraphs(content):
    """
    修复单换行段落问题。

    中文博客/文章的 md 文件常使用单个 \\n 分隔段落（每行一段，行间无空行），
    而 Markdown 规范要求 \\n\\n 才是段落分隔，单 \\n 会被渲染为空格，
    导致 EPUB 中段落文字全部粘连在一起。

    检测规则：如果文件内容中完全没有 \\n\\n（双换行），但有 \\n（单换行），
    则将所有单 \\n 转换为 \\n\\n。

    对于已有 \\n\\n 的文件，其中的单 \\n 是有意的软换行，不转换。
    """
    if '\n\n' not in content and '\n' in content:
        return content.replace('\n', '\n\n'), True
    return content, False


def parse_args(argv):
    """解析命令行参数"""
    args = {
        'source_dir': None,
        'output_file': None,
        'strip_prefix': True,
        'daily_pattern': r'^\d{4}\.\d{1,2}\.\d{1,2}',
    }
    positional = []
    for a in argv[1:]:
        if a == '--no-strip-prefix':
            args['strip_prefix'] = False
        elif a.startswith('--daily-pattern='):
            args['daily_pattern'] = a.split('=', 1)[1]
        elif a.startswith('--'):
            print(f"未知选项: {a}")
            sys.exit(1)
        else:
            positional.append(a)

    if len(positional) != 2:
        print("用法: python3 merge_generic.py <源目录> <输出路径> [--no-strip-prefix] [--daily-pattern=REGEX]")
        sys.exit(1)
    args['source_dir'] = positional[0]
    args['output_file'] = positional[1]
    return args


def is_daily_log(filename, pattern):
    """判断是否为日志类文件（日期前缀文件名）"""
    return bool(pattern.match(filename))


def cleanup_styles(text):
    """清理 HTML 样式污染"""
    for pattern, replacement in STYLE_CLEANUP_PATTERNS:
        text = pattern.sub(replacement, text)
    return text.strip()


def get_title_from_file(filepath, filename, daily_pattern):
    """从文件内容或文件名提取标题，返回 (title, lines)"""
    if os.path.isdir(filepath):
        return os.path.splitext(filename)[0], []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return os.path.splitext(filename)[0], []

    # 剥离 XML 非法控制字符（否则 pandoc 转 XHTML 报错）
    content = CONTROL_CHAR_RE.sub('', content)

    # 修复单换行段落（在清理样式之前，避免样式标签影响换行检测）
    content, was_fixed = fix_single_newline_paragraphs(content)

    # 清理 HTML 样式污染
    lines = content.splitlines(True)
    clean_lines = [cleanup_styles(l) for l in lines]

    # 找第一个非空行检测标题
    idx = 0
    while idx < len(clean_lines) and clean_lines[idx].strip() == '':
        idx += 1
    if idx >= len(clean_lines):
        return os.path.splitext(filename)[0], clean_lines

    first = clean_lines[idx].strip()

    # 检测是否为 # 标题行
    hm = re.match(r'^(#{1,6})\s+(.+)$', first)
    if hm:
        title = hm.group(2).strip()
        clean_lines.pop(idx)  # 避免重复输出标题
        return title, clean_lines

    return os.path.splitext(filename)[0], clean_lines


def collect_files(source_dir):
    """
    遍历目录树，构建嵌套字典结构。

    返回示例:
    {
        '0Plan': {
            'AI': {'__files__': ['/path/0Plan/AI/file.md', ...]},
            '总纲': {'__files__': [...]},
        },
        '1Time': {
            'A日生活日志': {
                '2015年': {'__files__': [...]},
                '2016年': {'__files__': [...]},
            },
        },
    }
    """
    structure = {}

    for root, dirs, files in sorted(os.walk(source_dir)):
        rel = os.path.relpath(root, source_dir)
        if rel == '.':
            continue

        parts = rel.split(os.sep)
        files_md = sorted([f for f in files if f.endswith('.md')])
        if not files_md:
            continue

        current = structure
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]

        # 关键: 存储完整路径，非 (root, f) 元组
        current['__files__'] = [
            os.path.join(root, f) for f in files_md
            if os.path.isfile(os.path.join(root, f))
        ]

    return structure


def strip_sort_prefix(name):
    """剥离目录名中的排序数字前缀（0Plan → Plan，2015年 → 2015年）"""
    return re.sub(r'^\d+(?=[A-Z])', '', name) or name


def write_section(out, structure, level, daily_pattern, max_level=6):
    """递归写入章节内容"""
    files = structure.pop('__files__', [])

    if files:
        for filepath in files:
            filename = os.path.basename(filepath)
            title, lines = get_title_from_file(filepath, filename, daily_pattern)

            if is_daily_log(filename, daily_pattern):
                # 日常日志：用粗体，避免大量 H4 撑爆目录
                out.write(f'**{title}**\n\n')
            else:
                h = '#' * min(level, max_level)
                out.write(f'{h} {title}\n\n')

            for line in lines:
                cleaned = cleanup_styles(line)
                # 正文中的标题提升层级，确保嵌套在文件标题之下
                hm = re.match(r'^(#{1,6})\s+', cleaned)
                if hm:
                    orig = len(hm.group(1))
                    new = min(orig + level, 6)
                    cleaned = '#' * new + cleaned[orig:]
                out.write(cleaned)
                if not cleaned.endswith('\n'):
                    out.write('\n')
            out.write('\n\n')

    # 递归子目录
    for key, substructure in sorted(structure.items()):
        if isinstance(substructure, dict):
            heading = strip_sort_prefix(key)
            h = '#' * min(level, max_level)
            out.write(f'{h} {heading}\n\n')
            write_section(out, substructure, level + 1, daily_pattern, max_level)


def merge_notes(source_dir, output_file, strip_prefix=True, daily_pattern=None):
    """主入口"""
    if daily_pattern is None:
        daily_pattern = r'^\d{4}\.\d{1,2}\.\d{1,2}'
    daily_re = re.compile(daily_pattern)

    structure = collect_files(source_dir)

    if not structure:
        print("错误：未找到任何 Markdown 文件")
        sys.exit(1)

    fixed_newlines = 0

    if not structure:
        print("错误：未找到任何 Markdown 文件")
        sys.exit(1)

    with open(output_file, 'w', encoding='utf-8') as out:
        # 按数字前缀排序（0→9 在前，字母在后）
        sorted_keys = sorted(
            structure.keys(),
            key=lambda k: (
                int(re.match(r'^(\d+)', k).group(1)) if re.match(r'^(\d+)', k) else 99,
                k,
            ),
        )

        for key in sorted_keys:
            display_name = strip_sort_prefix(key) if strip_prefix else key
            out.write(f"# {display_name}\n\n")
            write_section(out, structure[key], 2, daily_re)

    # 统计
    total = sum(
        1 for _, _, files in os.walk(source_dir) for f in files if f.endswith('.md')
    )
    print(f"完成。合并 {total} 个文件到 {output_file}")
    if fixed_newlines:
        print(f"修复了 {fixed_newlines} 个文件的单换行段落问题（\\n → \\n\\n）")


if __name__ == '__main__':
    args = parse_args(sys.argv)
    merge_notes(
        args['source_dir'],
        args['output_file'],
        strip_prefix=args['strip_prefix'],
        daily_pattern=args['daily_pattern'],
    )
