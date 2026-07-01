#!/usr/bin/env python3
"""
word-cover-md — 博客文章 Markdown 文件标题格式化与归类工具

用法:
  python3 word_cover_md.py clean-names <目录>     # 清理文件名中的网址/评论数/标点
  python3 word_cover_md.py append-category <目录>  # 从 Categories 字段补分类后缀
  python3 word_cover_md.py prepend-date <目录>     # 从 Posted on 字段补日期前缀
  python3 word_cover_md.py move-articles <目录>    # 按「时间-内容-分类」格式移动文件
  python3 word_cover_md.py format-all <目录>       # 扫描所有目录，格式化有元数据的文件
  python3 word_cover_md.py convert-date <目录>     # MM-DD-YYYY → YYYY-MM-DD
  python3 word_cover_md.py full-pipeline <目录>    # 全流程：清理→补分类→补日期→移动→转格式
  python3 word_cover_md.py split <全量文档.md>     # 按 ### 拆分全量文档
"""

import os
import re
import shutil
import sys
from collections import Counter

# ── 分类目录映射 ──────────────────────────────────────────
CATEGORY_MAP = {
    '修行笔记': '第一部分：修身/第一章：修行笔记',
    '常识学派': '第一部分：修身/第三章：常识学派',
    '认识自己': '第一部分：修身/第四章：认识自己',
    '修身养性': '第一部分：修身',
    '商业世界': '第二部分：商业/第一章：商业世界',
    '互联网络': '第二部分：商业/第二章：互联网络',
    '工作杂记': '第二部分：商业/第三章：工作杂记',
    '游戏设计': '第二部分：商业/第四章：游戏设计',
    '网络社区': '第二部分：商业/第五章：网络社区',
    '点滴生活': '第三部分：生活/第一章：点滴生活',
    '理论研究': '第三部分：生活/第二章：理论研究',
    '行走足迹': '第三部分：生活/第三章：行走足迹',
    '读书笔记': '第三部分：生活/第四章：读书笔记',
    '关于博客': '第四部分：自我/第一章：关于博客',
    '关于自己': '第四部分：自我/第二章：关于自己',
    '单独篇章': '第四部分：自我/第三章：单独篇章',
    '奇思妙想': '第四部分：自我/第四章：奇思妙想',
}

# 主目录分区
SECTIONS = ['第一部分：修身', '第二部分：商业', '第三部分：生活', '第四部分：自我']


# ══════════════════════════════════════════════════════════
#  1. clean-names — 清理文件名中的网址、评论数、标点
# ══════════════════════════════════════════════════════════
def clean_filename(name):
    """处理单个文件名"""
    stem, ext = os.path.splitext(name)
    if ext.lower() != '.md':
        return name
    old = stem
    stem = re.sub(r'\[(.+)\]\([^)]+\)', r'\1', stem)        # 去除网址
    stem = re.sub(r'有\d+条评论', '', stem)                   # 去除"有X条评论"
    stem = re.sub(r'[？，！（）?,!()]', '', stem)              # 去除标点
    stem = re.sub(r'\s+', ' ', stem).strip()
    stem = stem.strip('-').strip('—')
    stem = re.sub(r'\s*-\s*', '-', stem)
    return f'{stem}{ext}' if stem != old else name


def cmd_clean_names(base_dir):
    pairs = []
    for root, dirs, files in os.walk(base_dir):
        if '.claude' in root.split(os.sep):
            continue
        for f in files:
            if not f.endswith('.md') or f == '全量文档.md':
                continue
            new = clean_filename(f)
            if new != f:
                pairs.append((os.path.join(root, f), os.path.join(root, new)))
    if not pairs:
        print('没有需要清理的文件。')
        return
    print(f'共 {len(pairs)} 个文件需要清理：\n')
    by_dir = {}
    for old, new in pairs:
        d = os.path.dirname(old)
        by_dir.setdefault(d, []).append((os.path.basename(old), os.path.basename(new)))
    for d, lst in sorted(by_dir.items()):
        print(f'  📁 {os.path.relpath(d, base_dir)}/')
        for o, n in lst:
            print(f'     {o}\n     → {n}')
    print(f'\n即将清理以上 {len(pairs)} 个文件')
    ok = 0
    for old, new in pairs:
        if os.path.exists(new):
            print(f'  ⚠️  跳过（已存在）: {os.path.basename(new)}')
            continue
        shutil.move(old, new)
        ok += 1
    print(f'\n✅ 清理完成：{ok}/{len(pairs)}')


