#!/usr/bin/env node
/**
 * md2book - Markdown 书籍转 PDF 转换器
 *
 * 用法: node md2book.js <input.md> [options]
 *
 * 选项:
 *   --theme <name>    视觉主题: minimal(默认), academic, playful
 *   --output <path>   输出 PDF 路径（默认与输入文件同级）
 *   --no-toc          不生成目录
 *   --verbose         显示详细日志
 */

import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from 'fs';
import { join, dirname, basename, extname, resolve } from 'path';
import { fileURLToPath } from 'url';
import MarkdownIt from 'markdown-it';
import markdownItAnchor from 'markdown-it-anchor';
import markdownItFrontMatter from 'markdown-it-front-matter';
import markdownItToc from 'markdown-it-table-of-contents';
import hljs from 'highlight.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ASSETS_DIR = join(__dirname, '..', 'assets');
const STYLES_DIR = join(ASSETS_DIR, 'styles');
const TEMPLATES_DIR = join(ASSETS_DIR, 'templates');

// =====================================================
// CLI 参数解析
// =====================================================

function parseArgs(argv) {
  const args = argv.slice(2);
  const opts = {
    input: null,
    theme: 'minimal',
    output: null,
    toc: true,
    verbose: false,
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--theme':
        opts.theme = args[++i] || 'minimal';
        break;
      case '--output':
        opts.output = args[++i];
        break;
      case '--no-toc':
        opts.toc = false;
        break;
      case '--verbose':
        opts.verbose = true;
        break;
      case '--help':
      case '-h':
        printHelp();
        process.exit(0);
      default:
        if (!opts.input) opts.input = args[i];
    }
  }

  if (!opts.input) {
    console.error('错误: 请指定输入的 Markdown 文件路径');
    printHelp();
    process.exit(1);
  }

  if (!['minimal', 'academic', 'playful'].includes(opts.theme)) {
    console.error(`错误: 不支持的主题 "${opts.theme}"，可选: minimal, academic, playful`);
    process.exit(1);
  }

  return opts;
}

function printHelp() {
  console.log(`
用法: node md2book.js <input.md> [选项]

选项:
  --theme <name>   视觉主题: minimal(默认), academic, playful
  --output <path>  输出 PDF 路径
  --no-toc         不生成目录
  --verbose        显示详细日志
  --help, -h       显示帮助

示例:
  node md2book.js book.md
  node md2book.js book.md --theme academic
  node md2book.js book.md --output ./output/book.pdf
`);
}

// =====================================================
// Markdown 解析
// =====================================================

function createMarkdownParser(onFrontMatter) {
  const md = new MarkdownIt({
    html: true,
    breaks: false,
    linkify: true,
    typographer: true,
    highlight(str, lang) {
      if (lang && hljs.getLanguage(lang)) {
        try {
          return hljs.highlight(str, { language: lang }).value;
        } catch (e) { /* fallback */ }
      }
      return md.utils.escapeHtml(str);
    }
  });

  // 解析 YAML frontmatter
  if (onFrontMatter) {
    md.use(markdownItFrontMatter, onFrontMatter);
  }

  // 锚点
  md.use(markdownItAnchor, {
    level: [1, 2, 3],
    slugify: (s) => encodeURIComponent(String(s).trim().toLowerCase()),
    permalink: false,
  });

  // 目录（可选，也在 HTML 层面生成）
  md.use(markdownItToc, {
    includeLevel: [1, 2],
    containerClass: 'toc',
    slugify: (s) => encodeURIComponent(String(s).trim().toLowerCase()),
  });

  // 渲染 callout 语法
  md.core.ruler.after('inline', 'callout', (state) => {
    // 将 [!INFO] 等 callout 语法转为 HTML
    const tokens = state.tokens;
    for (let i = 0; i < tokens.length; i++) {
      if (tokens[i].type === 'paragraph_open' && i + 2 < tokens.length) {
        const content = tokens[i + 1].content;
        const match = content.match(/^\[!(INFO|TIP|WARNING|DANGER)\]\s*(.*)/);
        if (match) {
          const type = match[1].toLowerCase();
          const title = match[2] || type.charAt(0).toUpperCase() + type.slice(1);
          const body = tokens[i + 1].content.replace(/^\[!\w+\]\s*/, '');

          // 替换当前段落
          tokens[i + 1].content = '';
          tokens[i + 1].type = 'html_inline';

          // 在 inline 后面插入 callout HTML
          const calloutHTML = `<div class="callout callout-${type}">
            <div class="callout-title">${title}</div>
            <div class="callout-content"><p>${body}</p></div>
          </div>`;

          // 添加一个 raw HTML token
          const htmlToken = new state.Token('html_inline', '', 0);
          htmlToken.content = calloutHTML;
          tokens.splice(i + 2, 0, htmlToken);
        }
      }
    }
  });

  return md;
}

