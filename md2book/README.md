[English](#english) | [简体中文](#简体中文)

---

<a id="english"></a>
# 📚 md2book

A professional tool to convert Markdown files into beautifully typeset PDF e-books. It supports smart pagination, perfect Chinese rendering, elegant cover designs, and multiple visual themes.

## ✨ Features

- **Professional Typesetting**: Smart pagination, automatic table of contents, and beautiful cover generation.
- **Multiple Themes**:
  - `minimal`: Minimalist tech style (lots of white space, monochrome, suitable for tech books).
  - `academic`: Classic academic style (serif fonts, warm paper background, professional).
  - `playful`: Lively illustration style (colorful, gradient decorations).
- **Rich Markdown Support**: Standard GFM, code syntax highlighting (highlight.js), custom callouts (`[!INFO]`, `[!TIP]`, `[!WARNING]`, `[!DANGER]`).
- **Perfect Chinese Typography**: Carefully tuned fonts and line spacing for Chinese characters.

## 🚀 Quick Start

### Prerequisites

Ensure you have Node.js installed.

### Installation

```bash
cd scripts
npm install
npx playwright install chromium
```

### Usage

```bash
node scripts/md2book.js <input.md>
node scripts/md2book.js <input.md> --theme <minimal|academic|playful>
node scripts/md2book.js <input.md> --output <path.pdf>
node scripts/md2book.js <input.md> --verbose
```

## 📝 Frontmatter Configuration

Your Markdown file should include YAML frontmatter:

```yaml
---
title: Book Title
subtitle: Optional Subtitle
author: Author Name
publisher: Optional Publisher
version: v1.0
date: 2026-04-10
isbn: 978-0-000000-00-0
description: A short description
---
```

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<a id="简体中文"></a>
# 📚 md2book

将 Markdown 格式的技术书籍/教程转换为专业排版的 PDF 电子书。支持智能分页、中文完美渲染、精美装帧设计和多种视觉主题。

## ✨ 特性

- **专业排版**：智能分页、自动生成目录、精美封面渲染。
- **多款视觉主题**：
  - `minimal`（极简科技风）：纯白背景，黑白灰色调，适合技术文档、编程教程。
  - `academic`（经典学术风）：暖色纸张质感背景，深红色强调色，适合理论著作、学术专著。
  - `playful`（活泼插画风）：渐变彩色封面，圆角卡片设计，适合入门教程、科普读物。
- **丰富的 Markdown 支持**：标准 GFM、代码语法高亮 (highlight.js)、自定义提示框 Callout (`[!INFO]`, `[!TIP]`, `[!WARNING]`, `[!DANGER]`)。
- **完美中文渲染**：精心调校的中文字体排版与行距。

## 🚀 快速开始

### 环境要求

请确保已安装 Node.js。

### 安装依赖

```bash
cd scripts
npm install
npx playwright install chromium
```

### 使用方法

```bash
node scripts/md2book.js <input.md>
node scripts/md2book.js <input.md> --theme <minimal|academic|playful>
node scripts/md2book.js <input.md> --output <path.pdf>
node scripts/md2book.js <input.md> --verbose
```

## 📝 Frontmatter 配置

您的 Markdown 文件开头应包含 YAML frontmatter 格式的元数据：

```yaml
---
title: 书名
subtitle: 副标题（可选）
author: 作者名
publisher: 出版社（可选）
version: v1.0
date: 2026-04-10
isbn: 978-0-000000-00-0（可选）
description: 一句话简介
---
```

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。
