#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演读DECK/publish.py — 会勇禾口王的AI笔记 · 沉浸式演示主题站发布脚本

做什么:
  1. 把 MANIFEST 里的「演示版」HTML 拷进 dist/,用干净 slug 命名(suanli/ep01 …)
  2. 把内嵌的本地 Anthropic 字体(绝对路径)改成站内 /fonts/,并把 woff2 一起打包进去
     —— 这样公网也能用上 Anthropic Sans/Mono(原 suanli 文章页公网会丢这两个字体)
  3. 把 Google Fonts 换成 loli.net 国内镜像(国内首屏不卡字体)
  4. 生成 dist/index.html 沉浸式主题导航页(暖黑,COMPUTE LEDGER 调性)
  5. --deploy(默认) 用 Wrangler 部署到 Cloudflare Pages 项目 keynote → keynote.pages.dev

用法:
  python3 演读DECK/publish.py              # 构建 + 部署到 Cloudflare Pages(keynote)
  python3 演读DECK/publish.py --build-only # 只生成 dist/(本地预览,不部署)

加一期:在 MANIFEST 加一行即可,重跑脚本。零依赖,只用标准库。

定位:keynote.pages.dev = 沉浸式阅览主题站。一个主题(系列)一组演示稿,后续可扩展更多主题。
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
SELF = Path(__file__).resolve().parent                # 演读DECK/（发布系统自身目录，自包含）
ROOT = SELF.parent                                    # 项目根（MANIFEST 里演示版源路径的基准）
OUT = SELF / "dist"                                   # 构建产物 = 部署到 CF Pages 的目录
CF_PROJECT = "hekouwang"              # *.pages.dev 前缀 → hekouwang.pages.dev
SITE_TITLE = "演读 DECK"
SITE_TAGLINE = "把复杂的 AI，读成一场演示。一屏一镜、可翻页、能自动播放的沉浸式阅读。"
BRAND = "会勇禾口王的AI笔记"
HANDLE = "@huiyonghkw"

# Anthropic 字体已收进本目录 fonts/src（自包含，不再依赖外部 skill 路径）
FONT_SRC = SELF / "fonts" / "src"
FONT_FILES = ["anthropicSans.woff2", "anthropicMono.woff2"]
# V6 焰彩白引擎用的 Mozilla 可变字体（拉丁，小体积、无需子集化，整包打进 dist/fonts/）
MOZILLA_FILES = ["MozillaHeadline-Variable.woff2", "MozillaText-Variable.woff2"]
# 演示版源 HTML(content-factory 出品)里内嵌的本地字体路径；localize 时统一替换成站内 /fonts/。
# 正则同时认两种写法，不写死某台机器/用户名——他机/换目录/不同 skill 路径都认：
#   ① 任意绝对路径 + /assets/fonts/（模型已把 {{SKILL_DIR}} 替换成真实绝对路径的常态）
#   ② 未替换的 {{SKILL_DIR}}/assets/fonts/ 占位符（模型拷引擎模板时漏替换的兜底）
# 覆盖 Anthropic + Mozilla 两族字体。
FONT_ABS_RE = re.compile(r"(?:\{\{SKILL_DIR\}\}|/[^\s'\"()]*?)/assets/fonts/")

# 首页源（持久化，改首页改这个；dist/ 每次构建都会被清空）
HOMEPAGE_SRC = SELF / "home.html"

# 思源黑/宋 自托管：字重静态源 + 子集化缓存
CJK_SRC = SELF / "fonts" / "src"                      # 字体源（思源 4 字重 + 宋；约 8MB，不部署）
CJK_CACHE = SELF / "fonts" / "cache"                  # 子集化产物缓存（无字体源/无 venv 时回退用）
CJK_JOBS = [                                            # (字体源, 输出名)  逐字重子集化
    ("NotoSansSC-400.woff2", "NotoSansSC-400.woff2"),
    ("NotoSansSC-500.woff2", "NotoSansSC-500.woff2"),
    ("NotoSansSC-700.woff2", "NotoSansSC-700.woff2"),
    ("NotoSansSC-900.woff2", "NotoSansSC-900.woff2"),   # 800 映射到 900（@fontsource 无 800）
    ("NotoSerifSC-700.woff2", "NotoSerifSC.woff2"),     # 金句衬线，单字重覆盖全段
]
# 注入到每个页面的本地思源 @font-face（替换掉 Google/loli 外链）
FONT_FACE_CJK = (
    "<style>"
    "@font-face{font-family:'Noto Sans SC';src:url('/fonts/NotoSansSC-400.woff2') format('woff2');font-weight:400;font-style:normal;font-display:swap}"
    "@font-face{font-family:'Noto Sans SC';src:url('/fonts/NotoSansSC-500.woff2') format('woff2');font-weight:500;font-style:normal;font-display:swap}"
    "@font-face{font-family:'Noto Sans SC';src:url('/fonts/NotoSansSC-700.woff2') format('woff2');font-weight:700;font-style:normal;font-display:swap}"
    "@font-face{font-family:'Noto Sans SC';src:url('/fonts/NotoSansSC-900.woff2') format('woff2');font-weight:800 900;font-style:normal;font-display:swap}"
    "@font-face{font-family:'Noto Serif SC';src:url('/fonts/NotoSerifSC.woff2') format('woff2');font-weight:400 900;font-style:normal;font-display:swap}"
    "</style>"
)
# 关键字体预加载（首屏最显眼的几个字重 + Anthropic），插到每页 <head> 最前，
# 让浏览器一解析就高优先级并行下载，几乎消除「先系统字、再换思源」的字重跳变(FOUT)。
PRELOAD_LINKS = (
    '<link rel="preload" href="/fonts/NotoSansSC-900.woff2" as="font" type="font/woff2" crossorigin>'
    '<link rel="preload" href="/fonts/NotoSansSC-400.woff2" as="font" type="font/woff2" crossorigin>'
    '<link rel="preload" href="/fonts/anthropicSans.woff2" as="font" type="font/woff2" crossorigin>'
    '<link rel="preload" href="/fonts/anthropicMono.woff2" as="font" type="font/woff2" crossorigin>'
)
# V6 焰彩白页面的预加载（Mozilla 可变字体 + 思源，无 Anthropic）
PRELOAD_LINKS_V6 = (
    '<link rel="preload" href="/fonts/NotoSansSC-900.woff2" as="font" type="font/woff2" crossorigin>'
    '<link rel="preload" href="/fonts/NotoSansSC-400.woff2" as="font" type="font/woff2" crossorigin>'
    '<link rel="preload" href="/fonts/MozillaHeadline-Variable.woff2" as="font" type="font/woff2" crossorigin>'
    '<link rel="preload" href="/fonts/MozillaText-Variable.woff2" as="font" type="font/woff2" crossorigin>'
)
# Cloudflare Pages 静态头：字体强缓存（子集名稳定，改字体时极少；一周缓存够稳又不至于太僵）
HEADERS_FILE = "/fonts/*\n  Cache-Control: public, max-age=604800, stale-while-revalidate=86400\n"