// =====================================================
// YAML frontmatter 简易解析
// =====================================================

function parseYamlFrontMatter(text) {
  const meta = {};
  const lines = text.split('\n');
  for (const line of lines) {
    const match = line.match(/^(\w+):\s*(.*)$/);
    if (match) {
      const key = match[1].trim();
      const val = match[2].trim().replace(/^["']|["']$/g, '');
      meta[key] = val;
    }
  }
  return meta;
}

// =====================================================
// HTML 组装
// =====================================================

function generateTOCFromMarkdown(md, html) {
  // 从已渲染的 HTML 中提取标题生成 TOC
  const headingRegex = /<h([12])[^>]*>(.*?)<\/h\1>/gi;
  const tocItems = [];
  let match;

  while ((match = headingRegex.exec(html)) !== null) {
    const level = parseInt(match[1]);
    const text = match[2].replace(/<[^>]+>/g, '').trim();
    const slug = encodeURIComponent(text.toLowerCase());
    tocItems.push({ level, text, slug });
  }

  if (tocItems.length === 0) return '';

  let tocHtml = '<div class="toc"><h2>目录</h2><ul>';
  for (const item of tocItems) {
    const indent = item.level === 2 ? ' style="margin-left: 1.5em; font-size: 9.5pt;"' : '';
    tocHtml += `<li${indent}><a href="#${item.slug}">${item.text}</a></li>`;
  }
  tocHtml += '</ul></div>';
  return tocHtml;
}

function wrapChapterTitles(html) {
  // 给每个 H1 添加 slug id 以便锚点链接
  return html.replace(/<h1>(.*?)<\/h1>/gi, (match, content) => {
    const slug = encodeURIComponent(content.replace(/<[^>]+>/g, '').trim().toLowerCase());
    return `<h1 id="${slug}">${content}</h1>`;
  }).replace(/<h2>(.*?)<\/h2>/gi, (match, content) => {
    const slug = encodeURIComponent(content.replace(/<[^>]+>/g, '').trim().toLowerCase());
    return `<h2 id="${slug}">${content}</h2>`;
  });
}

function buildFullHTML({
  bodyContent,
  metadata,
  themeName,
  tocEnabled,
  tocHtml,
  cssPaths,
}) {
  const { title, subtitle, author, date, isbn, description, version, publisher } = metadata;
  const year = date ? date.substring(0, 4) : new Date().getFullYear().toString();

  const themeCSS = cssPaths.theme || '';

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${title || '书籍'}</title>
<style>
/* CSS Variables */
:root {
  --accent-color: #333;
  --text-color: #333;
  --border-color: #eee;
  --bg-color: #fff;
  --link-color: #2563eb;
  --emphasis-color: #111;
  --code-bg: #f5f5f5;
  --code-text: #c7254e;
  --code-block-bg: #1e1e1e;
  --code-block-header-bg: #2d2d2d;
  --code-block-text: #d4d4d4;
  --table-header-bg: #f8f9fa;
  --table-stripe-bg: #fafbfc;
  --table-hover-bg: #f0f4ff;
  --blockquote-bg: #f8fafc;
  --blockquote-text: #555;
}

/* Reset */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body {
  margin: 0;
  padding: 0;
  background: white;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Page size for PDF generation */
@page {
  size: A4;
  margin: 25mm 20mm 25mm 20mm;
  @bottom-center {
    content: counter(page);
    font-family: "Source Han Serif CN", "STSong", "Songti SC", serif;
    font-size: 9pt;
    color: #999;
  }
}

@page cover {
  margin: 0;
  @bottom-center { content: none; }
}

@page copyright {
  @top-left { content: none; }
  @top-right { content: none; }
}

${themeCSS}

/* Base typography */
.book-body {
  font-size: 10.5pt;
  line-height: 1.85;
  color: var(--text-color, #333);
  font-family: "Source Han Serif CN", "STSong", "Songti SC", "SimSun", serif;
  text-align: justify;
  text-justify: inter-ideograph;
  hyphens: none;
  padding: 0;
}

/* Headings */
.book-body h1, .book-body h2, .book-body h3, .book-body h4 {
  font-family: "PingFang SC", "Heiti SC", "Microsoft YaHei", sans-serif;
}

.book-body h1 {
  font-size: 22pt;
  margin-top: 40pt;
  margin-bottom: 16pt;
  padding-top: 20pt;
  break-before: page;
  border-top: 2px solid var(--accent-color, #333);
}

.book-body h2 {
  font-size: 16pt;
  margin-top: 28pt;
  margin-bottom: 12pt;
  padding-bottom: 6pt;
  border-bottom: 1px solid var(--border-color, #eee);
  break-after: avoid;
}

.book-body h3 {
  font-size: 13pt;
  margin-top: 20pt;
  margin-bottom: 8pt;
  break-after: avoid;
}

.book-body p {
  margin-bottom: 8pt;
  line-height: 1.85;
}

/* Links */
.book-body a {
  color: var(--link-color, #2563eb);
  text-decoration: none;
  border-bottom: 1px solid var(--link-color, #2563eb);
}

/* Lists */
.book-body ul, .book-body ol {
  margin: 8pt 0;
  padding-left: 2em;
}

.book-body li {
  margin-bottom: 4pt;
  line-height: 1.7;
}

/* Inline code */
.book-body code:not(pre code) {
  font-family: "SF Mono", "Menlo", "Monaco", monospace;
  font-size: 0.88em;
  background: var(--code-bg, #f5f5f5);
  padding: 1px 5px;
  border-radius: 3px;
  color: var(--code-text, #c7254e);
}

/* Code blocks */
.book-body pre {
  margin: 14pt 0;
  padding: 16px 18px;
  background: var(--code-block-bg, #1e1e1e);
  border-radius: 8px;
  overflow-x: auto;
  font-size: 8.5pt;
  line-height: 1.6;
  tab-size: 2;
  break-inside: avoid;
}

.book-body pre code {
  background: none;
  padding: 0;
  border-radius: 0;
  color: var(--code-block-text, #d4d4d4);
  font-size: inherit;
}

/* Syntax highlighting */
.book-body .hljs-keyword { color: #569cd6; }
.book-body .hljs-string { color: #ce9178; }
.book-body .hljs-number { color: #b5cea8; }
.book-body .hljs-comment { color: #6a9955; font-style: italic; }
.book-body .hljs-function { color: #dcdcaa; }
.book-body .hljs-class { color: #4ec9b0; }
.book-body .hljs-type { color: #4ec9b0; }
.book-body .hljs-variable { color: #9cdcfe; }
.book-body .hljs-built_in { color: #4ec9b0; }
.book-body .hljs-literal { color: #569cd6; }
.book-body .hljs-tag { color: #569cd6; }
.book-body .hljs-attr { color: #9cdcfe; }
.book-body .hljs-title { color: #dcdcaa; }
.book-body .hljs-meta { color: #c586c0; }

/* Tables */
.book-body table {
  width: 100%;
  margin: 16pt 0;
  border-collapse: collapse;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  font-size: 9pt;
  break-inside: avoid;
}

.book-body thead {
  background: var(--table-header-bg, #f8f9fa);
}

.book-body th {
  font-weight: 600;
  padding: 10px 14px;
  text-align: left;
  border-bottom: 2px solid var(--accent-color, #333);
}

.book-body td {
  padding: 9px 14px;
  border-bottom: 1px solid #eee;
}

.book-body tbody tr:nth-child(even) {
  background: var(--table-stripe-bg, #fafbfc);
}

/* Blockquotes */
.book-body blockquote {
  margin: 16pt 0;
  padding: 14px 20px;
  border-left: 4px solid var(--accent-color, #3b82f6);
  background: var(--blockquote-bg, #f8fafc);
  border-radius: 0 6px 6px 0;
  color: var(--blockquote-text, #555);
  font-style: italic;
  break-inside: avoid;
}

/* Callouts */
.book-body .callout {
  margin: 16pt 0;
  padding: 14px 18px;
  border-radius: 8px;
  border-left: 4px solid;
  break-inside: avoid;
}
.book-body .callout-title {
  font-weight: 700;
  font-size: 10pt;
  margin-bottom: 4px;
}
.book-body .callout-info {
  background: #eff6ff;
  border-color: #3b82f6;
  color: #1e40af;
}
.book-body .callout-tip {
  background: #f0fdf4;
  border-color: #22c55e;
  color: #166534;
}
.book-body .callout-warning {
  background: #fffbeb;
  border-color: #f59e0b;
  color: #92400e;
}
.book-body .callout-danger {
  background: #fef2f2;
  border-color: #ef4444;
  color: #991b1b;
}

/* Images */
.book-body figure {
  margin: 20pt 0;
  text-align: center;
  break-inside: avoid;
}
.book-body figure img {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.book-body figcaption {
  font-size: 8.5pt;
  color: #888;
  margin-top: 8pt;
  text-align: center;
  font-style: italic;
}

/* Horizontal rule */
.book-body hr {
  border: none;
  height: 1px;
  background: linear-gradient(to right, transparent, #ddd, transparent);
  margin: 28pt 0;
}

/* TOC */
.book-body .toc {
  margin: 20pt 0;
  break-after: page;
}
.book-body .toc h2 {
  font-size: 20pt;
  border-bottom: none;
  text-align: center;
  margin-bottom: 24pt;
}
.book-body .toc ul {
  list-style: none;
  padding-left: 0;
}
.book-body .toc > ul > li {
  margin-bottom: 6pt;
  padding-bottom: 6pt;
  border-bottom: 1px dotted #ddd;
}
.book-body .toc li a {
  text-decoration: none;
  border-bottom: none;
  color: var(--text-color, #333);
}
.book-body .toc ul ul {
  padding-left: 1.5em;
  margin-top: 4pt;
}
.book-body .toc ul ul li {
  font-size: 9.5pt;
  margin-bottom: 3pt;
}

/* Cover page */
.cover-page {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 60px 40px;
  page: cover;
}
.cover-page .cover-title {
  font-size: 36pt;
  font-weight: 800;
  color: #111;
  text-align: center;
  letter-spacing: 4px;
  line-height: 1.3;
  margin-bottom: 24px;
}
.cover-page .cover-subtitle {
  font-size: 16pt;
  font-weight: 300;
  color: #666;
  text-align: center;
  margin-bottom: 48px;
  letter-spacing: 2px;
}
.cover-page .cover-divider {
  width: 60px;
  height: 2px;
  background: #111;
  margin: 0 auto 48px;
}
.cover-page .cover-author {
  font-size: 12pt;
  color: #555;
  text-align: center;
  letter-spacing: 6px;
  text-transform: uppercase;
}
.cover-page .cover-date {
  font-size: 9pt;
  color: #999;
  margin-top: 12px;
  text-align: center;
}

/* Copyright page */
.copyright-page {
  min-height: 100vh;
  padding: 60px 40px 40px;
  page: copyright;
}
.copyright-page .copyright-title {
  font-size: 18pt;
  font-weight: 700;
  color: #333;
  margin-bottom: 30px;
}
.copyright-page .copyright-line {
  border: none;
  border-top: 1px solid #ddd;
  margin: 20px 0;
}
.copyright-page .copyright-info {
  font-size: 9pt;
  line-height: 2;
  color: #555;
}
.copyright-page .copyright-notice {
  font-size: 8.5pt;
  color: #888;
  line-height: 1.6;
  margin-top: 20px;
}

/* Back cover */
.back-cover {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 60px 40px;
  page: cover;
}
</style>
</head>
<body>

<!-- Cover -->
<div class="cover-page" style="page: cover;">
  <div class="cover-title">${title || '书籍'}</div>
  ${subtitle ? `<div class="cover-subtitle">${subtitle}</div>` : ''}
  <div class="cover-divider"></div>
  <div class="cover-author">${author || '匿名'}</div>
  ${date ? `<div class="cover-date">${date}</div>` : ''}
</div>

<!-- Copyright -->
<div class="copyright-page" style="page: copyright;">
  <div class="copyright-title">${title || '书籍'}</div>
  <hr class="copyright-line">
  <div class="copyright-info">
    <strong>作者：</strong>${author || '匿名'}<br>
    ${publisher ? `<strong>出版：</strong>${publisher}<br>` : ''}
    ${version ? `<strong>版本：</strong>${version}<br>` : ''}
    ${date ? `<strong>日期：</strong>${date}<br>` : ''}
    ${isbn ? `<strong>ISBN：</strong>${isbn}<br>` : ''}
    ${description ? `<strong>简介：</strong>${description}<br>` : ''}
  </div>
  <div class="copyright-notice">
    <hr class="copyright-line">
    版权所有 &copy; ${year} ${author || '匿名'}。保留所有权利。<br>
    未经书面许可，不得以任何形式复制或传播本书内容。
  </div>
</div>

${tocEnabled && tocHtml ? `<!-- TOC -->\n<div class="book-body">${tocHtml}</div>` : ''}

<!-- Book Content -->
<div class="book-body">
${bodyContent}
</div>

<!-- Back Cover -->
<div class="back-cover" style="page: cover;">
  <div class="cover-title" style="font-size: 18pt; opacity: 0.4;">${title || '书籍'}</div>
  <div class="cover-divider"></div>
  <div class="cover-author">${author || '匿名'}</div>
  ${description ? `<div style="margin-top: 30px; font-size: 10pt; color: #888; text-align: center; max-width: 400px; line-height: 1.8;">${description}</div>` : ''}
</div>

</body>
</html>`;
}

// =====================================================
// PDF 生成
// =====================================================

// 自动检测 Playwright Chromium 路径
function findChromiumPath() {
  const playwrightCache = process.env.HOME + '/Library/Caches/ms-playwright';
  if (!existsSync(playwrightCache)) return null;

  const entries = readdirSync(playwrightCache).filter(e => e.startsWith('chromium-') && !e.includes('headless'));
  if (entries.length === 0) return null;

  entries.sort((a, b) => {
    const na = parseInt(a.split('-')[1]) || 0;
    const nb = parseInt(b.split('-')[1]) || 0;
    return nb - na;
  });

  const latest = entries[0];
  const armPath = join(playwrightCache, latest, 'chrome-mac-arm64', 'Google Chrome for Testing.app', 'Contents', 'MacOS', 'Google Chrome for Testing');
  const intelPath = join(playwrightCache, latest, 'chrome-mac', 'Google Chrome for Testing.app', 'Contents', 'MacOS', 'Google Chrome for Testing');

  if (existsSync(armPath)) return armPath;
  if (existsSync(intelPath)) return intelPath;
  return null;
}

async function generatePDF(htmlContent, outputPath, verbose) {
  if (verbose) console.log('启动浏览器...');

  const execPath = findChromiumPath();
  const launchOpts = {
    headless: true,
    args: ['--no-sandbox'],
  };
  if (execPath) {
    launchOpts.executablePath = execPath;
    if (verbose) console.log('Chromium 路径:', execPath);
  }

  const browser = await chromium.launch(launchOpts);
  const page = await browser.newPage();

  // 设置页面内容
  await page.setContent(htmlContent, {
    waitUntil: 'networkidle',
    timeout: 60000,
  });

  // 等待字体加载
  await page.evaluate(() => document.fonts.ready);
  await new Promise((r) => setTimeout(r, 1000));

  if (verbose) console.log('生成 PDF...');

  // 导出 PDF
  await page.pdf({
    path: outputPath,
    format: 'A4',
    printBackground: true,
    margin: {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0,
    },
    displayHeaderFooter: false,
    preferCSSPageSize: true,
  });

  await browser.close();

  if (verbose) console.log(`PDF 已生成: ${outputPath}`);
}

// =====================================================
// 主流程
// =====================================================

async function main() {
  const opts = parseArgs(process.argv);

  const inputPath = resolve(opts.input);
  if (!existsSync(inputPath)) {
    console.error(`错误: 文件不存在: ${inputPath}`);
    process.exit(1);
  }

  // 读取输入文件
  const rawContent = readFileSync(inputPath, 'utf-8');
  let frontMatterData = {};
  let markdownContent = rawContent;

  // 提取 frontmatter
  const fmMatch = rawContent.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (fmMatch) {
    frontMatterData = parseYamlFrontMatter(fmMatch[1]);
    markdownContent = fmMatch[2];
  }

  if (opts.verbose) {
    console.log('元数据:', frontMatterData);
  }

  // 创建 Markdown 解析器
  const md = createMarkdownParser();

  // 解析 Markdown
  let bodyHtml = md.render(markdownContent);
  bodyHtml = wrapChapterTitles(bodyHtml);

  // 生成目录
  const tocHtml = opts.toc ? generateTOCFromMarkdown(md, bodyHtml) : '';

  // 读取主题 CSS
  let themeCSS = '';
  const themePath = join(STYLES_DIR, 'themes', `${opts.theme}.css`);
  if (existsSync(themePath)) {
    themeCSS = readFileSync(themePath, 'utf-8');
    // 提取 :root 变量部分注入到全局
    const rootMatch = themeCSS.match(/:root\s*\{([\s\S]*?)\}/);
    if (rootMatch) {
      // 变量已经在 buildFullHTML 的 :root 中定义，这里用主题的覆盖值
    }
    // 提取 cover-page, cover-title 等样式
    const styleRegex = /(\.cover-page|\.cover-title|\.cover-subtitle|\.cover-divider|\.cover-author|\.cover-date|\.book-body|@page)[\s\S]*?\{[\s\S]*?\}/gi;
    const themeStyles = themeCSS.match(styleRegex);
    if (themeStyles) {
      themeCSS = themeStyles.join('\n');
    } else {
      themeCSS = '';
    }
  }

  // 组装完整 HTML
  const fullHtml = buildFullHTML({
    bodyContent: bodyHtml,
    metadata: frontMatterData,
    themeName: opts.theme,
    tocEnabled: opts.toc,
    tocHtml: tocHtml,
    cssPaths: { theme: themeCSS },
  });

  // 确定输出路径
  let outputPath;
  if (opts.output) {
    outputPath = resolve(opts.output);
  } else {
    const baseName = basename(inputPath, extname(inputPath));
    const dirName = dirname(inputPath);
    outputPath = join(dirName, `${baseName}.pdf`);
  }

  // 确保输出目录存在
  const outputDir = dirname(outputPath);
  if (!existsSync(outputDir)) {
    mkdirSync(outputDir, { recursive: true });
  }

  // 生成 PDF
  await generatePDF(fullHtml, outputPath, opts.verbose);

  console.log(`✓ PDF 已生成: ${outputPath}`);
}

main().catch((err) => {
  console.error('转换失败:', err.message);
  process.exit(1);
});
