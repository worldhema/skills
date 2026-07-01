---
name: word-cover-md
description: 博客文章 Markdown 文件标题格式化与归类工具 — 清理文件名中的网址/评论数/标点，从文件内容提取日期和分类补全标题，按「时间-内容-分类」格式移动到对应子目录，转换日期格式
argument-hint: ["[clean-names|append-category|prepend-date|move-articles|format-all|convert-date|full-pipeline|split] <path>"]
---

# /word-cover-md

将博客文章 Markdown 文件按「YYYY-MM-DD-标题-分类」格式规范化并归类到对应子目录。

## 使用方式

```
/word-cover-md <子命令> [路径]
```

### 子命令

| 子命令 | 说明 |
|--------|------|
| `clean-names <目录>` | 清理所有 md 文件名：去除网址（`[标题](url)` → `标题`）、去除"有X条评论"、去除中英文标点 `？，！（）?,!()` |
| `append-category <目录>` | 对 `未分类/` 中的文件，读取内容 `Categories[分类名]` 字段，追加到文件名尾部 |
| `prepend-date <目录>` | 对 `未分类/` 中的文件，读取内容 `Posted on[MM/DD/YYYY]` 字段，转为 MM-DD-YYYY 加到文件名开头 |
| `move-articles <目录>` | 将 `未分类/` 中符合「时间-内容-分类」格式的文件移动到对应的分类子目录 |
| `format-all <目录>` | 扫描所有子目录，对不符合格式但文件内有 `Posted on` + `Categories` 字段的文件进行格式化并移动到正确目录 |
| `convert-date <目录>` | 将文件名中的日期从 MM-DD-YYYY 转换为 YYYY-MM-DD |
| `full-pipeline <目录>` | 按顺序执行以上全部 6 个步骤 |
| `split <全量文档.md>` | 按 `###` 拆分全量 Markdown 文档为独立文件，按 H1/H2 目录结构归档 |

### 目录结构约定

处理后的文件遵循 `YYYY-MM-DD-文章标题-分类目录.md` 格式，并按分类放入以下子目录：

```
第一部分：修身/
├── 第一章：修行笔记/
├── 第三章：常识学派/
├── 第四章：认识自己/

第二部分：商业/
├── 第一章：商业世界/
├── 第二章：互联网络/
├── 第三章：工作杂记/
├── 第四章：游戏设计/
├── 第五章：网络社区/

第三部分：生活/
├── 第一章：点滴生活/
├── 第二章：理论研究/
├── 第三章：行走足迹/
├── 第四章：读书笔记/

第四部分：自我/
├── 第一章：关于博客/
├── 第二章：关于自己/
├── 第三章：单独篇章/
├── 第四章：奇思妙想/

未分类/         ← 不匹配格式或缺少元数据的文件
```

### 元数据格式

文件内容中的 WordPress 元数据：

```
Author[作者名](url)Posted on[MM/DD/YYYY](url)Categories[分类名](url)[...]
```

- `Posted on[MM/DD/YYYY]` — 发布日期，用于生成日期前缀
- `Categories[分类名]` — 文章分类，用于生成分类后缀和确定目标目录

## 工作原理

1. **clean-names**: 遍历目录下所有 md 文件，清理文件名中的 URL 链接、评论数和标点符号
2. **append-category**: 对 `未分类/` 中无分类后缀的文件，从文件内容提取 Categories 字段追加到文件名
3. **prepend-date**: 对 `未分类/` 中无日期前缀的文件，从文件内容提取 Posted on 字段添加到文件名开头
4. **move-articles**: 解析 `未分类/` 中符合 `XX-XX-XXXX-标题-分类` 格式的文件，按分类映射移动到对应子目录
5. **format-all**: 扫描所有已分类目录，对仍不符合格式但内容中有元数据的文件进行格式化并纠正目录
6. **convert-date**: 将文件名中的 `MM-DD-YYYY` 转换为 `YYYY-MM-DD`（完整的 ISO 格式）

## 脚本位置

`~/.claude/skills/word-cover-md/scripts/word_cover_md.py`