# ══════════════════════════════════════════════════════════
#  2. append-category — 从 Categories 字段补分类后缀
# ══════════════════════════════════════════════════════════
def cmd_append_category(base_dir):
    src_dir = os.path.join(base_dir, '未分类')
    if not os.path.isdir(src_dir):
        print(f'未找到 {src_dir}')
        return
    ok = skip = 0
    for f in sorted(os.listdir(src_dir)):
        if not f.endswith('.md'):
            continue
        fpath = os.path.join(src_dir, f)
        with open(fpath, 'r', encoding='utf-8') as fh:
            content = fh.read()
        m = re.search(r'Categories\[([^\]]+)\]', content)
        if not m:
            skip += 1
            continue
        cat = m.group(1).strip()
        if not cat:
            skip += 1
            continue
        new_name = f'{f[:-3]}-{cat}.md'
        new_path = os.path.join(src_dir, new_name)
        if os.path.exists(new_path):
            stem = new_path[:-3]
            c = 1
            while os.path.exists(f'{stem}_{c}.md'):
                c += 1
            new_path = f'{stem}_{c}.md'
            new_name = os.path.basename(new_path)
        os.rename(fpath, new_path)
        ok += 1
        print(f'  {f}\n  → {new_name}')
    print(f'\n✅ 补分类后缀: {ok}  跳过: {skip}')


# ══════════════════════════════════════════════════════════
#  3. prepend-date — 从 Posted on 字段补日期前缀
# ══════════════════════════════════════════════════════════
def cmd_prepend_date(base_dir):
    src_dir = os.path.join(base_dir, '未分类')
    if not os.path.isdir(src_dir):
        print(f'未找到 {src_dir}')
        return
    ok = skip = 0
    for f in sorted(os.listdir(src_dir)):
        if not f.endswith('.md'):
            continue
        fpath = os.path.join(src_dir, f)
        with open(fpath, 'r', encoding='utf-8') as fh:
            content = fh.read()
        m = re.search(r'Posted on\[([^\]]+)\]', content)
        if not m:
            skip += 1
            continue
        parts = m.group(1).strip().split('/')
        if len(parts) != 3:
            skip += 1
            continue
        date_pre = f'{parts[0]}-{parts[1]}-{parts[2]}'
        if re.match(r'^\d{2}-\d{2}-\d{4}-', f):
            ok += 1
            continue
        new_name = f'{date_pre}-{f}'
        new_path = os.path.join(src_dir, new_name)
        if os.path.exists(new_path):
            stem = new_path[:-3]
            c = 1
            while os.path.exists(f'{stem}_{c}.md'):
                c += 1
            new_path = f'{stem}_{c}.md'
            new_name = os.path.basename(new_path)
        os.rename(fpath, new_path)
        ok += 1
        print(f'  {f}\n  → {new_name}')
    print(f'\n✅ 补日期前缀: {ok}  跳过: {skip}')


# ══════════════════════════════════════════════════════════
#  4. move-articles — 按「时间-内容-分类」格式移动文件
# ══════════════════════════════════════════════════════════
def _parse_move_name(filename):
    if not filename.endswith('.md'):
        return None
    name = filename[:-3]
    m = re.match(r'^(\d{2}-\d{2}-\d{4})-(.+)-([^-]+)$', name)
    if not m:
        return None
    cat = m.group(3)
    if cat not in CATEGORY_MAP:
        return None
    return cat, CATEGORY_MAP[cat]


def cmd_move_articles(base_dir):
    src_dir = os.path.join(base_dir, '未分类')
    if not os.path.isdir(src_dir):
        print(f'未找到 {src_dir}')
        return
    to_move = []
    skipped = []
    for f in sorted(os.listdir(src_dir)):
        if not f.endswith('.md'):
            continue
        src = os.path.join(src_dir, f)
        r = _parse_move_name(f)
        if r is None:
            name = f[:-3]
            m = re.match(r'^(\d{2}-\d{2}-\d{4})-(.+)-([^-]+)$', name)
            skipped.append((f, f'未知分类「{m.group(3)}」' if m else '不匹配格式'))
            continue
        cat, rel_dir = r
        to_move.append((src, os.path.join(base_dir, rel_dir, f), cat, rel_dir))
    if not to_move:
        print('没有需要移动的文件。')
        return
    cc = Counter(i[2] for i in to_move)
    print(f'共 {len(to_move)} 个可移动文件：\n')
    for c, n in sorted(cc.items(), key=lambda x: -x[1]):
        print(f'  {c} → {CATEGORY_MAP[c]}/ ({n}篇)')
    print(f'\n跳过 {len(skipped)} 个')
    for fn, why in skipped[:10]:
        print(f'  ⏭  {fn} ({why})')
    ok = dup = 0
    for src, dst, _, _ in to_move:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            stem, ext = os.path.splitext(dst)
            c = 1
            while os.path.exists(f'{stem}_{c}{ext}'):
                c += 1
            dst = f'{stem}_{c}{ext}'
            dup += 1
        shutil.move(src, dst)
        ok += 1
    print(f'\n✅ 移动: {ok}  ' + (f'重名 {dup} 个' if dup else '') + f'  跳过: {len(skipped)}')


