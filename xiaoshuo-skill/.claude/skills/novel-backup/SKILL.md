---
name: novel-backup
description: 自动版本备份——将本章全部改动提交到 git，保留完整版本历史。触发词：自动备份、版本备份、git提交、提交本章、存档。
trigger: 自动备份、版本备份、git提交、提交本章、存档、commit
---

# 子技能7 · 自动版本备份

每章存档，通过 git 保留完整版本历史。

## 输入

- 本章全部改动（正文、细纲、设定文档、追踪文档）

## 输出

一次成功的 git commit，message 格式：

```
feat(chapter): 第XXX章-标题
```

（非章节类提交见下方注意事项）

## 执行步骤

1. `git status` 确认待提交改动
2. `git add -A`
3. `git commit -m "feat(chapter): 第XXX章-标题"`
4. `git log --oneline -5` 确认提交成功

## 注意事项

- 提交前确认正文已定稿、追踪文档已更新。
- 其他场景 message：初始化 `feat(setting): <描述>`、审查修正 `fix(chapter): 第XXX章 审查修正`、成书/脚本 `chore: <描述>`。
- 版本历史查看与回滚命令见 `05-版本备份/说明.md`。
- 详细规范见 `04-技能配置/子技能7-自动版本备份.md`。
