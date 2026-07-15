# 更新日志 · hekouwang-yandu-deck-skill

本文件记录本 Skill 的所有版本变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/)，
版本号遵循 [语义化版本 SemVer](https://semver.org/lang/zh-CN/)：`MAJOR.MINOR.PATCH`。

**变更分类**
- `功能` 新增能力 · `变更` 默认/行为调整 · `优化` 既有能力打磨 · `修复` 缺陷修正 · `移除` 删除

---

## [1.2.0]

### 修复
- **捆绑副本追平真身（本次最大的洞）**：skill 里的 `publish.py`（511 行）已落后项目真身（735 行）——**SKILL.md 白纸黑字写着「publish.py 已支持 Mozilla 字体打包」，而副本里 "mozilla" 出现 0 次**；`home.html` 也只有真身的一半（314/657）。已全量同步，并补上从未随 skill 分发的留言板子系统。承诺现在兑现得了。
- **主色口径追平线上**：description 与 §1.4 还写着「暖黑/米白两套主色」，实际线上已是四套并存。**推测缺件正是漂移的成因**——占大头的 V6 焰彩黑没有模板（黑版是 flip 出来的），新 EP 无黑版可拷只能退回老模板，Harness（暖黑）/ 出行SaaS（米白）就是这么来的。
- **陈旧引用**：兄弟 skill 名补 `-skill` 后缀（真实目录是 `hekouwang-content-factory-skill`，旧名照着找会扑空）；`ROOT` 注释里的旧项目名 `Pi.dev/`；`references/系统说明.md` 里的「后续会升级成 Skill」（早就是了）。
- **§2 首页描述**：主色暖黑 → **米白**（2026-07-14 已改），系列卡「两个」→ **五个**，并点明系列卡是**静态手写**、不由 MANIFEST 生成（`write_index()` 是遗留死函数），加系列须三处一起动。

### 功能
- **留言板随 skill 分发**（`references/留言板-D1.md` + `assets/functions/api/comments.js` + `wrangler.toml` + `schema.sql`）：CF Pages Functions + D1，按页隔离，留言存自己的 CF 账号、无第三方。含建库三步、已有防护（限频/蜜罐/XSS/路径注入）、部署三坑（配置式部署不带 dist 参、验证跟随 308、curl 加 `--noproxy`）。
- **换肤专题**（`references/换肤-token-flip.md`）：白↔黑 token-flip 映射表 + 三条验收 + 六个坑。含「**原地覆盖脚本先读后写**」——`open(dst,'w')` 会先把文件截断成空，曾把 9 期全写空。

### 变更
- **§1.4 主色规矩改为「米白是全站默认，V6 焰彩白是国标专属例外」**；暖黑 / V6焰彩黑降为**存量历史态、不再新做**（存量按计划 flip 回米白）。`deck-engine-暖黑.html` 仅为维护存量保留，标注「新 EP 别拷」。故**不再补 V6焰彩黑模板**——补了等于鼓励继续新做。

### 优化
- **副本去账号化**（skill 是公开分发的）：`CF_BEACON_TOKEN` 置空（留空则不注入 beacon，降级干净）、`wrangler.toml` 的 `database_id` 改占位符。否则别人用这个 skill 建的站，流量统计报到作者面板、留言写进作者的库。
- **删死代码**：`FONT_ABS_PREFIX` 指向一个不存在的目录（少 `-skill` 后缀），真正干活的是 `FONT_ABS_RE`。已删常量、采用 skill 版更通用的正则（同时认 `{{SKILL_DIR}}` 占位符与任意绝对路径，覆盖 Anthropic + Mozilla）。
- **§0 加防漂移提示**：点明「项目里的是真身、skill 里的是副本，改完记得同步回来」，并记下这次漂移作为前车之鉴。

## [1.1.0]

### 功能
- **放映 / 提词器模块**（`assets/presenter/presenter-module.html`，§1.6）：按 `S` 开「讲者视图」独立窗口——计时器 + 当前镜逐字稿 + 下一镜预览。主屏与讲者窗靠 **BroadcastChannel 双向同步**，**主屏保持干净可投影/录屏**；弹窗被拦（或无 BroadcastChannel）自动回退页内浮层。
- **真·双屏 + 反向遥控**：第二显示器另开 deck 窗口加 `?speaker=1` 即变讲者窗（免弹窗，`window.name`/`?speaker` 识别，绕开引擎深链冲 hash）；讲者窗按 `←/→` 遥控主屏翻镜、`P/R` 控计时（向主屏引擎派发方向键事件，不改引擎）。键位 `S/P/R/Esc`。
- 逐字稿写进每张 `.slide` 的 `<div class="notes">`（观众/录屏永不可见），**同时即该镜的配音/口播脚本**，可照念或喂 TTS——「演示稿 + 提词器 + 口播稿」三合一。
- 已注入两套引擎模板（暖黑/米白）与 `examples/demo.html`，拷模板即带，无需改引擎；靠 `.active` class（MutationObserver）与引擎解耦。无头截图验证浮层渲染通过。

## [1.0.1]

### 变更
- **目录结构对齐官方 `anthropics/skills` 约定**：原先所有可移植副本都堆在 `reference/`（单数、且混入可执行脚本）。
  现按官方分目录——`scripts/publish.py`、`assets/templates/{deck-engine-暖黑,deck-engine-米白,home}.html`、
  `references/系统说明.md`、`examples/demo.html`。SKILL.md / README(中英) 的指针与结构树同步更新。
  注：`scripts/publish.py` 与 `assets/templates/home.html` 落地时仍须拷进同一个 `演读DECK/`（publish.py 用 `SELF/home.html` 找首页源），文档已注明。

## [1.0.0]

首个有记录的版本（此前以 git 历史维护，无 CHANGELOG）。

### 修复
- **字体路径可移植化**：① `reference/publish.py` 的 `localize()` 由写死的绝对前缀
  （硬编码家目录 + `assets/fonts/`）改为**正则 `FONT_ABS_RE`**，同时认「任意绝对路径」与未替换的
  `{{SKILL_DIR}}` 占位符，统一收成站内 `/fonts/`；② 引擎模板 `deck-engine-{暖黑,米白}.html` 的
  `@font-face` 硬编码字体路径改为占位符 `{{SKILL_DIR}}/assets/fonts/`，拷模板做 EP 时替换。
  不再绑定某台机器/用户名；同时修了 content-factory 改用 `{{SKILL_DIR}}` 占位后、源 HTML 字体前缀随机器变化会替换不中导致字体失效的隐患。

### 优化
- **SKILL.md 声明 `allowed-tools`**：收敛到本 skill 真正需要的工具集，减小越权面。

### 既有能力（首版基线）
- **演示版引擎**：零依赖（纯 CSS + 原生 JS）一屏一镜 keynote，暖黑/米白两套主色；导航（方向键/空格/点击/触屏/圆点/全屏）、自动播放、进度条、深链、`prefers-reduced-motion` 自适应。模板 `reference/deck-engine-{暖黑,米白}.html`。
- **进场动画钩子**：`.an/.bar/.tok/.draw/.grow/[data-count]` + 巨幅幽灵章节号。
- **字体自托管（零 CDN）**：`publish.py` 删外链、注入本地 `@font-face`、`pyftsubset` 子集化思源黑 4 字重 + 宋，preload 防 FOUT，`/fonts/*` 强缓存。
- **发布**：构建 `dist/` → `wrangler pages deploy` 到 Cloudflare Pages（hekouwang.pages.dev）；`MANIFEST`/`SERIES_META` 加期加系列。
- **踩坑沉淀**：dist 每构建清空、本地预览须起 http、CF 子域占用 + 本机 DNS 劫持、EdgeOne 死路、venv 移动失效、代理截断 >4MB 下载。
- 强依赖内容产线 `hekouwang-content-factory`（付费 skill，提供源文章/视觉规范/字体）；引擎可零依赖单独使用。
