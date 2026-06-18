# hekouwang-yandu-deck · 演读 DECK

会勇禾口王的AI笔记 ·「演读 DECK」沉浸式演示产线与发布 Skill。

把一篇文章/选题做成**一屏一镜、可翻页、能自动播放**的 keynote 演示版网页（**暖黑** / **米白** 两套主色），自托管字体（思源黑/宋子集化 + Anthropic 打包、零 CDN、preload 治 FOUT），并一键发布到 Cloudflare Pages。

线上样例：**https://hekouwang.pages.dev**

## 这是什么

这是一个 [Claude Code](https://claude.com/claude-code) **Skill**。`SKILL.md` 是给 Agent 读的方法说明；`reference/` 是可直接拷用的模板与脚本。

```
SKILL.md                       # 方法 + 触发词 + 防踩坑（Agent 入口）
reference/
├── deck-engine-暖黑.html       # 演示版引擎模板（数据/财经/科普暗调）
├── deck-engine-米白.html       # 演示版引擎模板（人文/方法论亮调）
├── publish.py                 # 构建 dist/ → 部署 CF Pages（零三方依赖）
├── home.html                  # 首页模板
└── 系统说明.md
```

## 安装

把本仓库放进 `~/.claude/skills/hekouwang-yandu-deck/`：

```bash
git clone git@github.com:huiyonghkw/hekouwang-yandu-deck.git ~/.claude/skills/hekouwang-yandu-deck
```

之后在 Claude Code 里说「把这篇做成演示版 / 加一期演读 / 发 hekouwang」等即会自动加载。

## 核心能力

- **演示版引擎**（零依赖 CSS+JS）：全屏一屏一镜、←/→/空格/点击/触屏翻页、自动播放、进场动画（卡片错峰 / 柱子生长 / SVG 描线 / 数字滚动 / 幽灵章节号）、`fit()` 自适应、`#N` 深链、`prefers-reduced-motion` 友好。
- **两套主色**：暖黑（数据控制台）/ 米白（编辑人文），引擎 JS 主题无关。
- **字体自托管**：思源黑 4 字重 + 宋按用字子集化（各 ~180KB），Anthropic Sans/Mono 打包，全站零外链；preload + 强缓存消除首屏字重跳变。
- **一键发布**：`python3 publish.py`，MANIFEST 加一行即加一期，CF Pages 干净 URL。

> 配套图文/视频产线见 `hekouwang-content-factory`。
