#!/usr/bin/env python3
"""
merge_md_to_book.py - 将目录中的 md 文件按年份合并成一本书

用法:
    python3 merge_md_to_book.py <源目录> <输出路径>

示例:
    python3 merge_md_to_book.py /path/to/blog /path/to/combined.md

自动修复:
    - 单换行段落：中文文章常用单 \\n 分段，Markdown 需 \\n\\n，自动检测并转换
    - 无标题文件：正文无 # 标题时，用文件名作为章节标题
"""
import os
import re
import sys


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
        return content.replace('\n', '\n\n')
    return content


def merge_blog(blog_dir, output_file):
    # 收集所有年份目录（纯数字目录名）
    year_dirs = sorted([
        d for d in os.listdir(blog_dir)
        if d.isdigit() and os.path.isdir(os.path.join(blog_dir, d))
    ])

    if not year_dirs:
        print("错误：在目录中未找到数字命名的子目录（如 2005、2006 等）")
        print("提示：如果目录结构不同，请编辑此脚本调整 year_dirs 的收集逻辑")
        sys.exit(1)

    total = 0
    skipped = []
    fixed_newlines = 0

    # 元数据行模式
    meta_patterns = [
        re.compile(r'^作者[：:]\s*'),
        re.compile(r'^tag[：:]\s*', re.IGNORECASE),
        re.compile(r'^HEMA原作'),
    ]

    with open(output_file, 'w', encoding='utf-8') as out:
        for year in year_dirs:
            year_path = os.path.join(blog_dir, year)

            md_files = []
            for root, dirs, files in os.walk(year_path):
                for f in files:
                    if f.endswith('.md'):
                        md_files.append(os.path.join(root, f))

            if not md_files:
                continue

            md_files.sort(key=lambda x: os.path.basename(x))
            out.write(f"# {year}\n\n")

            for filepath in md_files:
                rel = os.path.relpath(filepath, blog_dir)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    skipped.append(f"{rel} (读取错误: {e})")
                    continue

                if not content.strip():
                    skipped.append(f"{rel} (空文件)")
                    continue

                # 修复单换行段落
                original = content
                content = fix_single_newline_paragraphs(content)
                if content != original:
                    fixed_newlines += 1

                lines = content.splitlines(True)

                # 找第一个非空行
                idx = 0
                while idx < len(lines) and lines[idx].strip() == '':
                    idx += 1
                if idx >= len(lines):
                    skipped.append(f"{rel} (无内容)")
                    continue

                first = lines[idx].strip()

                # 检测是否为 # 开头的 markdown 标题
                hm = re.match(r'^(#{1,6})\s+(.+)$', first)
                if hm:
                    level = len(hm.group(1))
                    title = hm.group(2).strip()
                    out.write(f"{'#' * (level + 1)} {title}\n\n")
                    for i, line in enumerate(lines):
                        if i == idx:
                            continue
                        h2 = re.match(r'^(#{1,6})\s+(.*)$', line)
                        if h2:
                            out.write(f"{'#' * (len(h2.group(1)) + 1)} {h2.group(2)}\n")
                        else:
                            out.write(line)
                else:
                    # 文件无 # 标题，用文件名（不含扩展名）作为标题，
                    # 避免正文第一段被误当作目录标题
                    title = os.path.splitext(os.path.basename(filepath))[0]
                    out.write(f"## {title}\n\n")
                    in_content = False
                    for i, line in enumerate(lines):
                        if i == idx:
                            continue
                        s = line.strip()
                        if not in_content and s == '':
                            continue
                        if not in_content:
                            is_meta = any(p.match(s) for p in meta_patterns)
                            if is_meta:
                                continue
                        in_content = True
                        out.write(line)

                out.write("\n\n")
                total += 1

    print(f"完成。合并 {total} 个文件到 {output_file}")
    if fixed_newlines:
        print(f"修复了 {fixed_newlines} 个文件的单换行段落问题（\\n → \\n\\n）")
    if skipped:
        print(f"\n跳过/警告 ({len(skipped)} 个):")
        for s in skipped:
            print(f"  - {s}")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("用法: python3 merge_md_to_book.py <源目录> <输出路径>")
        sys.exit(1)
    merge_blog(sys.argv[1], sys.argv[2])
