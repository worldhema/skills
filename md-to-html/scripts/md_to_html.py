#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md_to_html.py — 将 Markdown 转为带左侧目录的单文件 HTML。

两种模式：
  普通模式  ：干净的带目录阅读页。
  审阅模式  ：提供 --backup（修订前版本），对全文做行级+字符级 diff，
              高亮本次新增内容，便于逐章审阅。

用法：
  python3 md_to_html.py 输入.md                          # 普通模式
  python3 md_to_html.py 输入.md -b 修订前.md             # 审阅模式（diff 高亮）
  python3 md_to_html.py 输入.md -o 输出.html -t "标题"   # 指定输出与标题

输出为自包含单文件 HTML（内联 CSS/JS），可直接打开、发送、打印。
"""
import argparse
import difflib
import html
import os
import re
import sys

# ----------------------------------------------------------------------
# diff 标记
# ----------------------------------------------------------------------
def mark_diff(old_lines, new_lines):
    """返回 (is_new, add_mask)。
    is_new[i]    : 第 i 行为整行新增
    add_mask[i]  : 第 i 行为部分新增，(start,end) 列表（字符级）
    """
    is_new = [False] * len(new_lines)
    add_mask = [None] * len(new_lines)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old_lines, new_lines).get_opcodes():
        if tag == "insert":
            for j in range(j1, j2):
                is_new[j] = True
        elif tag == "replace":
            o, n = old_lines[i1:i2], new_lines[j1:j2]
            if len(o) == len(n):
                for oline, nline, j in zip(o, n, range(j1, j2)):
                    if oline == nline:
                        continue
                    adds = []
                    for ctag, a, b, c, d in difflib.SequenceMatcher(None, oline, nline).get_opcodes():
                        if ctag in ("insert", "replace"):
                            adds.append((c, d))
                    if adds:
                        add_mask[j] = adds
            else:
                for j in range(j1, j2):
                    is_new[j] = True
    return is_new, add_mask

def esc(s):
    return html.escape(s, quote=False)

_INLINE_RE = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`")

def inline(text):
    """行内 Markdown → HTML：**加粗**、`代码`。输入原始文本，输出已转义 HTML。"""
    text = esc(text)
    def rep(m):
        if m.group(1) is not None:
            return "<strong>%s</strong>" % m.group(1)
        return "<code>%s</code>" % m.group(2)
    return _INLINE_RE.sub(rep, text)

PUNCT = set("，。、；：？！（）《》“”‘’…—·,.;:!?()[] 　\"'")
def is_punct(s):
    return bool(s) and all(c in PUNCT for c in s)

def apply_adds(text, adds):
    """把部分新增的字符级区间包成 <mark>（内容）或 <span class="mk-punct">（标点）。"""
    if not adds:
        return esc(text)
    parts = [esc(text[:adds[0][0]])]
    for i, (s, e) in enumerate(adds):
        seg = text[s:e]
        if is_punct(seg):
            parts.append('<span class="mk-punct">' + esc(seg) + "</span>")
        else:
            parts.append("<mark>" + esc(seg) + "</mark>")
        nxt = adds[i + 1][0] if i + 1 < len(adds) else len(text)
        parts.append(esc(text[e:nxt]))
    return "".join(parts)

# ----------------------------------------------------------------------
# 渲染
# ----------------------------------------------------------------------
HEAD_RE = re.compile(r"^(#{1,4})\s+(.*)$")
TABLE_RE = re.compile(r"^[+|]")
BOX_RE = re.compile(r"^[┌┐└┘├┤┬┴┼│]")   # ASCII/框线手绘图块（架构图等）
FENCE_RE = re.compile(r"^\s*(```+|~~~+)(.*)$")   # 围栏代码块
QUOTE_RE = re.compile(r"^>\s?")                   # 引用块
HR_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")   # 水平分隔线
UL_RE = re.compile(r"^\s*[-*+]\s+")               # 无序列表
OL_RE = re.compile(r"^\s*\d+[.)]\s+")             # 有序列表

# ---- 标准 Markdown 表格解析（`| a | b |` 形式 → 真 <table>）----
def is_sep_row(line):
    """判断是否为 Markdown 表格分隔行（去掉 | : 空格后只剩 -）。"""
    s = line.replace("|", "").replace(":", "").replace(" ", "").replace("\t", "")
    return bool(s) and all(c == "-" for c in s)

def split_cells(row):
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [c.strip() for c in row.split("|")]

def parse_md_table(block):
    """把含分隔行的标准 Markdown 表格块解析为 <table> HTML；单元格内容走 inline()。"""
    sep_idx = next(i for i, r in enumerate(block) if is_sep_row(r))
    header_rows = [r for r in block[:sep_idx] if r.strip()]
    body_rows = [r for r in block[sep_idx + 1:] if r.strip()]
    out = ["<table>"]
    if header_rows:
        out.append("<thead><tr>")
        for c in split_cells(header_rows[0]):
            out.append("<th>%s</th>" % inline(c))
        out.append("</tr></thead>")
    out.append("<tbody>")
    for r in body_rows:
        out.append("<tr>")
        for c in split_cells(r):
            out.append("<td>%s</td>" % inline(c))
        out.append("</tr>")
    out.append("</tbody></table>")
    return "".join(out)

def build_document(new_lines, review_mode, is_new, add_mask):
    toc = []          # (level, title, anchor, is_new)
    body = []         # html 行
    id_counter = [0]
    new_char_count = 0
    new_block_count = 0

    def h_id():
        id_counter[0] += 1
        return "h-%d" % id_counter[0]

    def emit_text_line(i):
        nonlocal new_char_count, new_block_count
        line = new_lines[i]
        if not line.strip():
            return
        if is_new[i]:
            new_block_count += 1
            new_char_count += len(line)
            body.append('<p class="p new">%s</p>' % inline(line))
        elif add_mask[i]:
            new_char_count += sum(e - s for s, e in add_mask[i] if not is_punct(line[s:e]))
            body.append('<p class="p">%s</p>' % apply_adds(line, add_mask[i]))
        else:
            body.append('<p class="p">%s</p>' % inline(line))

    i, n = 0, len(new_lines)
    while i < n:
        line = new_lines[i]
        mf = FENCE_RE.match(line)
        if mf:
            # ``` 围栏代码块
            fence = mf.group(1)
            lang = mf.group(2).strip()
            j = i + 1
            buf = []
            close_re = re.compile(r"^\s*" + re.escape(fence) + r"\s*$")
            while j < n and not close_re.match(new_lines[j]):
                buf.append(new_lines[j])
                j += 1
            if j < n:
                j += 1   # 跳过闭合围栏
            lang_cls = ' lang="%s"' % esc(lang) if lang else ""
            body.append('<pre class="codefence"><code%s>%s</code></pre>'
                        % (lang_cls, esc("\n".join(buf))))
            i = j
            continue
        m = HEAD_RE.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2)
            aid = h_id()
            htag = min(level, 4)   # # → h1, ## → h2, ### → h3, #### → h4
            if is_new[i]:
                new_block_count += 1
                body.append('<h%d id="%s" class="new-heading">%s <span class="tag-new">新增</span></h%d>'
                            % (htag, aid, inline(title), htag))
            else:
                body.append('<h%d id="%s">%s</h%d>' % (htag, aid, inline(title), htag))
            if level >= 2:   # 最高级标题作页眉，不进目录
                toc.append((level, title, aid, is_new[i]))
            i += 1
            continue
        if BOX_RE.match(line) and line.strip():
            # 框线/ASCII 架构图 → 等宽 pre 保留（含 │ ┌ ├ 等制表符的连续块）
            j = i + 1
            while j < n and new_lines[j].strip() and BOX_RE.match(new_lines[j]):
                j += 1
            block_new = any(is_new[k] for k in range(i, j))
            cls = "codeblock new" if block_new else "codeblock"
            body.append('<div class="%s"><pre>%s</pre></div>' % (cls, esc("\n".join(new_lines[i:j]))))
            if block_new:
                new_block_count += 1
            i = j
            continue
        if TABLE_RE.match(line) and line.strip():
            j = i
            while j < n and (TABLE_RE.match(new_lines[j])
                             or (not new_lines[j].strip() and j + 1 < n and TABLE_RE.match(new_lines[j + 1]))):
                j += 1
            block = new_lines[i:j]
            block_new = any(is_new[k] for k in range(i, j))
            if any(is_sep_row(r) for r in block):
                # 标准 Markdown 表格（含 |---| 分隔行）→ 真 <table>
                cls = "mdtable new" if block_new else "mdtable"
                body.append('<div class="%s"><div class="tbl-wrap">%s</div></div>'
                            % (cls, parse_md_table(block)))
            else:
                # ASCII 手绘图/纯 | 文本块 → 等宽 pre 保留
                cls = "table new" if block_new else "table"
                body.append('<div class="%s"><pre>%s</pre></div>' % (cls, esc("\n".join(block))))
            if block_new:
                new_block_count += 1
            i = j
            continue
        if QUOTE_RE.match(line):
            # > 引用块：连续 > 行合并，空行作为段落分隔
            j = i
            paras = []
            cur = []
            while j < n:
                q = new_lines[j]
                if q.startswith(">"):
                    cur.append(q[1:].strip())
                    j += 1
                elif not q.strip() and j + 1 < n and new_lines[j + 1].startswith(">"):
                    if cur:
                        paras.append(cur)
                        cur = []
                    j += 1
                else:
                    break
            if cur:
                paras.append(cur)
            qp = "".join("".join("<p>%s</p>" % inline(x) for x in para if x)
                         for para in paras)
            body.append("<blockquote>%s</blockquote>" % qp)
            i = j
            continue
        if HR_RE.match(line):
            # --- 水平分隔线
            body.append("<hr%s>" % (' class="new"' if is_new[i] else ""))
            i += 1
            continue
        if UL_RE.match(line) or OL_RE.match(line):
            # 无序/有序列表：连续同类合并为一级列表
            ordered = bool(OL_RE.match(line))
            j = i
            items = []
            while j < n:
                q = new_lines[j]
                if not q.strip():
                    nxt = new_lines[j + 1] if j + 1 < n else ""
                    if (OL_RE.match(nxt) if ordered else UL_RE.match(nxt)):
                        j += 1
                        continue
                    break
                is_ol = bool(OL_RE.match(q))
                if is_ol != ordered:
                    break
                mm = (OL_RE if is_ol else UL_RE).match(q)
                items.append(q[mm.end():].strip())
                j += 1
            tag = "ol" if ordered else "ul"
            body.append("<%s>%s</%s>" % (tag,
                        "".join("<li>%s</li>" % inline(x) for x in items if x), tag))
            i = j
            continue
        emit_text_line(i)
        i += 1
    return toc, body, new_char_count, new_block_count

def render_toc(toc):
    """平铺标题序列 → 嵌套 ul。"""
    depth_class = {2: "tl-2", 3: "tl-3", 4: "tl-4"}
    idx = [0]

    def rec(level):
        items = []
        while idx[0] < len(toc):
            lvl, title, aid, tnew = toc[idx[0]]
            if lvl < level:
                break
            if lvl == level:
                idx[0] += 1
                inner = rec(level + 1)
                badge = '<span class="toc-new">新</span>' if tnew else ""
                items.append('<li class="%s"><a href="#%s">%s%s</a>%s</li>'
                             % (depth_class.get(lvl, "tl-%d" % lvl), aid, esc(title), badge, inner))
            else:
                items.append(rec(lvl))   # 悬空层级上提
        return "<ul>%s</ul>" % "".join(items)

    return rec(2)

# ----------------------------------------------------------------------
# 模板
# ----------------------------------------------------------------------
CSS = """
:root{--side-w:290px;--bg:#f5f5f2;--card:#ffffff;--ink:#2b2b2b;--muted:#8a8a8a;
--line:#e6e4df;--accent:#2e7d32;--mark-bg:#fff3a3;--new-bg:#f0f8ef;--new-border:#4caf50;}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC",sans-serif;background:var(--bg);color:var(--ink);line-height:1.85;font-size:16px}
#side{position:fixed;top:0;left:0;bottom:0;width:var(--side-w);background:#fff;border-right:1px solid var(--line);overflow-y:auto;z-index:20;padding:16px 0 40px}
#side .side-title{padding:8px 20px 14px;font-size:15px;font-weight:700;color:var(--muted);letter-spacing:.5px;border-bottom:1px solid var(--line)}
#side ul{list-style:none;margin:0;padding:0}
#side li a{display:block;padding:5px 20px;color:#444;text-decoration:none;font-size:13.5px;border-left:3px solid transparent;transition:background .15s,color .15s}
#side li.tl-2>a{font-weight:700;padding-top:10px;color:#1f5d24}
#side li.tl-3>a{padding-left:34px;color:#555}
#side li.tl-4>a{padding-left:52px;font-size:12.5px;color:#777}
#side li a:hover{background:#f0f8ef;color:#1f5d24}
#side li a.active{background:#e7f4e6;color:#1f5d24;border-left-color:var(--accent)}
#side li a .toc-new{display:inline-block;font-size:10px;color:#c0392b;margin-left:4px}
#main{margin-left:var(--side-w);padding:28px 48px 120px;max-width:1000px}
#main.noside{margin-left:0;max-width:880px;margin-right:auto}
.banner{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:22px 28px;margin:8px 0 26px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px}
.banner h1{margin:0 0 4px;font-size:24px}
.banner p{margin:0;color:var(--muted);font-size:13px}
.banner-stats{display:flex;align-items:center;gap:22px}
.stat{text-align:center}
.stat b{display:block;font-size:22px;color:var(--accent)}
.stat span{font-size:11px;color:var(--muted)}
.switch{display:flex;align-items:center;gap:8px;font-size:13px;color:#555;cursor:pointer;user-select:none}
#content h1{font-size:30px;margin:6px 0 12px;color:#174d1a;border-bottom:2px solid #cfd8cf;padding-bottom:10px}
h2{font-size:26px;border-bottom:2px solid #e2efe0;padding-bottom:10px;margin:52px 0 18px;color:#174d1a}
h3{font-size:21px;margin:38px 0 12px;color:#1f5d24}
h4{font-size:17.5px;margin:30px 0 10px;color:#333}
.tag-new{display:inline-block;font-size:11px;font-weight:600;color:#fff;background:#4caf50;border-radius:3px;padding:1px 7px;margin-left:10px;vertical-align:middle;letter-spacing:1px}
p{margin:0 0 14px;text-align:justify}
p.new{background:var(--new-bg);border-left:4px solid var(--new-border);border-radius:0 6px 6px 0;padding:8px 14px}
mark{background:var(--mark-bg);color:inherit;border-radius:3px;padding:0 2px}
.mk-punct{background:#f2f2ef;color:#b3b0ab;border-radius:2px}
body.hide-punct .mk-punct{background:inherit;color:inherit}
strong{font-weight:700;color:#1d3b1f}
code{background:#f2f2ef;border-radius:3px;padding:1px 5px;font-family:"SF Mono",Menlo,Consolas,"Courier New",monospace;font-size:.9em;color:#a3442b}
blockquote{background:#f7f7f4;border-left:4px solid var(--accent);border-radius:0 8px 8px 0;margin:14px 0;padding:2px 18px;color:#4a4a4a}
blockquote p{margin:10px 0;color:#4a4a4a}
blockquote strong{color:var(--accent)}
hr{border:none;border-top:1px solid var(--line);margin:34px 0}
hr.new{border-top-color:var(--new-border)}
#content ul,#content ol{margin:0 0 14px;padding-left:1.6em}
#content li{margin:4px 0}
#content li p{margin:0}
.codefence{background:#fafaf8;border:1px solid var(--line);border-radius:8px;margin:14px 0;overflow-x:auto}
.codefence code{background:transparent;padding:0;display:block;padding:14px 16px;font-family:"SF Mono",Menlo,Consolas,"Courier New",monospace;font-size:13px;line-height:1.6;color:#333}
.table{background:#fff;border:1px solid var(--line);border-radius:8px;margin:14px 0;overflow-x:auto}
.table pre{font-family:"SF Mono",Menlo,Consolas,"Courier New",monospace;font-size:12.5px;line-height:1.5;padding:14px 16px;margin:0;color:#333}
.table.new{border-color:var(--new-border)}
.table.new pre{background:var(--new-bg)}
.mdtable{background:#fff;border:1px solid var(--line);border-radius:8px;margin:14px 0}
.tbl-wrap{overflow-x:auto}
.codeblock{background:#fafaf8;border:1px solid var(--line);border-radius:8px;margin:14px 0;overflow-x:auto}
.codeblock pre{font-family:"SF Mono",Menlo,Consolas,"Courier New",monospace;font-size:13px;line-height:1.6;padding:14px 16px;margin:0;color:#333}
.codeblock.new{border-color:var(--new-border)}
.mdtable table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.65}
.mdtable th,.mdtable td{border:1px solid var(--line);padding:8px 12px;text-align:left;vertical-align:top}
.mdtable th{background:#f0f8ef;color:#1f5d24;font-weight:600;white-space:nowrap}
.mdtable tbody tr:nth-child(even) td{background:#fafaf8}
.mdtable.new{border-color:var(--new-border)}
body.hide-new p.new{background:transparent;border-left-color:transparent}
body.hide-new .table.new{border-color:var(--line)}
body.hide-new .table.new pre{background:transparent}
body.hide-new mark{background:inherit}
body.hide-new .mk-punct{background:inherit;color:inherit}
body.hide-new .tag-new{display:none}
@media (max-width:800px){
  #side{position:static;width:100%;height:auto;max-height:40vh;border-right:none;border-bottom:1px solid var(--line)}
  #main{margin-left:0;padding:20px 18px 90px}
}
"""

JS = """
var links=Array.prototype.slice.call(document.querySelectorAll('#side a[href^="#"]'));
var heads=links.map(function(a){return document.getElementById(a.getAttribute('href').slice(1));});
function onScroll(){
  var pos=window.scrollY+120,cur=null;
  heads.forEach(function(h){if(h&&h.offsetTop<=pos)cur=h;});
  links.forEach(function(a){a.classList.remove('active');});
  if(cur){var a=links.filter(function(x){return x.getAttribute('href')==='#'+cur.id;})[0];if(a)a.classList.add('active');}
}
window.addEventListener('scroll',onScroll,{passive:true});
document.addEventListener('DOMContentLoaded',onScroll);
var tg=document.getElementById('toggleNew');if(tg)tg.addEventListener('change',function(e){document.body.classList.toggle('hide-new',!e.target.checked);});
var tp=document.getElementById('togglePunct');if(tp)tp.addEventListener('change',function(e){document.body.classList.toggle('hide-punct',!e.target.checked);});
"""

def make_html(page_title, lang, toc_html, stats, body, review_mode, has_toc):
    side = ('<nav id="side"><div class="side-title">目录</div>%s</nav>' % toc_html) if has_toc else ""
    main_cls = 'id="main"' if has_toc else 'id="main" class="noside"'
    body_extra = ' class="hide-punct"' if review_mode else ""
    return """<!DOCTYPE html>
<html lang="%s">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<style>%s</style>
</head>
<body%s>
%s
<div %s>
%s
<div id="content">
%s
</div>
</div>
<script>%s</script>
</body>
</html>""" % (lang, esc(page_title), CSS, body_extra, side, main_cls, stats, "\n".join(body), JS)

# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="将 Markdown 转为带左侧目录的单文件 HTML；提供 --backup 时高亮本次新增内容（审阅模式）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  md_to_html.py 书稿.md\n"
               "  md_to_html.py 书稿.md -b 书稿-修订前.md -o 审阅稿.html -t \"《书稿》审阅稿\"")
    ap.add_argument("input", help="输入 Markdown 文件")
    ap.add_argument("-o", "--output", help="输出 HTML 路径（默认与输入同名 .html）")
    ap.add_argument("-b", "--backup", help="修订前版本（Markdown），用于 diff 高亮本次新增")
    ap.add_argument("-t", "--title", help="页面标题（默认取文件名）")
    ap.add_argument("--lang", default="zh-CN", help="页面语言，默认 zh-CN")
    ap.add_argument("--no-banner", action="store_true", help="不显示顶部信息条")
    ap.add_argument("-q", "--quiet", action="store_true", help="静默，不打印统计")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        sys.exit("输入文件不存在：%s" % args.input)
    with open(args.input, encoding="utf-8") as f:
        new_lines = f.read().split("\n")

    review_mode = False
    old_lines = None
    if args.backup:
        if not os.path.exists(args.backup):
            sys.exit("备份文件不存在：%s" % args.backup)
        with open(args.backup, encoding="utf-8") as f:
            old_lines = f.read().split("\n")
        review_mode = True

    is_new, add_mask = (mark_diff(old_lines, new_lines) if review_mode
                        else ([False] * len(new_lines), [None] * len(new_lines)))

    toc, body, new_char, new_block = build_document(new_lines, review_mode, is_new, add_mask)
    toc_html = render_toc(toc)

    page_title = args.title or os.path.splitext(os.path.basename(args.input))[0]

    if args.no_banner:
        stats = ""
    elif review_mode:
        stats = """<div class="banner">
  <div class="banner-main">
    <h1>%s · 审阅稿</h1>
    <p>全文 %d 行（修订前 %d 行）｜绿色块＝新增段落，黄色标记＝句中新增</p>
  </div>
  <div class="banner-stats">
    <div class="stat"><b>%d</b><span>新增段落/标题</span></div>
    <div class="stat"><b>%d</b><span>新增字符</span></div>
    <label class="switch"><input type="checkbox" id="toggleNew" checked> <span>高亮新增</span></label>
    <label class="switch"><input type="checkbox" id="togglePunct"> <span>标点改动</span></label>
  </div>
</div>""" % (esc(page_title), len(new_lines), len(old_lines), new_block, new_char)
    else:
        stats = """<div class="banner">
  <div class="banner-main">
    <h1>%s</h1>
    <p>共 %d 行</p>
  </div>
</div>""" % (esc(page_title), len(new_lines))

    out = args.output or (os.path.splitext(args.input)[0] + ".html")
    html_doc = make_html(page_title, args.lang, toc_html, stats, body, review_mode, bool(toc))

    with open(out, "w", encoding="utf-8") as f:
        f.write(html_doc)

    if not args.quiet:
        mode = "审阅模式" if review_mode else "普通模式"
        extra = "，新增段落/标题 %d，新增字符 %d" % (new_block, new_char) if review_mode else ""
        print("已生成（%s）：%s" % (mode, out))
        print("  目录项 %d，%d 行%s" % (len(toc), len(new_lines), extra))

if __name__ == "__main__":
    main()