# 子集化保险字符：基础 ASCII + 常用中文标点
CJK_BASE_CHARS = (
    "".join(chr(c) for c in range(0x20, 0x7f))
    + "，。、；：？！“”‘’「」『』（）《》〈〉【】—…·～％‰×÷°±≈≠≤≥→←↑↓★☆●○■□▸▪◎❤⚗✎⚡🎁"
)

FONT_MIRRORS = {
    "https://fonts.googleapis.com": "https://fonts.loli.net",
    "https://fonts.gstatic.com": "https://gstatic.loli.net",
    "http://fonts.googleapis.com": "https://fonts.loli.net",
    "http://fonts.gstatic.com": "https://gstatic.loli.net",
}

# 发布清单:(源演示版 相对 ROOT, slug, 系列, EP标签, 分类, 标题, 一句话简介, 屏数)
MANIFEST = [
    (
        "EP-智能体互联国标系列/序篇-全景与三协议/序篇-演示版.html",
        "guobiao/xu", "智能体互联国标", "序篇", "全景 · OVERVIEW",
        "全球第一份「智能体互联」国标，到底定了什么",
        "GB/Z 185 七部分原文读完：它和 MCP／A2A／ANP 什么关系，最不一样的一刀切在身份。",
        17,
    ),
    (
        "EP-智能体互联国标系列/EP01-总体架构/EP01-演示版.html",
        "guobiao/ep01", "智能体互联国标", "EP01", "总体架构 · ARCHITECTURE",
        "智能体要互联，先过哪五道关",
        "185.1 总体架构：五域十接口一条闭环，用一次「订会议室」走通身份→工具全链路。",
        17,
    ),
    (
        "EP-算力账本/EP01-把算力当电卖/EP01-演示版.html",
        "suanli/ep01", "算力账本", "EP01", "入门 · BASICS",
        "算力、Token，到底是什么？",
        "把算力当成“电”、Token 当成“电表度数”，零基础也能跟上的第一课。",
        18,
    ),
    (
        "EP-算力账本/EP02-Token越便宜越紧张/EP02-演示版.html",
        "suanli/ep02", "算力账本", "EP02", "Token 经济学 · TOKEN",
        "AI 越用越便宜，算力为什么反而不够用？",
        "价格越低、总需求越疯——一笔算力供需的反直觉账。",
        24,
    ),
    (
        "EP-算力账本/EP03-算力租赁的回本账/EP03-演示版.html",
        "suanli/ep03", "算力账本", "EP03", "算力租赁经济学 · LEASING",
        "一张几十万的卡，多久能租回本？",
        "算力租赁的回本账，一笔笔拆给你看。",
        19,
    ),
    (
        "EP-算力账本/EP3.5-一度电能吐多少Token/EP3.5-演示版.html",
        "suanli/ep35", "算力账本", "EP3.5", "能耗账 · ENERGY",
        "一度电，能吐多少 Token？",
        "从瓦特到 Token，把 AI 的能耗账算明白。",
        22,
    ),
    (
        "EP-算力账本/EP04-推理比训练更烧钱/EP04-演示版.html",
        "suanli/ep04", "算力账本", "EP04", "推理经济学 · INFERENCE",
        "训练烧一次，推理烧一辈子",
        "AI 进千家万户，烧钱的重心正从训练倒向推理——一笔成本反转的账。",
        20,
    ),
    (
        "EP-偷师AI大佬/EP01-Dario只管一个人/EP01-演示版.html",
        "toushi/ep01", "偷师AI大佬", "EP01", "管理 · DARIO",
        "只管一个人的 CEO",
        "Dario 只有 1 个直接下属——把执行委托出去，把判断收回自己。",
        10,
    ),
    (
        "EP-偷师AI大佬/EP02-Karpathy把代码交给AI/EP02-演示版.html",
        "toushi/ep02", "偷师AI大佬", "EP02", "编程 · KARPATHY",
        "把代码交给 AI 的教父",
        "Karpathy 自宣 99% 不写代码——从亲手做，到编排 + 监督。",
        18,
    ),
    (
        "EP-偷师AI大佬/EP03-Demis研究品味/EP03-演示版.html",
        "toushi/ep03", "偷师AI大佬", "EP03", "品味 · DEMIS",
        "诺奖得主说：真正稀缺的是品味",
        "执行交给 AI 之后，判断和品味怎么练。",
        13,
    ),
    (
        "EP-偷师AI大佬/专题-读懂大佬的AI喊话/演示版.html",
        "toushi/zhuanti-dario", "偷师AI大佬", "专题", "真话 · DARIO",
        "AI 大佬的真话，没被剪辑前是什么样",
        "Dario 完整 70 分钟访谈、51 问答一句不删——让你看清 AI 世界到底在说什么。",
        56,
    ),
    (
        "EP-Harness工程系列/EP05下集-该用MCP还是CLI/演示版.html",
        "harness/ep05x", "Harness 工程", "EP05·下集", "工具 · TOOLS",
        "该用 MCP，还是直接敲命令（CLI）",
        "都说抛弃 MCP 转 CLI，其实吵错了轴：登记层归 MCP、执行层归代码执行，一张两轴图讲清。",
        17,
    ),
    (
        "EP-出行SaaS工程手记/EP01-一份代码变100个小程序/EP01-演示版.html",
        "saas/ep01", "出行SaaS工程手记", "EP01", "多租户 · SAAS",
        "一份代码，怎么变成 100 个商户各自的小程序",
        "微信「代运营」把复杂度的乘法改写成一条平线：授权令牌链 + 9 步代发布流水线 + 边际成本趋零，再让 AI 把它压到一个人扛得住。",
        21,
    ),
]