# ══════════════════════════════════════════════════════════
#  5. format-all — 扫描所有目录，格式化有元数据的文件
# ══════════════════════════════════════════════════════════
def cmd_format_all(base_dir):
    pat_ok = re.compile(r'^\d{2}-\d{2}-\d{4}-.+-[^-]+\.md$')
    to_proc = []
    no_meta = 0
    for sec in SECTIONS:
        sp = os.path.join(base_dir, sec)
        if not os.path.isdir(sp):
            continue
        for root, dirs, files in os.walk(sp):
            for f in sorted(files):
                if not f.endswith('.md') or pat_ok.match(f):
                    continue
                fp = os.path.join(root, f)
                with open(fp, 'r', encoding='utf-8') as fh:
                    c = fh.read()
                posted = re.search(r'Posted on\[([^\]]+)\]', c)
                cat_m = re.search(r'Categories\[([^\]]+)\]', c)
                if not posted or not cat_m:
                    no_meta += 1
                    continue
                to_proc.append((fp, f, posted.group(1), cat_m.group(1)))
    print(f'找到 {len(to_proc)} 个可格式化的文件\n')
    ok = dup = skip = 0
    for fp, fn, ds, cat in to_proc:
        parts = ds.split('/')
        if len(parts) != 3:
            skip += 1
            continue
        dp = f'{parts[0]}-{parts[1]}-{parts[2]}'
        title = fn[:-3]
        title = re.sub(r'_\d+$', '', title)
        title = re.sub(r'\[(.+)\]\([^)]+\)', r'\1', title)
        title = title.strip()
        nn = f'{dp}-{title}-{cat}.md'
        td = CATEGORY_MAP.get(cat)
        if not td:
            skip += 1
            continue
        dst = os.path.join(base_dir, td, nn)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            stem, ext = os.path.splitext(dst)
            c = 1
            while os.path.exists(f'{stem}_{c}{ext}'):
                c += 1
            dst = f'{stem}_{c}{ext}'
            dup += 1
        old_rel = os.path.relpath(fp, base_dir)
        new_rel = os.path.relpath(dst, base_dir)
        print(f'  {old_rel}\n  → {new_rel}\n')
        shutil.move(fp, dst)
        ok += 1
    print(f'✅ 格式化: {ok}  ' + (f'重名 {dup}  ' if dup else '') + f'跳过: {skip}  无元数据: {no_meta}')


# ══════════════════════════════════════════════════════════
#  6. convert-date — MM-DD-YYYY → YYYY-MM-DD
# ══════════════════════════════════════════════════════════
def cmd_convert_date(base_dir):
    all_sections = SECTIONS + ['未分类']
    pat = re.compile(r'^(\d{2})-(\d{2})-(\d{4})-(.+)')
    ok = conflicts = skip = 0
    for sec in all_sections:
        sp = os.path.join(base_dir, sec)
        if not os.path.isdir(sp):
            continue
        for root, dirs, files in os.walk(sp):
            for f in sorted(files):
                if not f.endswith('.md'):
                    continue
                m = pat.match(f)
                if not m:
                    continue
                mo, da, yr, rest = m.group(1), m.group(2), m.group(3), m.group(4)
                nn = f'{yr}-{mo}-{da}-{rest}'
                if nn == f:
                    continue
                old = os.path.join(root, f)
                new = os.path.join(root, nn)
                if os.path.exists(new):
                    stem, ext = os.path.splitext(new)
                    c = 1
                    while os.path.exists(f'{stem}_{c}{ext}'):
                        c += 1
                    new = f'{stem}_{c}{ext}'
                    nn = os.path.basename(new)
                    conflicts += 1
                shutil.move(old, new)
                ok += 1
                print(f'  {f}\n  → {nn}')
    print(f'\n✅ 转换: {ok}  ' + (f'重名 {conflicts}  ' if conflicts else '') + f'跳过: {skip}')


