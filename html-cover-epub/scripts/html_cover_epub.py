#!/usr/bin/env python3
"""html-cover-epub: 把 WordPress WXR XML 博客导出转换为标准 EPUB3 电子书。

转换经验总结（2026-08 处理河马博客 964 篇文章时的完整流程）：

1. XML 解析前必须先清理非法控制字符（\x00-\x08 等），否则 ElementTree 报错
2. 正文清理：去除失效媒体（img/object/embed/iframe/audio/video/noscript）、空链接、空块
3. 段落化：WordPress 博客正文多用纯文本 + 空行分段（无 <p> 标签），需自动包裹 <p>
4. XML 合法化：HTML 片段转 XHTML 时必须
   - 空元素自闭合：<br> → <br/>（否则 ElementTree "mismatched tag"）
   - 未定义实体转数字实体：&nbsp; → &#160;（否则 "undefined entity"）
   - 用 HTMLParser 配对修复不闭合/多余的标签
5. EPUB 打包要点：
   - mimetype 必须是 zip 第一个条目且不压缩（ZIP_STORED）
   - OPF 的 spine 引用的是 manifest 的 id，不是 href
   - NCX navPoint 嵌套闭合需用栈跟踪（曾出现多 15 个 </navPoint>）
   - 每篇文章独立 xhtml，分类页作为章目录页
"""
import argparse
import html
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

# ---------- XML 非法控制字符 ----------
ILLEGAL = re.compile(
    u'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f\ud800-\udfff\ufffe\uffff]'
)

VOID_TAGS = {
    'br', 'img', 'hr', 'meta', 'link', 'input', 'embed', 'area', 'base',
    'col', 'colgroup', 'param', 'source', 'track', 'wbr',
}

# 块级元素检测，用于判断正文是否已有 HTML 结构
BLOCK_RE = re.compile(
    r'<(?:p|div|br|ul|ol|li|blockquote|pre|table|h[1-6]|hr|dl|dt|dd|tr|figure)\b',
    re.I,
)


# ---------- 正文清理 ----------
def clean_content(c):
    """去除失效媒体与无用标记，保留正文 HTML。"""
    if not c:
        return ''
    c = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', c, flags=re.S | re.I)
    for tag in ['object', 'iframe', 'audio', 'video', 'noscript']:
        c = re.sub(r'<%s[^>]*>.*?</%s>' % (tag, tag), '', c, flags=re.S | re.I)
    c = re.sub(r'<embed[^>]*?/?>', '', c, flags=re.S | re.I)
    c = re.sub(r'<img[^>]*>', '', c, flags=re.S | re.I)
    c = re.sub(r'</?(?:object|embed|iframe|audio|video|noscript|param)\b[^>]*>',
               '', c, flags=re.S | re.I)
    c = re.sub(r'<a[^>]*>\s*</a>', '', c, flags=re.S | re.I)
    c = re.sub(r'<p[^>]*>\s*(?:<br\s*/?>)*\s*</p>', '', c, flags=re.S | re.I)
    c = re.sub(r'<(div|span|figure|figcaption)[^>]*>\s*</\1>', '', c, flags=re.S | re.I)
    c = re.sub(r'\r\n', '\n', c)
    return c.strip()


def fix_paragraphs(c):
    """WordPress 博客常以纯文本 + 空行分段（无 <p> 标签），自动包裹为段落。

    若正文已有块级元素，则不重复包裹，只规范化空行。
    """
    if not c:
        return ''
    if BLOCK_RE.search(c):
        return re.sub(r'\n\s*\n+', '\n\n', c)
    paras = re.split(r'\n\s*\n+', c)
    return '\n'.join(
        '<p>%s</p>' % p.strip().replace('\n', '<br>')
        for p in paras if p.strip()
    )


