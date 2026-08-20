# Claude Code Skills

本仓库存放我创建并在用的 [Claude Code](https://claude.com/claude-code) Skill，覆盖书籍制作、文档处理、内容整理与创作等工作流。

## 安装方式

把对应 skill 目录复制到 `~/.claude/skills/` 下即可使用：

```bash
cp -r <skill目录> ~/.claude/skills/
```

带 Python/Node 依赖的 skill，首次使用前按该目录内说明安装依赖；纯提示词类 skill 开箱即用。

## Skills 一览

### 书籍制作

| Skill | 功能 | 依赖 |
|-------|------|------|
| `md2book` | 将 Markdown 文件转换为带封面的 PDF 电子书，内置 3 套主题样式 | Node.js（markdown-it） |
| `md-to-epub-book` | 将目录中多篇 Markdown 文章合并转换为带目录的 EPUB 电子书，针对中文博客文章优化 | pandoc、python3 |
| `html-cover-epub` | 将 WordPress 导出的 XML 文章转换为 EPUB3 电子书 | python3 |

### 文档处理

| Skill | 功能 | 依赖 |
|-------|------|------|
| `md-to-html` | 将 Markdown 转换为带左侧目录的单文件 HTML 阅读页；提供修订前版本时自动做 diff 高亮，生成逐章审阅稿 | python3 |

### 内容整理

| Skill | 功能 | 依赖 |
|-------|------|------|
| `word-cover-md` | 博客文章 Markdown 标题格式化与归类：清理文件名、提取日期与分类、移动到对应子目录 | python3 |

### 内容创作

| Skill | 功能 | 依赖 |
|-------|------|------|
| `xiaoshuo-skill` | 本地小说创作框架：5 阶段 + 10 技能 + 单章 7 步自动化循环，把设定、人物边界、伏笔变成强制规则；内置戏剧冲突、英雄之旅（千面英雄）、写作手法、人物弧光方法论与灵感引擎，用流程锁住 AI 避免长篇崩盘 | 无需额外依赖 |

## 说明

- 每个 skill 的详细用法见其目录内的 `SKILL.md`。
- 本仓库以备份为主要目的，随使用持续更新。
