#!/usr/bin/env python3
"""
clean_combined_md.py - 清理合并后的 markdown 文件中的 Word 导出污染

处理:
  - Setext 标题 (文本\n==== 或 文本\n----) → ATX 格式
  - Word 目录条目 ([[文本]{.underline} N](#_TocXXX))
  - Pandoc anchor ([]{#...})
  - Pandoc 属性 ({#目录 .TOC} 等)
  - XML 非法控制字符剥离

用法:
    python3 clean_combined_md.py <输入.md> <输出.md> [--strict]

选项:
    --strict  严格模式：仅保留特定 H1（Plan/Time/Work/Writing/Mind/Life 等），
               其余正文 ==== 转换的 H1 降级为 H2（适用于 Apple Notes 等多级内容）
"""
import re
import sys

# XML 非法控制字符
CONTROL_CHAR_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def clean_combined_md(input_path, output_path, strict=False, valid_h1s=None):
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 剥离 XML 非法控制字符（防止 pandoc 报 PCDATA error）
    lines = [CONTROL_CHAR_RE.sub('', l) for l in lines]

    setext_ul = re.compile(r'^(={3,}|-{3,})$')
    word_toc = re.compile(r'^\[\[.*\]\(#')
    pandoc_anchor = re.compile(r'\[\]\{[^}]+\}')
    pandoc_attr = re.compile(r'\s*\{#[^}"]+\}')

    result = []
    i = 0

    # 保护 YAML front matter
    if lines and lines[0].strip() == '---':
        result.append(lines[0])
        i = 1
        while i < len(lines) and lines[i].strip() != '---':
            result.append(lines[i])
            i += 1
        if i < len(lines):
            result.append(lines[i])
            i += 1
        result.append('\n')

    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()

        # --- 1. Setext 标题转换 ---
        if setext_ul.match(stripped):
            prev = None
            prev_idx = None
            for j in range(len(result) - 1, -1, -1):
                rs = result[j].rstrip()
                if rs == '':
                    continue
                if setext_ul.match(rs):
                    break
                prev = rs
                prev_idx = j
                break

            if prev and not prev.startswith('#'):
                if strict and stripped.startswith('='):
                    # 严格模式：检查有效的 H1 列表
                    if valid_h1s and prev in valid_h1s:
                        new_h = f"# {prev}\n"  # 保留为 H1
                    else:
                        new_h = f"## {prev}\n"  # 降级为 H2
                else:
                    new_h = f"{'##' if stripped.startswith('=') else '###'} {prev}\n"

                if prev_idx is not None:
                    result.pop(prev_idx)
                result.append(new_h)
                i += 1
                continue
            else:
                i += 1
                continue

        # --- 2. 跳过 Word 目录条目 ---
        if word_toc.match(stripped):
            i += 1
            continue

        # --- 3. 跳过 `目录 {#目录 .TOC}` ---
        if re.match(r'^目录\s*\{#目录', stripped):
            i += 1
            continue

        # --- 4. 删除 Pandoc anchors 和 attributes ---
        line = pandoc_anchor.sub('', line)
        line = pandoc_attr.sub('', line)
        result.append(line)
        i += 1

    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(result)

    total_h1 = sum(1 for l in result if l.startswith('# ') and not l.startswith('## '))
    total_h2 = sum(1 for l in result if l.startswith('## '))
    print(f"清理完成。输出: {output_path}")
    print(f"H1 章节: {total_h1}, H2 文章: {total_h2}")


if __name__ == '__main__':
    valid_h1s = None
    args = sys.argv[1:]
    strict = False

    if '--strict' in args:
        strict = True
        args.remove('--strict')

    # 支持 --valid-h1s 参数
    for i, a in enumerate(args):
        if a.startswith('--valid-h1s='):
            valid_h1s = set(a.split('=', 1)[1].split(','))
            args.pop(i)
            break

    if len(args) != 2:
        print("用法: python3 clean_combined_md.py <输入.md> <输出.md> [--strict] [--valid-h1s=Plan,Time,Work]")
        sys.exit(1)

    clean_combined_md(args[0], args[1], strict=strict, valid_h1s=valid_h1s)
