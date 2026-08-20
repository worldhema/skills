# 字体配置参考

## macOS 自带中文字体

### 正文（宋体风格）

| 字体名 | 路径 | 权重 | 用途 |
|--------|------|------|------|
| Source Han Serif CN Regular | `~/Library/Fonts/SourceHanSerifCN-Regular-1.otf` | 400 | 正文默认 |
| Source Han Serif CN Medium | `~/Library/Fonts/` | 500 | 正文加粗 |
| Source Han Serif CN Bold | `~/Library/Fonts/SourceHanSerifCN-Bold-2.otf` | 700 | 强调文字 |
| Songti SC Regular | `/System/Library/Fonts/Supplemental/Songti.ttc` | 400 | 备用正文 |
| STSong | 系统内置 | 400 | 最终降级 |

### 标题（黑体风格）

| 字体名 | 路径 | 权重 | 用途 |
|--------|------|------|------|
| Heiti SC Medium | `/System/Library/Fonts/STHeiti Medium.ttc` | 500 | 标题默认 |
| Heiti SC Light | `/System/Library/Fonts/STHeiti Light.ttc` | 300 | 轻量标题 |
| PingFang SC | 系统内置 | 400/500/600 | 苹方（如果有） |

### 代码（等宽字体）

| 字体名 | 路径 | 用途 |
|--------|------|------|
| SF Mono | 系统内置 | 代码块首选 |
| Menlo | `/System/Library/Fonts/Supplemental/` | 备用等宽 |
| Monaco | 系统内置 | 最终降级 |

## 字体栈定义

```css
/* 正文 */
font-family: "Source Han Serif CN", "STSong", "Songti SC", "SimSun", serif;

/* 标题 */
font-family: "PingFang SC", "Heiti SC", "Microsoft YaHei", sans-serif;

/* 代码 */
font-family: "SF Mono", "Menlo", "Monaco", "Courier New", monospace;
```

## 安装额外字体（可选）

### 思源宋体完整版
```bash
# 从 Google Fonts 或 Adobe 下载
# 安装到 ~/Library/Fonts/
# 然后运行: fc-cache -fv 刷新字体缓存
```

### 苹方字体
macOS 10.11+ 自带 PingFang SC，无需额外安装。

## 验证字体可用性

```bash
# 列出所有中文字体
fc-list :lang=zh

# 检查特定字体
fc-match "Source Han Serif CN"
fc-match "Songti SC"
fc-match "Heiti SC"
```