SERIES_META = {
    "智能体互联国标": {
        "en": "AGENT INTERCONNECTION · GB/Z 185",
        "dek": "全球第一份「智能体互联」国标 GB/Z 185，七部分一集集讲成人话。",
    },
    "算力账本": {
        "en": "COMPUTE LEDGER",
        "dek": "用记账的方式，把 AI 背后的算力与 Token 经济学讲清楚。",
    },
    "偷师AI大佬": {
        "en": "STEAL THE PLAYBOOK",
        "dek": "从 AI 大佬身上，偷一个普通人明天就能用的方法。",
    },
    "Harness 工程": {
        "en": "HARNESS ENGINEERING",
        "dek": "模型会说话之外，让它真会干活的「模型外面那层」——循环、工具、子代理，一集一个部件拆给你看。",
    },
    "出行SaaS工程手记": {
        "en": "RIDE-SAAS · FIELD NOTES",
        "dek": "面向企业出行的多租户 SaaS，怎么用一份代码服务一百个商户——真实项目里的架构、踩坑与 AI 协作，一期一个战场。",
    },
}


# ---------------------------------------------------------------------------
# ── Cloudflare Web Analytics beacon ──────────────────────────────────
# 每页注入（deck 走 build()、首页走 copy_home()，都过 localize()，一处即全站）。
# 意义：爬虫不执行 JS → 这个数字天然把机器人筛掉，是「真人有没有来」的唯一可信口径。
#   （对照：CF「帐户分析/流量概览」统计的是边缘请求数，机器人全算进去，会虚高几十倍。）
# token 是公开的客户端标识（本来就明文出现在页面里），非密钥，入库无风险。
# ⚠️ static.cloudflareinsights.com 国内可能加载失败 → CN 真人会被少计。
#    别把它当唯一真相源；判断国内真人另看留言板 D1 / 公众号后台。
# ⚠️ 落地新项目时把 token 换成你自己的（CF 控制台 → Web Analytics → 添加站点后拿）。
#    留空则不注入 beacon（不想统计、或还没建站时的默认）。
CF_BEACON_TOKEN = ""   # ← 填你自己的 Web Analytics token
CF_BEACON = ("""<!-- Cloudflare Web Analytics --><script type='module' """
             """src='https://static.cloudflareinsights.com/beacon.min.js' """
             f"""data-cf-beacon='{{"token": "{CF_BEACON_TOKEN}"}}'>"""
             """</script><!-- End Cloudflare Web Analytics -->""") if CF_BEACON_TOKEN else ""


def localize(html: str) -> str:
    """① 本地 Anthropic 字体绝对路径 → 站内 /fonts/；② 自托管思源黑/宋：
    删掉 Google Fonts / loli 外链（preconnect + css2），注入本地 @font-face；
    ③ 注入 Cloudflare Web Analytics beacon（真人流量统计）。"""
    html = FONT_ABS_RE.sub("/fonts/", html)   # 通配收编 Anthropic + Mozilla 绝对路径
    # 删除字体 preconnect（googleapis / gstatic / loli 任意）
    html = re.sub(r'\s*<link rel="preconnect"[^>]*(?:googleapis|gstatic|loli)[^>]*>', "", html)
    # 第一处 Noto css2 外链 → 本地 @font-face；其余同类外链删除
    html, n = re.subn(r'<link href="https://[^"]*/css2\?family=Noto[^"]*"[^>]*>',
                      FONT_FACE_CJK, html, count=1)
    if n:
        html = re.sub(r'<link href="https://[^"]*/css2\?family=Noto[^"]*"[^>]*>', "", html)
    # 关键字体预加载（插到 <head> 最前，避免首屏字重跳变）；V6 页面用 Mozilla 预加载
    if "rel=\"preload\"" not in html:
        pl = PRELOAD_LINKS_V6 if "Mozilla" in html else PRELOAD_LINKS
        html = html.replace("<head>", "<head>" + pl, 1)
    # Web Analytics beacon（放 </body> 前，type=module 天然 defer，不挡首屏）
    if "cloudflareinsights" not in html:
        html = (html.replace("</body>", CF_BEACON + "\n</body>", 1)
                if "</body>" in html else html + CF_BEACON)
    return html