# ══════════════════════════════════════════════════════════
#  7. split — 按 ### 拆分全量文档
# ══════════════════════════════════════════════════════════
def sanitize(name, maxlen=120):
    name = re.sub(r'[/\\:*?"<>|]', '-', name)
    name = name.replace('\0', '')
    name = re.sub(r'\s+', ' ', name).strip().strip('. ')
    return "untitled" if not name else (name[:maxlen].rstrip() if len(name) > maxlen else name)


def looks_like_heading(text):
    text = text.strip()
    if not text:
        return False
    text = text.rstrip('\\')
    if not text or len(text) > 80:
        return False
    if text.endswith(('。', '？', '！', '，', '；', '：', '……', '——', '.', '?', '!', ',', ';', ':')):
        return False
    if re.search(r'[，、]', text):
        return False
    if re.match(r'^https?://', text):
        return False
    return True


def cmd_split(md_path):
    """按 ### 拆分全量文档"""
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.read().split('\n')
    h1, h2 = '', ''
    segs = []
    cur_h3 = None
    cur_start = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if i > 0 and re.fullmatch(r'={3,}\s*', line):
            prev = lines[i - 1]
            if prev.strip() and looks_like_heading(prev):
                h1 = prev.strip()
                h2 = ''
                i += 1
                continue
        if i > 0 and re.fullmatch(r'-{3,}\s*', line) and len(line.strip()) >= 5:
            prev = lines[i - 1]
            if prev.strip() and looks_like_heading(prev):
                h2 = prev.strip()
                i += 1
                continue
        if line.startswith('### '):
            if cur_h3 is not None:
                segs.append((h1, h2, cur_h3, cur_start, i))
            heading = line.lstrip('#').strip()
            heading = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', heading).strip()
            cur_h3 = heading
            cur_start = i
            i += 1
            continue
        i += 1
    if cur_h3 is not None:
        segs.append((h1, h2, cur_h3, cur_start, len(lines)))
    print(f'共找到 {len(segs)} 篇文章\n')
    base = os.path.dirname(md_path)
    written = 0
    for h1, h2, heading, start, end in segs:
        dir_path = os.path.join(base, sanitize(h1) if h1 else '_root')
        if h2:
            dir_path = os.path.join(dir_path, sanitize(h2))
        os.makedirs(dir_path, exist_ok=True)
        fname = sanitize(heading) + '.md'
        fpath = os.path.join(dir_path, fname)
        counter = 1
        while os.path.exists(fpath):
            fpath = os.path.join(dir_path, f'{sanitize(heading)}_{counter}.md')
            counter += 1
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines[start:end]))
        written += 1
    print(f'✅ 写入 {written} 个文件到 {base}')


# ══════════════════════════════════════════════════════════
#  CLI 入口
# ══════════════════════════════════════════════════════════
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == 'split':
        if len(sys.argv) < 3:
            print('用法: word_cover_md.py split <全量文档.md>')
            sys.exit(1)
        cmd_split(sys.argv[2])
        return

    # 以下命令需要目录参数
    if len(sys.argv) < 3:
        print(f'用法: word_cover_md.py {cmd} <目录>')
        sys.exit(1)
    base_dir = sys.argv[2]
    if not os.path.isdir(base_dir):
        print(f'目录不存在: {base_dir}')
        sys.exit(1)

    cmds = {
        'clean-names': cmd_clean_names,
        'append-category': cmd_append_category,
        'prepend-date': cmd_prepend_date,
        'move-articles': cmd_move_articles,
        'format-all': cmd_format_all,
        'convert-date': cmd_convert_date,
    }
    if cmd == 'full-pipeline':
        print('═══ 1/6 清理文件名 ═══')
        cmd_clean_names(base_dir)
        print('\n═══ 2/6 补分类后缀 ═══')
        cmd_append_category(base_dir)
        print('\n═══ 3/6 补日期前缀 ═══')
        cmd_prepend_date(base_dir)
        print('\n═══ 4/6 移动文章 ═══')
        cmd_move_articles(base_dir)
        print('\n═══ 5/6 格式化所有目录 ═══')
        cmd_format_all(base_dir)
        print('\n═══ 6/6 转换日期格式 ═══')
        cmd_convert_date(base_dir)
        print('\n✅ 全流程完成！')
    elif cmd in cmds:
        cmds[cmd](base_dir)
    else:
        print(f'未知命令: {cmd}')
        print(__doc__)


if __name__ == '__main__':
    main()