class _TagFixer(HTMLParser):
    """把任意 HTML 片段重写为合法 XHTML：空元素自闭合、标签配对闭合、转义文本。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.stack = []

    def _attrs(self, attrs):
        return ''.join(
            ' %s="%s"' % (k, html.escape(v, quote=True)) for k, v in attrs
        )

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t in VOID_TAGS:
            self.out.append('<%s%s/>' % (tag, self._attrs(attrs)))
        else:
            self.out.append('<%s%s>' % (tag, self._attrs(attrs)))
            self.stack.append(t)

    def handle_startendtag(self, tag, attrs):
        self.out.append('<%s%s/>' % (tag, self._attrs(attrs)))

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in VOID_TAGS:
            return
        if t in self.stack:
            while self.stack and self.stack[-1] != t:
                self.out.append('</%s>' % self.stack.pop())
            if self.stack:
                self.stack.pop()
            self.out.append('</%s>' % tag)
        # 多余闭合标签（无对应开标签）直接丢弃

    def handle_data(self, data):
        self.out.append(html.escape(data, quote=True))


def repair_fragment(c):
    """HTML 片段 → 合法 XHTML 片段（空元素自闭合 + 标签配对 + 实体处理）。"""
    if not c:
        return ''
    f = _TagFixer()
    f.feed(c)
    f.close()
    for t in reversed(f.stack):
        f.out.append('</%s>' % t)
    return ''.join(f.out)


# ---------- 解析 WordPress WXR XML ----------
def parse_wxr(path):
    """返回 (posts, cats, groups)。

    posts: [{id, title, date, cats:[..], content}]
    cats:  分类名按文章数降序
    groups:{分类名: [post_id, ...] 按日期升序}
    """
    with open(path, 'rb') as f:
        raw = f.read()
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        text = raw.decode('gb18030', errors='replace')
    root = ET.fromstring(ILLEGAL.sub('', text))

    posts = []
    for item in root.iter('item'):
        # 兼容不同 WXR 命名空间版本：按 tag 结尾匹配
        def field(suffix, default=''):
            for el in item:
                if el.tag.endswith('}' + suffix):
                    return (el.text or '').strip()
            return default

        post_type = field('post_type')
        status = field('status')
        if post_type != 'post' or status != 'publish':
            continue

        pid = field('post_id')
        title = field('title', '（无标题）')
        date = field('post_date')[:10]  # YYYY-MM-DD
        content = field('encoded')

        cats = [
            el.text.strip()
            for el in item.findall('category')
            if el.get('domain') == 'category' and el.text
        ]
        posts.append({
            'id': int(pid) if pid.isdigit() else len(posts) + 1,
            'title': title,
            'date': date,
            'cats': cats,
            'content': repair_fragment(fix_paragraphs(clean_content(content))),
        })

    # 每篇只归入第一个分类（避免一稿多归造成目录重复）
    group_map = {}
    for p in posts:
        cat = p['cats'][0] if p['cats'] else '未分类'
        group_map.setdefault(cat, []).append(p)

    cats = sorted(group_map.keys(), key=lambda c: -len(group_map[c]))
    groups = {
        cat: [p['id'] for p in sorted(group_map[cat], key=lambda p: p['date'])]
        for cat in cats
    }
    return posts, cats, groups


# ---------- EPUB 打包 ----------
CSS = """body { font-family: "PingFang SC", "Songti SC", serif; line-height: 1.8; margin: 1em 1.2em; color: #222; }
h1 { font-size: 1.7em; text-align: left; }
h2 { font-size: 1.4em; text-align: left; }
h3 { font-size: 1.15em; text-align: left; }
p { margin: 0 0 1em; }
.meta { color: #888; font-size: .85em; margin-bottom: 1.2em; }
.post-title { margin-bottom: .3em; }
.content { font-size: .98em; }
blockquote { border-left: 3px solid #ccc; margin: 1em 0; padding: .3em 1em; color: #555; }
a { color: #1a5276; }
img, object, embed, iframe, audio, video { display: none; }
code { font-family: Menlo, Consolas, monospace; background: #f4f4f4; padding: 1px 4px; border-radius: 3px; font-size: .9em; }
pre { background: #f6f8fa; padding: 1em; font-family: Menlo, Consolas, monospace; font-size: .9em; white-space: pre-wrap; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #ddd; padding: .4em .6em; }
.cat-list { list-style: none; padding: 0; }
.cat-list li { margin-bottom: .3em; }
.cat-list a { text-decoration: none; }
.cover { text-align: left; margin-top: 4em; }
.cover h1 { font-size: 2em; margin-bottom: .5em; }
.cover .sub { color: #666; margin: .5em 0; }
"""


def _xhtml(title, body, css_path='../css/epub.css'):
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN">\n<head>\n'
        '<meta charset="utf-8"/>\n'
        '<title>%s</title>\n'
        '<link rel="stylesheet" type="text/css" href="%s"/>\n'
        '</head>\n<body>\n%s\n</body>\n</html>'
        % (html.escape(title), css_path, body)
    )


def build_epub(posts, cats, groups, out, title, author, uid):
    posts_by_id = {p['id']: p for p in posts}
    files = {}  # 路径 -> 内容

    cover_body = (
        '<div class="cover">\n<h1>%s</h1>\n'
        '<p class="sub">作者：%s</p>\n'
        '<p class="sub">共 %d 篇文章 · %d 个分类</p>\n'
        '<p class="sub">正文图片与嵌入媒体（flash/音频/iframe 等）因资源失效已去除</p>\n'
        '</div>' % (title, author, len(posts), len(cats))
    )
    files['OEBPS/cover.xhtml'] = _xhtml(title, cover_body, 'css/epub.css')

    ncx_entries = []  # (playOrder, level, label, src)
    manifest = [
        ('ncx', 'toc.ncx', 'application/x-dtbncx+xml'),
        ('css', 'css/epub.css', 'text/css'),
        ('cover', 'cover.xhtml', 'application/xhtml+xml'),
    ]
    spine = ['cover']
    play = 0
    play += 1
    ncx_entries.append((play, 1, '封面', 'cover.xhtml'))

    for ci, cat in enumerate(cats):
        cat_id = 'cat-%d' % ci
        pids = groups[cat]
        lis = ''.join(
            '<li><a href="../p/%d.xhtml">%s</a> <span class="meta">（%s）</span></li>'
            % (pid, html.escape(posts_by_id[pid]['title']), posts_by_id[pid]['date'])
            for pid in pids
        )
        cat_body = (
            '<h1>%s <span class="meta">（%d篇）</span></h1>\n'
            '<ul class="cat-list">\n%s\n</ul>' % (html.escape(cat), len(pids), lis)
        )
        ch_path = 'ch/%s.xhtml' % cat_id
        files['OEBPS/' + ch_path] = _xhtml(cat, cat_body, '../css/epub.css')
        manifest.append((cat_id, ch_path, 'application/xhtml+xml'))
        spine.append(cat_id)  # 注意：spine 引用 manifest 的 id
        play += 1
        ncx_entries.append((play, 1, '%s（%d篇）' % (cat, len(pids)), ch_path))

        for pid in pids:
            p = posts_by_id[pid]
            p_body = (
                '<h2 class="post-title">%s</h2>\n'
                '<p class="meta">%s</p>\n'
                '<div class="content">%s</div>'
                % (html.escape(p['title']), p['date'], p['content'] or '<p>（正文为空）</p>')
            )
            ppath = 'p/%d.xhtml' % pid
            files['OEBPS/' + ppath] = _xhtml(p['title'], p_body, '../css/epub.css')
            pid_id = 'p-%d' % pid
            manifest.append((pid_id, ppath, 'application/xhtml+xml'))
            spine.append(pid_id)  # manifest 的 id
            play += 1
            ncx_entries.append((play, 2, p['title'], ppath))

    manifest_xml = ''.join(
        '<item id="%s" href="%s" media-type="%s"/>' % m for m in manifest
    )
    spine_xml = ''.join('<itemref idref="%s"/>' % s for s in spine)
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="zh-CN">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        '<dc:identifier id="bookid">%s</dc:identifier>\n'
        '<dc:title>%s</dc:title>\n'
        '<dc:creator>%s</dc:creator>\n'
        '<dc:language>zh-CN</dc:language>\n'
        '<meta property="dcterms:modified">2026-08-10T00:00:00Z</meta>\n'
        '</metadata>\n<manifest>\n%s\n</manifest>\n<spine>\n%s\n</spine>\n</package>'
        % (uid, html.escape(title), html.escape(author), manifest_xml, spine_xml)
    )

    # NCX：分类 navPoint 嵌套文章 navPoint，用栈正确闭合
    nav_buf = []
    stack = []
    for po, level, label, src in ncx_entries:
        if level == 1:
            while stack:
                nav_buf.append('  </navPoint>')
                stack.pop()
            nav_buf.append(
                '  <navPoint id="nav-%d" playOrder="%d"><navLabel><text>%s</text>'
                '</navLabel><content src="%s"/>' % (po, po, html.escape(label), src)
            )
            stack.append(1)
        else:
            nav_buf.append(
                '    <navPoint id="nav-%d" playOrder="%d"><navLabel><text>%s</text>'
                '</navLabel><content src="%s"/></navPoint>'
                % (po, po, html.escape(label), src)
            )
    while stack:
        nav_buf.append('  </navPoint>')
        stack.pop()
    ncx_xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'
        '<head><meta name="dtb:uid" content="%s"/><meta name="dtb:depth" content="2"/>'
        '<meta name="dtb:totalPageCount" content="0"/>'
        '<meta name="dtb:maxPageNumber" content="0"/></head>\n'
        '<docTitle><text>%s</text></docTitle>\n<navMap>\n%s\n</navMap>\n</ncx>'
        % (uid, html.escape(title), '\n'.join(nav_buf))
    )

    with zipfile.ZipFile(out, 'w') as z:
        # mimetype 必须是无压缩的第一个条目
        z.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        z.writestr(
            'META-INF/container.xml',
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>\n'
            '</container>',
        )
        z.writestr('OEBPS/content.opf', opf)
        z.writestr('OEBPS/toc.ncx', ncx_xml)
        z.writestr('OEBPS/css/epub.css', CSS)
        for path, content in files.items():
            z.writestr(path, content)

    return len(posts), len(cats)


# ---------- 验证 ----------
def verify_epub(path):
    """结构校验：所有 xhtml 为合法 XML、spine 全命中、无媒体残留。"""
    z = zipfile.ZipFile(path)
    names = z.namelist()

    problems = []

    # mimetype
    if names[0] != 'mimetype' or z.getinfo('mimetype').compress_type != 0:
        problems.append('mimetype 不是无压缩的首条目')

    # OPF spine 命中 manifest
    opf = z.read('OEBPS/content.opf').decode()
    manifest = dict(re.findall(r'<item id="([^"]+)" href="([^"]+)"', opf))
    spine_ids = re.findall(r'<itemref idref="([^"]+)"', opf)
    missing = [s for s in spine_ids if s not in manifest]
    if missing:
        problems.append('spine 未命中的 manifest id: %s' % missing[:5])

    # 所有 xhtml 合法
    bad_xml = []
    media = 0
    for n in names:
        if n.endswith('.xhtml'):
            raw = z.read(n)
            try:
                ET.fromstring(raw)
            except Exception as e:
                bad_xml.append((n, str(e)[:50]))
            if re.search(r'<(img|object|embed|iframe|audio|video|script)\b', raw.decode('utf-8', 'replace'), re.I):
                media += 1
    if bad_xml:
        problems.append('非法 XML 页面 %d 个，例: %s' % (len(bad_xml), bad_xml[:2]))
    if media:
        problems.append('含媒体残留页面 %d 个' % media)

    return problems


# ---------- 主入口 ----------
def main():
    ap = argparse.ArgumentParser(
        description='把 WordPress WXR XML 博客导出转换为标准 EPUB3 电子书'
    )
    ap.add_argument('xml', help='WordPress 导出 XML 文件路径')
    ap.add_argument('-o', '--out', help='输出 epub 路径（默认与 xml 同名 .epub）')
    ap.add_argument('-t', '--title', help='书名（默认取文件名的文章标题）')
    ap.add_argument('-a', '--author', default='', help='作者名')
    ap.add_argument('--no-verify', action='store_true', help='跳过打包后结构校验')
    args = ap.parse_args()

    if not os.path.exists(args.xml):
        print('错误: 找不到文件 %s' % args.xml, file=sys.stderr)
        sys.exit(1)

    posts, cats, groups = parse_wxr(args.xml)
    if not posts:
        print('错误: 未解析到任何已发布文章', file=sys.stderr)
        sys.exit(1)

    out = args.out or os.path.splitext(args.xml)[0] + '.epub'
    title = args.title or os.path.splitext(os.path.basename(args.xml))[0]
    uid = os.path.splitext(os.path.basename(out))[0]

    n, nc = build_epub(posts, cats, groups, out, title, args.author, uid)
    print('已生成: %s' % out)
    print('  文章 %d 篇 / 分类 %d 个 / 大小 %.2f MB'
          % (n, nc, os.path.getsize(out) / 1024 / 1024))

    if not args.no_verify:
        problems = verify_epub(out)
        if problems:
            print('验证发现问题:')
            for p in problems:
                print('  ✗ %s' % p)
            sys.exit(2)
        print('结构校验通过 ✓')


if __name__ == '__main__':
    main()