# ── 每期 deck 的悬浮留言面板 ──────────────────────────────────────────
# deck 是全屏翻页(body 不滚动),留言板做成右侧把手 + 滑出面板(暗色玻璃,自适应暗/亮 deck)。
# 自包含、类名 hkwc- 前缀防冲突、字体走系统栈。__PAGE_KEY__/__PAGE_TITLE__ 按期替换。
COMMENT_WIDGET = r"""
<style>
.hkwc-tab{position:fixed;right:0;top:50%;transform:translateY(-50%);z-index:9990;
  writing-mode:vertical-rl;text-orientation:upright;letter-spacing:.28em;
  background:rgba(224,138,95,.92);color:#231a14;font:700 13px/1 -apple-system,BlinkMacSystemFont,'PingFang SC','Noto Sans SC',system-ui,sans-serif;
  border:none;border-radius:12px 0 0 12px;padding:15px 9px;cursor:pointer;box-shadow:-3px 0 16px rgba(0,0,0,.28);
  transition:padding .2s,background .2s}
.hkwc-tab:hover{padding-right:13px;background:#e08a5f}
.hkwc-tab .n{writing-mode:horizontal-tb;display:inline-block;margin-top:8px;font-size:11px;opacity:.85}
.hkwc-ov{position:fixed;inset:0;z-index:9998;background:rgba(8,8,10,.55);backdrop-filter:blur(3px);
  opacity:0;visibility:hidden;transition:opacity .28s,visibility .28s}
.hkwc-ov.on{opacity:1;visibility:visible}
.hkwc-panel{position:fixed;top:0;right:0;bottom:0;z-index:9999;width:min(430px,92vw);
  display:flex;flex-direction:column;background:#1a1917;color:#f4f2eb;
  font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Noto Sans SC',system-ui,sans-serif;
  border-left:1px solid rgba(244,242,235,.12);box-shadow:-14px 0 44px rgba(0,0,0,.5);
  transform:translateX(100%);transition:transform .32s cubic-bezier(.22,.61,.36,1)}
.hkwc-ov.on .hkwc-panel{transform:none}
.hkwc-hd{padding:20px 22px 14px;border-bottom:1px solid rgba(244,242,235,.09);flex:0 0 auto}
.hkwc-hd .en{font:700 10px/1 ui-monospace,monospace;letter-spacing:.28em;color:#efb79b;text-transform:uppercase}
.hkwc-hd h3{font-size:20px;font-weight:800;letter-spacing:-.01em;margin:8px 0 3px}
.hkwc-hd .sub{font-size:12px;color:#948e84;line-height:1.5}
.hkwc-x{position:absolute;top:16px;right:16px;width:32px;height:32px;border-radius:50%;border:1px solid rgba(244,242,235,.14);
  background:transparent;color:#aea99f;font-size:17px;cursor:pointer;line-height:1;transition:background .2s}
.hkwc-x:hover{background:rgba(244,242,235,.08);color:#f4f2eb}
.hkwc-list{flex:1 1 auto;overflow-y:auto;padding:16px 22px;display:flex;flex-direction:column;gap:11px;-webkit-overflow-scrolling:touch}
.hkwc-item{background:#221f1d;border:1px solid rgba(244,242,235,.08);border-radius:12px;padding:12px 14px}
.hkwc-item .who{display:flex;align-items:baseline;gap:9px;margin-bottom:5px}
.hkwc-item .name{font-weight:700;font-size:13.5px;color:#f6e1d1}
.hkwc-item .when{font:400 10.5px/1 ui-monospace,monospace;color:#5f5a52;letter-spacing:.03em}
.hkwc-item .text{font-size:14px;line-height:1.6;color:#cdc8bd;white-space:pre-wrap;word-break:break-word}
.hkwc-empty{font:400 12.5px/1.6 ui-monospace,monospace;color:#5f5a52;padding:6px 0}
.hkwc-ft{flex:0 0 auto;padding:14px 22px 20px;border-top:1px solid rgba(244,242,235,.09);background:#161514}
.hkwc-ft input,.hkwc-ft textarea{width:100%;background:#221f1d;border:1px solid rgba(244,242,235,.14);border-radius:9px;
  color:#f4f2eb;font-family:inherit;font-size:14px;padding:9px 11px;margin-bottom:8px}
.hkwc-ft input::placeholder,.hkwc-ft textarea::placeholder{color:#5f5a52}
.hkwc-ft input:focus,.hkwc-ft textarea:focus{outline:none;border-color:#e08a5f}
.hkwc-ft textarea{resize:vertical;min-height:56px;line-height:1.5}
.hkwc-hp{position:absolute;left:-9999px;width:1px;height:1px;opacity:0}
.hkwc-row{display:flex;align-items:center;justify-content:space-between;gap:12px}
.hkwc-msg{font:400 11.5px/1 ui-monospace,monospace;letter-spacing:.02em;min-height:12px}
.hkwc-msg.ok{color:#aec2d4}.hkwc-msg.err{color:#efb79b}
.hkwc-send{font:700 13px/1 ui-monospace,monospace;color:#231a14;background:#e08a5f;border:none;border-radius:999px;
  padding:9px 20px;cursor:pointer;white-space:nowrap;transition:transform .15s,opacity .2s}
.hkwc-send:hover{transform:translateY(-1px)}.hkwc-send:disabled{opacity:.5;cursor:not-allowed;transform:none}
.hkwc-cr{margin-top:12px;font:400 10.5px/1.5 ui-monospace,monospace;color:#5f5a52;letter-spacing:.02em}
.hkwc-cr a{color:#948e84;text-decoration:none;border-bottom:1px solid rgba(148,142,132,.35)}
.hkwc-cr a:hover{color:#efb79b;border-bottom-color:#efb79b}
@media(prefers-reduced-motion:reduce){.hkwc-ov,.hkwc-panel{transition:none}}
</style>
<button class="hkwc-tab" id="hkwcTab" aria-label="打开留言板">留言<span class="n" id="hkwcN"></span></button>
<div class="hkwc-ov" id="hkwcOv" aria-hidden="true">
  <aside class="hkwc-panel" role="dialog" aria-label="本期留言板" aria-modal="true">
    <div class="hkwc-hd">
      <button class="hkwc-x" id="hkwcX" aria-label="关闭">✕</button>
      <span class="en">TALK · 本期留言</span>
      <h3>聊两句</h3>
      <div class="sub">__PAGE_TITLE__</div>
    </div>
    <div class="hkwc-list" id="hkwcList"><div class="hkwc-empty">加载中…</div></div>
    <form class="hkwc-ft" id="hkwcForm" autocomplete="off">
      <input id="hkwcNick" name="nickname" maxlength="24" placeholder="昵称(可留空=匿名读者)">
      <input class="hkwc-hp" type="text" name="website" tabindex="-1" aria-hidden="true">
      <textarea id="hkwcBody" name="content" maxlength="500" rows="2" placeholder="选题建议 / 想深挖哪一段 / 打个招呼…"></textarea>
      <div class="hkwc-row">
        <span class="hkwc-msg" id="hkwcMsg"></span>
        <button class="hkwc-send" id="hkwcSend" type="submit">发送</button>
      </div>
      <div class="hkwc-cr">本站演示引擎开源为 Claude Skill · <a href="https://github.com/huiyonghkw/hekouwang-yandu-deck-skill" target="_blank" rel="noopener">GitHub @huiyonghkw</a></div>
    </form>
  </aside>
</div>
<script>
(function(){
  var PAGE='__PAGE_KEY__';
  var API='/api/comments?page='+encodeURIComponent(PAGE);
  var tab=document.getElementById('hkwcTab'),ov=document.getElementById('hkwcOv'),
      xBtn=document.getElementById('hkwcX'),form=document.getElementById('hkwcForm'),
      nick=document.getElementById('hkwcNick'),body=document.getElementById('hkwcBody'),
      send=document.getElementById('hkwcSend'),msg=document.getElementById('hkwcMsg'),
      listEl=document.getElementById('hkwcList'),nEl=document.getElementById('hkwcN');
  var loaded=false;
  function esc(s){var d=document.createElement('div');d.textContent=s==null?'':String(s);return d.innerHTML;}
  function when(ts){var n=Math.floor(Date.now()/1000),d=n-ts;
    if(d<60)return '刚刚';if(d<3600)return Math.floor(d/60)+' 分钟前';
    if(d<86400)return Math.floor(d/3600)+' 小时前';if(d<2592000)return Math.floor(d/86400)+' 天前';
    var t=new Date(ts*1000);return (t.getMonth()+1)+' 月 '+t.getDate()+' 日';}
  function itemHTML(c){return '<div class="hkwc-item"><div class="who"><span class="name">'+esc(c.nickname)+
    '</span><span class="when">'+when(c.created_at)+'</span></div><div class="text">'+esc(c.content)+'</div></div>';}
  function render(list){
    if(!list||!list.length){listEl.innerHTML='<div class="hkwc-empty">还没有留言,来做第一个 👋</div>';nEl.textContent='';return;}
    listEl.innerHTML=list.map(itemHTML).join('');nEl.textContent=list.length;}
  function load(){fetch(API,{headers:{'accept':'application/json'}}).then(function(r){return r.json();})
    .then(function(d){render(d&&d.comments);}).catch(function(){listEl.innerHTML='<div class="hkwc-empty">加载失败,稍后再试</div>';});}
  function open(){ov.classList.add('on');ov.setAttribute('aria-hidden','false');if(!loaded){loaded=true;load();}setTimeout(function(){body.focus();},320);}
  function close(){ov.classList.remove('on');ov.setAttribute('aria-hidden','true');tab.focus();}
  tab.addEventListener('click',open);
  xBtn.addEventListener('click',close);
  ov.addEventListener('click',function(e){if(e.target===ov)close();});
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&ov.classList.contains('on'))close();});
  form.addEventListener('submit',function(ev){ev.preventDefault();
    var content=body.value.trim();if(!content){msg.textContent='写点什么再发吧';msg.className='hkwc-msg err';return;}
    send.disabled=true;msg.textContent='发送中…';msg.className='hkwc-msg';
    fetch('/api/comments',{method:'POST',headers:{'content-type':'application/json'},
      body:JSON.stringify({page:PAGE,nickname:nick.value,content:content,website:form.website.value})})
    .then(function(r){return r.json().then(function(d){return {ok:r.ok,d:d};});})
    .then(function(res){send.disabled=false;
      if(!res.ok){msg.textContent=(res.d&&res.d.error)||'发送失败';msg.className='hkwc-msg err';return;}
      body.value='';msg.textContent='谢谢你的留言 ✓';msg.className='hkwc-msg ok';
      if(res.d&&res.d.comment){var em=listEl.querySelector('.hkwc-empty');if(em)listEl.innerHTML='';
        listEl.insertAdjacentHTML('afterbegin',itemHTML(res.d.comment));
        nEl.textContent=(parseInt(nEl.textContent)||0)+1;}else{load();}})
    .catch(function(){send.disabled=false;msg.textContent='网络出错,稍后再试';msg.className='hkwc-msg err';});});
  // 预取一次留言数,给把手加角标(不打开也能看到有没有人聊)
  fetch(API,{headers:{'accept':'application/json'}}).then(function(r){return r.json();})
    .then(function(d){if(d&&d.comments&&d.comments.length)nEl.textContent=d.comments.length;}).catch(function(){});
})();
</script>
"""


def inject_comments(html: str, page_key: str, page_title: str) -> str:
    """把悬浮留言面板注入 deck 页(</body> 前)。EP 源不动,只在发布层加。"""
    safe_title = (page_title or "").replace("<", "").replace(">", "").replace('"', "")
    snippet = COMMENT_WIDGET.replace("__PAGE_KEY__", page_key).replace("__PAGE_TITLE__", safe_title)
    if "</body>" in html:
        return html.replace("</body>", snippet + "\n</body>", 1)
    return html + snippet


def copy_home() -> None:
    if not HOMEPAGE_SRC.exists():
        sys.exit(f"❌ 缺主页源文件:{HOMEPAGE_SRC}（持久化首页 home.html）")
    (OUT / "index.html").write_text(
        localize(HOMEPAGE_SRC.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
    print("  ✓ 首页 home.html → dist/index.html（已自托管字体）")


def subset_cjk() -> None:
    """按 dist 里所有 HTML 实际用到的字，把思源黑/宋子集化成小 woff2 放进 fonts/。
    有字体源就现切；没有就回退用 assets/fonts-cjk/ 的缓存。"""
    chars = set(CJK_BASE_CHARS)
    for p in OUT.rglob("*.html"):
        chars |= set(p.read_text(encoding="utf-8", errors="ignore"))
    for ws in "\n\r\t":
        chars.discard(ws)
    charfile = OUT / "_chars.txt"
    charfile.write_text("".join(sorted(chars)), encoding="utf-8")

    pyft = None
    for cand in (SELF / "tools" / "fenv" / "bin" / "pyftsubset",):
        if cand.exists():
            pyft = str(cand); break
    if pyft is None:
        pyft = shutil.which("pyftsubset")

    have_src = all((CJK_SRC / s).exists() for s, _ in CJK_JOBS)
    if pyft and have_src:
        CJK_CACHE.mkdir(parents=True, exist_ok=True)
        for srcname, outname in CJK_JOBS:
            outf = OUT / "fonts" / outname
            subprocess.run([pyft, str(CJK_SRC / srcname), f"--text-file={charfile}",
                            "--flavor=woff2", f"--output-file={outf}",
                            "--no-hinting", "--desubroutinize"], check=True)
            shutil.copy2(outf, CJK_CACHE / outname)
            print(f"  ✓ 子集化 {srcname} → fonts/{outname}（{outf.stat().st_size // 1024} KB）")
    else:
        for _, outname in CJK_JOBS:
            cache = CJK_CACHE / outname
            if cache.exists():
                shutil.copy2(cache, OUT / "fonts" / outname)
                print(f"  ✓ 用缓存子集 fonts/{outname}")
            else:
                print(f"  ⚠️ 无字体源也无缓存:{outname}（思源将回退系统字，建议补 {CJK_SRC}）")
    charfile.unlink(missing_ok=True)


def build() -> list[dict]:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # 字体打包
    fdir = OUT / "fonts"
    fdir.mkdir()
    for f in FONT_FILES:
        s = FONT_SRC / f
        if not s.exists():
            sys.exit(f"❌ 缺字体文件:{s}")
        shutil.copy2(s, fdir / f)
    for f in MOZILLA_FILES:                       # V6 Mozilla 可变字体（有就打包）
        s = FONT_SRC / f
        if s.exists():
            shutil.copy2(s, fdir / f)
    print(f"  ✓ 打包字体 → dist/fonts/ ({', '.join(FONT_FILES + MOZILLA_FILES)})")

    built, missing = [], []
    for src_rel, slug, series, ep, cat, title, dek, screens in MANIFEST:
        src = ROOT / src_rel
        if not src.exists() or src.stat().st_size == 0:
            missing.append(src_rel)
            print(f"  ⚠️  跳过(缺失或空): {src_rel}")
            continue
        dst = OUT / f"{slug}.html"
        dst.parent.mkdir(parents=True, exist_ok=True)
        page_html = localize(src.read_text(encoding="utf-8", errors="replace"))
        page_html = inject_comments(page_html, slug, f"{ep} · {title}")
        dst.write_text(page_html, encoding="utf-8")
        built.append({"slug": slug, "series": series, "ep": ep, "cat": cat,
                      "title": title, "dek": dek, "screens": screens})
        print(f"  ✓ {src_rel}  →  dist/{slug}.html")

    if not built:
        sys.exit("❌ 没有可发布的演示版,检查 MANIFEST 路径。")

    copy_home()
    subset_cjk()
    (OUT / "_headers").write_text(HEADERS_FILE, encoding="utf-8")  # 字体强缓存（CF Pages）
    print(f"\n✅ 已生成 {len(built)} 篇演示版 + 首页（含字体预加载 + 强缓存）→ {OUT}")
    if missing:
        print(f"⚠️  {len(missing)} 篇被跳过:{', '.join(missing)}")
    return built


def write_index(items: list[dict]) -> None:
    # 按系列分组
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(it["series"], []).append(it)

    blocks = []
    for series, eps in groups.items():
        sm = SERIES_META.get(series, {"en": "", "dek": ""})
        cards = []
        for a in eps:
            cards.append(f'''      <a class="card pre" href="{a['slug']}">
        <div class="card-top"><span class="badge">{a['ep']}</span><span class="cat">{a['cat']}</span></div>
        <h3>{a['title']}</h3>
        <p>{a['dek']}</p>
        <div class="card-foot"><span class="screens">{a['screens']} 屏</span><span class="go">进入演示 →</span></div>
      </a>''')
        blocks.append(f'''    <section class="series">
      <div class="series-head pre">
        <div class="series-en">{sm['en']}</div>
        <h2>{series}</h2>
        <p class="series-dek">{sm['dek']}</p>
      </div>
      <div class="grid">
{chr(10).join(cards)}
      </div>
    </section>''')
    blocks_html = "\n".join(blocks)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{SITE_TITLE} · 沉浸式演示 — {BRAND}</title>
<meta name="description" content="{SITE_TAGLINE} 由{BRAND}出品。当前主题:算力账本 COMPUTE LEDGER。">
<meta property="og:type" content="website">
<meta property="og:title" content="{SITE_TITLE} · 沉浸式演示主题站">
<meta property="og:description" content="{SITE_TAGLINE}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%23161514'/%3E%3Cpath d='M13 5 6 18h6l-1 9 9-13h-6z' fill='none' stroke='%23e08a5f' stroke-width='2' stroke-linejoin='round'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.loli.net">
<link rel="preconnect" href="https://gstatic.loli.net" crossorigin>
<link href="https://fonts.loli.net/css2?family=Noto+Sans+SC:wght@400;500;700;800;900&family=Noto+Serif+SC:wght@600;700;900&display=swap" rel="stylesheet">
<style>
  @font-face{{font-family:'Anthropic Sans';src:url('/fonts/anthropicSans.woff2') format('woff2');font-weight:300 800;font-style:normal;font-display:swap;font-feature-settings:'dlig' 0}}
  @font-face{{font-family:'Anthropic Mono';src:url('/fonts/anthropicMono.woff2') format('woff2');font-weight:300 800;font-style:normal;font-display:swap}}
  :root{{
    --bg:#161514;--surface:#221f1d;--surface2:#1b1917;
    --line:rgba(244,242,235,.09);--line2:rgba(244,242,235,.16);--line3:rgba(244,242,235,.26);
    --text:#f4f2eb;--read:#cdc8bd;--text2:#aea99f;--text3:#948e84;--text4:#5f5a52;
    --hot:#e08a5f;--hot2:#efb79b;--hl0:#f6e1d1;--cool:#8fa6bd;--cool2:#aec2d4;
    --font:'Anthropic Sans','Noto Sans SC','PingFang SC',system-ui,sans-serif;
    --serif:'Noto Serif SC',Georgia,serif;
    --mono:'Anthropic Mono','PingFang SC',ui-monospace,monospace;
  }}
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  html{{scroll-behavior:smooth;background:var(--bg);color:var(--text);font-family:var(--font)}}
  body{{-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;overflow-x:hidden;
    background:radial-gradient(1100px 700px at 80% -8%,rgba(224,138,95,.12),transparent 60%),
      radial-gradient(900px 800px at -8% 28%,rgba(143,166,189,.06),transparent 55%),var(--bg)}}
  .grain{{position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.04;
    background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");background-size:200px 200px}}
  .mesh{{position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.5;
    background-image:linear-gradient(rgba(244,242,235,.022) 1px,transparent 1px),linear-gradient(90deg,rgba(244,242,235,.022) 1px,transparent 1px);
    background-size:64px 64px;mask:radial-gradient(circle at 50% 18%,#000,transparent 80%)}}
  .frame{{position:fixed;inset:18px;z-index:1;pointer-events:none}}
  .frame i{{position:absolute;width:22px;height:22px;border:1.5px solid var(--line3)}}
  .frame i:nth-child(1){{top:0;left:0;border-right:0;border-bottom:0}}
  .frame i:nth-child(2){{top:0;right:0;border-left:0;border-bottom:0}}
  .frame i:nth-child(3){{bottom:0;left:0;border-right:0;border-top:0}}
  .frame i:nth-child(4){{bottom:0;right:0;border-left:0;border-top:0}}

  .wrap{{position:relative;z-index:2;max-width:1080px;margin:0 auto;padding:0 clamp(1.5rem,5vw,3rem)}}

  .masthead{{display:flex;justify-content:space-between;align-items:center;font-family:var(--mono);
    font-size:.7rem;letter-spacing:.22em;text-transform:uppercase;color:var(--text3);
    padding:1.7rem 0 1.1rem;border-bottom:1px solid var(--line)}}
  .masthead .l{{display:flex;align-items:center;gap:.7rem;color:var(--text2)}}
  .masthead .live{{width:7px;height:7px;border-radius:50%;background:var(--hot);box-shadow:0 0 0 0 rgba(224,138,95,.5);animation:pulse 2.6s infinite}}
  @keyframes pulse{{0%{{box-shadow:0 0 0 0 rgba(224,138,95,.45)}}70%{{box-shadow:0 0 0 7px rgba(224,138,95,0)}}100%{{box-shadow:0 0 0 0 rgba(224,138,95,0)}}}}

  .hero{{padding:clamp(3.5rem,9vw,6.5rem) 0 clamp(2.5rem,6vw,4rem)}}
  .kicker{{font-family:var(--mono);font-size:.74rem;font-weight:500;letter-spacing:.34em;color:var(--cool2);text-transform:uppercase;display:flex;align-items:center;gap:.9rem;margin-bottom:2rem}}
  .kicker span{{width:3rem;height:1px;background:linear-gradient(90deg,var(--cool),transparent)}}
  .hero h1{{font-family:var(--mono);font-size:clamp(3.4rem,13vw,8rem);font-weight:800;letter-spacing:.04em;line-height:.95;
    background:linear-gradient(96deg,var(--hl0),var(--hot2) 45%,var(--hot));-webkit-background-clip:text;background-clip:text;color:transparent;margin-bottom:1.5rem}}
  .hero .tag{{font-size:clamp(1.1rem,2.4vw,1.4rem);color:var(--read);max-width:40rem;line-height:1.8}}
  .hero .tag b{{color:var(--text);font-weight:700}}
  .hero .howto{{margin-top:1.8rem;font-family:var(--mono);font-size:.74rem;letter-spacing:.06em;color:var(--text3);
    display:inline-flex;align-items:center;gap:.7rem;border:1px solid var(--line2);border-radius:9999px;padding:.6rem 1.2rem}}
  .hero .howto b{{color:var(--hot2);font-weight:600}}

  .series{{padding:clamp(2rem,5vw,3.5rem) 0}}
  .series-head{{margin-bottom:2rem}}
  .series-en{{font-family:var(--mono);font-size:.72rem;letter-spacing:.28em;text-transform:uppercase;color:var(--cool2);margin-bottom:.7rem}}
  .series h2{{font-size:clamp(1.7rem,4vw,2.5rem);font-weight:800;letter-spacing:-.02em;margin-bottom:.6rem}}
  .series-dek{{color:var(--text2);font-size:1.02rem;line-height:1.7;max-width:42rem}}

  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:1.1rem}}
  .card{{position:relative;display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--line);
    border-radius:18px;padding:1.7rem 1.8rem;text-decoration:none;color:inherit;overflow:hidden;isolation:isolate;
    box-shadow:0 1px 2px rgba(0,0,0,.25),0 16px 38px rgba(0,0,0,.28);
    transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease}}
  .card::before{{content:'';position:absolute;inset:0;z-index:-1;border-radius:inherit;pointer-events:none;
    background:linear-gradient(158deg,rgba(244,242,235,.05),transparent 40%)}}
  .card:hover{{transform:translateY(-4px);border-color:rgba(224,138,95,.5);
    box-shadow:0 18px 42px -16px rgba(224,138,95,.4)}}
  .card-top{{display:flex;align-items:center;gap:.7rem;margin-bottom:1.1rem}}
  .badge{{font-family:var(--mono);font-size:.72rem;font-weight:700;color:#231a14;background:var(--hot);
    padding:.25rem .65rem;border-radius:999px;letter-spacing:.04em}}
  .cat{{font-family:var(--mono);font-size:.64rem;letter-spacing:.14em;text-transform:uppercase;color:var(--text3)}}
  .card h3{{font-size:1.32rem;font-weight:800;line-height:1.3;margin-bottom:.6rem;letter-spacing:-.01em;text-wrap:balance}}
  .card p{{color:var(--text2);font-size:.95rem;line-height:1.7;flex:1}}
  .card-foot{{display:flex;justify-content:space-between;align-items:center;margin-top:1.3rem;
    padding-top:1rem;border-top:1px solid var(--line)}}
  .screens{{font-family:var(--mono);font-size:.7rem;letter-spacing:.1em;color:var(--text4)}}
  .go{{font-family:var(--mono);font-size:.78rem;font-weight:700;color:var(--hot2);letter-spacing:.02em}}

  .about{{margin-top:clamp(2.5rem,6vw,4.5rem);max-width:48rem}}
  .about-en{{font-family:var(--mono);font-size:.7rem;letter-spacing:.26em;text-transform:uppercase;color:var(--text3);margin-bottom:1rem}}
  .about-id{{font-size:clamp(1.15rem,2.4vw,1.5rem);font-weight:800;color:var(--text);line-height:1.4;letter-spacing:-.01em;margin-bottom:1rem;text-wrap:balance}}
  .about-id b{{color:var(--hot2);font-weight:800}}
  .about-line{{color:var(--text2);font-size:1.02rem;line-height:1.85;margin-bottom:1rem}}
  .about-line b{{color:var(--read);font-weight:700}}
  .about-cta{{color:var(--hot2);font-size:1.02rem;line-height:1.7}}
  .about-cta b{{color:var(--hl0);font-weight:700}}

  footer{{margin-top:clamp(2.5rem,6vw,4rem);padding:2.6rem 0 3.5rem;border-top:1px solid var(--line);
    display:flex;justify-content:space-between;flex-wrap:wrap;gap:1rem;align-items:center}}
  footer .brand{{font-family:var(--font);font-size:1.05rem;font-weight:800;color:var(--text)}}
  footer .meta{{font-family:var(--mono);font-size:.74rem;color:var(--text3);letter-spacing:.06em}}

  .pre{{opacity:0;transform:translateY(22px);transition:opacity .7s cubic-bezier(.22,.61,.36,1),transform .7s cubic-bezier(.22,.61,.36,1)}}
  .pre.in{{opacity:1;transform:none}}
  @media (prefers-reduced-motion:reduce){{.pre{{opacity:1;transform:none;transition:none}}}}
  @media(max-width:560px){{.grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="grain"></div>
<div class="mesh"></div>
<div class="frame"><i></i><i></i><i></i><i></i></div>

<div class="wrap">
  <div class="masthead">
    <div class="l"><span class="live"></span>{SITE_TITLE} / 沉浸式演示</div>
    <div class="r">{BRAND}</div>
  </div>

  <header class="hero">
    <div class="kicker pre"><span></span>沉浸式阅览 · 一屏一镜 · 可翻页 / 自动播放</div>
    <h1 class="pre">{SITE_TITLE}</h1>
    <p class="tag pre">{SITE_TAGLINE.replace("沉浸式阅览 · ", "")}<br>把复杂主题做成一场<b>可翻页的演示</b>——像看 PPT，也像看一支安静的视频。</p>
    <div class="howto pre">▸ 进入后 <b>方向键 / 空格 / 点击</b> 翻页，右下可 <b>自动播放</b></div>
  </header>

{blocks_html}

  <section class="about pre">
    <div class="about-en">ABOUT · {BRAND}</div>
    <p class="about-id">「禾口王」拼起来是个「程」字 —— <b>真会用 AI 的程序员</b>。</p>
    <p class="about-line">不聊 AI 会不会取代你，只聊先用 AI 的人怎么取代你。我自己先把 AI 工作流跑通，再拆给你——把 6 小时的活干成 30 分钟，一个人干完一支团队。<b>你正在看的这个演示站，就是这套流水线顺手产出的东西之一。</b></p>
    <p class="about-cta">🎁 微信搜 <b>{BRAND}</b>，回复 <b>工厂</b>，领「AI 内容流水线手册」。</p>
  </section>

  <footer>
    <span class="brand">{BRAND}</span>
    <span class="meta">{HANDLE} · 不聊 AI 会不会取代你，只聊先用 AI 的人怎么取代你</span>
  </footer>
</div>

<script>
(function(){{
  var motionOK=!window.matchMedia||window.matchMedia('(prefers-reduced-motion: no-preference)').matches;
  var els=[].slice.call(document.querySelectorAll('.pre'));
  if(!motionOK||!('IntersectionObserver' in window)){{els.forEach(function(e){{e.classList.add('in')}});return;}}
  var io=new IntersectionObserver(function(es){{es.forEach(function(en){{if(en.isIntersecting){{en.target.classList.add('in');io.unobserve(en.target);}}}});}},{{rootMargin:'0px 0px -8% 0px',threshold:.06}});
  els.forEach(function(e){{io.observe(e)}});
  setTimeout(function(){{els.forEach(function(e){{e.classList.add('in')}});}},1500);
}})();
</script>
</body>
</html>'''
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print("  ✓ 生成沉浸式导航页  →  dist/index.html")


# ---------------------------------------------------------------------------
def ensure_wrangler() -> str | None:
    exe = shutil.which("wrangler")
    if exe:
        return exe
    if shutil.which("npm") is None:
        print("\n⚠️  没有 npm,无法安装 Wrangler。请先装 Node.js。")
        return None
    print("\n📥 未检测到 Wrangler,自动安装:npm i -g wrangler …")
    try:
        subprocess.run(["npm", "i", "-g", "wrangler"], check=True)
    except subprocess.CalledProcessError:
        print("⚠️  Wrangler 安装失败,请手动 `npm i -g wrangler`。")
        return None
    return shutil.which("wrangler")


def deploy_cloudflare() -> None:
    exe = ensure_wrangler()
    if exe is None:
        return
    res = subprocess.run([exe, "whoami"], capture_output=True, text=True)
    out = (res.stdout + res.stderr).lower()
    if res.returncode != 0 or "not authenticated" in out or "not logged" in out:
        print("\n🔑 还没登录 Cloudflare。在终端跑一次(浏览器授权):")
        print("     wrangler login")
        print("   登录后重跑:python3 演读DECK/publish.py")
        return
    # 项目不存在则创建(已存在会报错,忽略)
    subprocess.run([exe, "pages", "project", "create", CF_PROJECT,
                    "--production-branch", "main"], capture_output=True)
    # 配置式部署:不带目录参数,让 wrangler 读 SELF/wrangler.toml
    # (pages_build_output_dir=dist + functions/ + D1 绑定一起随部署生效),cwd 必须是配置所在目录
    cmd = [exe, "pages", "deploy",
           "--branch", "main", "--commit-dirty=true"]
    print(f"\n🚀 部署到 Cloudflare Pages(读 wrangler.toml): {' '.join(cmd)}  (cwd={SELF})")
    try:
        subprocess.run(cmd, check=True, cwd=str(SELF))
        print(f"\n✅ 部署完成!公开地址:https://{CF_PROJECT}.pages.dev")
    except subprocess.CalledProcessError as e:
        sys.exit(f"❌ 部署失败(exit {e.returncode})。先 `wrangler login`;若报 D1 绑定错,"
                 f"确认 wrangler.toml 里 database_id 已填(见 README「留言板」一节);"
                 f"若 {CF_PROJECT}.pages.dev 名称被占用,改 CF_PROJECT 换一个前缀。")


def main() -> None:
    ap = argparse.ArgumentParser(description="发布沉浸式演示主题站(默认构建+部署到 Cloudflare Pages / keynote)")
    ap.add_argument("--build-only", action="store_true", help="只生成 dist/,不部署")
    args = ap.parse_args()

    print(f"📦 生成发布目录: {OUT}")
    build()
    if args.build_only:
        print(f"\n本地预览:  open {OUT}/index.html")
        print(f"一键发布:  python3 演读DECK/publish.py")
    else:
        deploy_cloudflare()


if __name__ == "__main__":
    main()
