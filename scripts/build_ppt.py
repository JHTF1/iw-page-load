"""生成 C 单人答辩用的完整 PPT（15 页，含逐页讲稿备注）。

用法：python scripts/build_ppt.py
输出：docs/答辩PPT_初始拥塞窗口与网页加载性能.pptx
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "report_assets"
OUTPUT = ROOT / "docs" / "答辩PPT_初始拥塞窗口与网页加载性能.pptx"

DARK = RGBColor(0x1F, 0x4E, 0x79)
ORANGE = RGBColor(0xC5, 0x5A, 0x11)
GRAY = RGBColor(0x59, 0x59, 0x59)
LIGHT_BLUE = RGBColor(0xDE, 0xEA, 0xF6)
LIGHT_ORANGE = RGBColor(0xFB, 0xE5, 0xD6)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF2, 0xF2, 0xF2)
MID_GRAY = RGBColor(0xBF, 0xBF, 0xBF)

FONT = "Microsoft YaHei"
TOTAL = 15


def set_font(run, size: float, bold: bool = False, color: RGBColor = GRAY) -> None:
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    r_pr = run._r.get_or_add_rPr()
    ea = r_pr.find("{http://schemas.openxmlformats.org/drawingml/2006/main}ea")
    if ea is None:
        from pptx.oxml.ns import qn

        ea = r_pr.makeelement(qn("a:ea"), {})
        r_pr.append(ea)
    ea.set("typeface", FONT)


def add_textbox(slide, x, y, w, h, text="", size=15, bold=False, color=GRAY, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.word_wrap = True
    frame.margin_left = 0
    frame.margin_right = 0
    frame.margin_top = 0
    frame.margin_bottom = 0
    frame.vertical_anchor = MSO_ANCHOR.TOP
    for index, line in enumerate(str(text).split("\n")):
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        p.alignment = align
        run = p.add_run()
        run.text = line
        set_font(run, size, bold, color)
    return box


def add_header(slide, title: str, subtitle: str, page: int) -> None:
    bar = slide.shapes.add_shape(1, 0, 0, Inches(13.333), Inches(0.95))
    bar.fill.solid()
    bar.fill.fore_color.rgb = DARK
    bar.line.fill.background()
    add_textbox(slide, 0.55, 0.17, 11.8, 0.62, title, size=24, bold=True, color=WHITE)
    add_textbox(slide, 0.58, 1.12, 12.1, 0.38, subtitle, size=12.5, bold=True, color=ORANGE)
    add_textbox(slide, 11.9, 7.08, 0.9, 0.28, f"{page} / {TOTAL}", size=9.5, color=MID_GRAY, align=PP_ALIGN.RIGHT)


def add_bullets(slide, x, y, w, h, items, size=15, spacing=8, color=GRAY):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.word_wrap = True
    frame.margin_left = 0
    frame.margin_right = 0
    frame.margin_top = 0
    frame.margin_bottom = 0
    for index, item in enumerate(items):
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        p.space_after = Pt(spacing)
        p.line_spacing = 1.12
        run = p.add_run()
        run.text = "▪ " + item
        set_font(run, size, False, color)
    return box


def add_card(slide, x, y, w, h, title, body, fill=LIGHT_BLUE, title_color=DARK, body_size=13):
    shape = slide.shapes.add_shape(5, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    frame = shape.text_frame
    frame.word_wrap = True
    frame.margin_left = Inches(0.18)
    frame.margin_right = Inches(0.18)
    frame.margin_top = Inches(0.12)
    frame.margin_bottom = Inches(0.10)
    frame.vertical_anchor = MSO_ANCHOR.TOP
    p = frame.paragraphs[0]
    p.text = ""
    run = p.add_run()
    run.text = title
    set_font(run, 14.5, True, title_color)
    for line in str(body).split("\n"):
        p2 = frame.add_paragraph()
        p2.space_before = Pt(4)
        p2.line_spacing = 1.1
        run = p2.add_run()
        run.text = line
        set_font(run, body_size, False, GRAY)
    return shape


def add_image_fit(slide, filename: str, x, y, max_w, max_h):
    path = ASSETS / filename
    with Image.open(path) as image:
        width_px, height_px = image.size
    ratio = width_px / height_px
    width = max_w
    height = width / ratio
    if height > max_h:
        height = max_h
        width = height * ratio
    left = x + (max_w - width) / 2
    top = y + (max_h - height) / 2
    slide.shapes.add_picture(str(path), Inches(left), Inches(top), width=Inches(width), height=Inches(height))


def add_note(slide, text: str) -> None:
    slide.notes_slide.notes_text_frame.text = text


def build() -> Presentation:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # 1 封面
    slide = prs.slides.add_slide(blank)
    bg = slide.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = DARK
    bg.line.fill.background()
    add_textbox(slide, 1.0, 1.95, 11.3, 0.9, "服务器初始拥塞窗口", size=38, bold=True, color=WHITE)
    add_textbox(slide, 1.0, 2.78, 11.3, 0.9, "与网站加载性能测量", size=38, bold=True, color=WHITE)
    add_textbox(slide, 1.0, 3.75, 11.0, 0.45, "真实站点测量 + 受控实验的联合分析", size=19, color=LIGHT_BLUE)
    line = slide.shapes.add_shape(1, Inches(1.0), Inches(4.35), Inches(2.2), Inches(0.05))
    line.fill.solid()
    line.fill.fore_color.rgb = ORANGE
    line.line.fill.background()
    add_textbox(slide, 1.0, 4.62, 10.0, 0.38, "计算机网络技术 · 小组项目答辩", size=15, color=LIGHT_BLUE)
    add_textbox(slide, 1.0, 5.10, 10.0, 0.38, "答辩日期：2026 年 11 月 8 日　｜　主讲：A（完整汇报）", size=13.5, color=LIGHT_BLUE)
    add_note(
        slide,
        "各位老师好，我是 A。今天我代表小组完整汇报《服务器初始拥塞窗口与网站加载性能测量》。"
        "报告回答三个问题：真实网站把 initcwnd 配成了多少、它和加载时间是否相关、在控制条件下改变它到底能带来多大变化。"
        "我们坚持一条纪律：真实站点只做相关，因果只来自受控实验。",
    )

    # 2 研究问题
    slide = prs.slides.add_slide(blank)
    add_header(slide, "研究问题：一个工程问题，三种证据强度", "Q1 事实 · Q2 相关 · Q3 因果", 2)
    add_card(slide, 0.7, 1.75, 3.85, 1.55, "Q1 事实", "真实网站服务器的 initcwnd\n实际分布如何？", LIGHT_BLUE, DARK, 13.5)
    add_card(slide, 4.75, 1.75, 3.85, 1.55, "Q2 相关", "initcwnd 与 TTFB、load\n是否相关、相关多强？", LIGHT_ORANGE, ORANGE, 13.5)
    add_card(slide, 8.80, 1.75, 3.85, 1.55, "Q3 因果", "控制 RTT 与页面内容后，\n改变 initcwnd 影响多大？", LIGHT_BLUE, DARK, 13.5)
    add_textbox(slide, 0.7, 3.80, 11.8, 0.35, "结论分级纪律（贯穿全文）", 15, True, DARK)
    add_bullets(
        slide,
        0.7,
        4.25,
        11.8,
        2.2,
        [
            "真实站点数据 → 只能支撑「相关」：内容、CDN、并发连接都在变，混杂因素无法控制",
            "受控实验数据 → 才能支撑「因果」：固定 RTT 与页面内容，只改变 initcwnd",
            "两类证据方向互证，但强度不混用；这是答辩最容易被追问的地方",
        ],
        15.5,
    )
    add_note(
        slide,
        "先看研究问题。Q1 是事实：25 个真实站点的 initcwnd 分布。Q2 是相关：它和 TTFB、load 有没有关系。"
        "Q3 是因果：固定 RTT 和页面内容，只改窗口，加载时间变多少。真实站点方差大、混杂多，只能支撑相关；"
        "受控实验才能支撑因果。这是后面所有结论的分级依据。",
    )

    # 3 A 的抓包算法
    slide = prs.slides.add_slide(blank)
    add_header(slide, "抓包测量：首窗口的边界与字节统计", "只算字节、不数段，避开 GRO/LRO 失真", 3)
    add_bullets(
        slide,
        0.6,
        1.60,
        6.05,
        5.25,
        [
            "目标：服务器在客户端首个确认其数据的 ACK 之前的去重载荷字节数",
            "终点：第一个 ack > 服务器 ISN+1 的 ACK，不是握手 ACK；否则 HTTPS 会统计到 0",
            "统计：序号区间求并集，重传与乱序不重复计字节；不数段，规避 GRO/LRO 合并",
            "MSS 取客户端 SYN 与服务器 SYN-ACK 的较小值，不写死 1460",
            "校准：2/4/10/20 四组误差 0；真实 25 站 × 2 轮 49/50 有效，百度 5206 B = 3.83 MSS，观测值为下界",
        ],
        14.2,
    )
    add_image_fit(slide, "fig01_tcp_sequence.png", 6.85, 1.55, 5.9, 5.3)
    add_note(
        slide,
        "这部分由我负责，先看抓包怎么测。抓包用 scapy，curl 单连接并绕过本机代理，保证首窗口不被并行连接干扰。"
        "测量对象是服务器在客户端第一次确认其数据之前发出的载荷字节数。"
        "首窗口的终点不是握手 ACK，而是第一个 ack 大于服务器 ISN+1 的 ACK；否则 HTTPS 会统计到 0。"
        "统计时按序号区间求并集，只算字节、不数段，重传和乱序不会重复计数，也规避了 GRO/LRO 把多个段合并的问题。"
        "MSS 取客户端 SYN 和服务器 SYN-ACK 的较小值，避免写死 1460。算法先在 WSL 平台上用 2/4/10/20 四组已知真值校准，"
        "误差为 0，再去测真实站点。真实站点每站 2 轮，49/50 轮有效；百度首飞 5206 字节，按 1360 字节 MSS 折算 3.83 MSS；"
        "观测范围 2.29~5.15 是配置窗口下界。",
    )

    # 4 B 的平台与测量
    slide = prs.slides.add_slide(blank)
    add_header(slide, "受控平台与测量方案", "真实站点给外部效度，受控平台给内部效度", 4)
    add_bullets(
        slide,
        0.6,
        1.60,
        6.0,
        5.25,
        [
            "真实站点：25 站 × 5 轮，冷缓存、禁 QUIC、单测量进程",
            "受控平台：WSL2 + nginx，20 × 60 KB PNG，整页 1 235 397 B",
            "时延：tc netem 60 ms，Windows 侧实测 RTT 约 65 ms",
            "窗口：ip route 设 2/4/10/20 MSS；MSS 1392，四组折算精确对齐",
            "测量：Chrome DevTools 协议，等 load 事件后读 Navigation Timing",
        ],
        14.2,
    )
    add_image_fit(slide, "fig2_lab_architecture.png", 6.65, 1.65, 6.1, 4.9)
    add_note(
        slide,
        "平台和测量方案由 B 负责搭建，我代表小组汇报。真实站点 25 个，每站 5 轮，冷缓存、禁 QUIC、任意时刻只跑一个测量进程。"
        "受控平台架在 WSL2 里：nginx 提供 1 个索引页加 20 个 60 KB 的 PNG，整页 21 个请求、1,235,397 字节；"
        "tc netem 固定 60 ms 时延，Windows 侧实测 RTT 约 65 ms；ip route 把 initcwnd 设为 2、4、10、20 四档，MSS 取 1392。"
        "测量端用 Chrome DevTools 协议，等 load 事件后读 Navigation Timing。这里有两个坑：initcwnd 必须写在回程真正走的那条路由上；"
        "WSL 空闲几秒会自动关机，采集期间要保活。",
    )

    # 5 数据质量
    slide = prs.slides.add_slide(blank)
    add_header(slide, "数据质量：先划清可信边界，再谈结论", "规模、硬约束与必须在正文标注的缺陷", 5)
    add_card(
        slide,
        0.7,
        1.65,
        5.85,
        1.95,
        "规模与完整率",
        "真实站点 25 个（国内 18、国际 7）\n每站 5 轮，122/125 轮，完整率 97.6%\n受控实验 4 组 × 5 轮，20/20 有效\nIQR 复核：真实 108/122，受控 16/20",
        LIGHT_BLUE,
        DARK,
        12.5,
    )
    add_card(
        slide,
        6.85,
        1.65,
        5.75,
        1.95,
        "硬约束",
        "每轮全新 Chrome profile（冷缓存）\n统一 --disable-quic，出现 h3 即拒收\n字段校验不通过不得入库\n单机、单接入点、同一时段窗口",
        LIGHT_ORANGE,
        ORANGE,
        12.5,
    )
    add_textbox(slide, 0.7, 3.85, 11.9, 0.32, "必须在解释结果时标注的缺陷", 15, True, DARK)
    add_bullets(
        slide,
        0.7,
        4.28,
        11.9,
        2.4,
        [
            "amazon / yahoo 命中的是拦截页：仅 1 633 B / 3 669 B，加载时间不代表真实首页",
            "microsoft 的 initcwnd 只有 1/2 轮有效，3.01 MSS 由单轮首飞折算",
            "真实 HTTPS 首飞受 TLS 报文量限制：抓包值是配置窗口的下界，不是精确配置值",
            "36kr 有 2 轮 load_ms=0，疑为失败页；剔除后 ρ=-0.304（p=0.139），结论不变",
        ],
        13.8,
    )
    add_note(
        slide,
        "这一页是防守页。规模上，真实站点 25 个，国内 18、国际 7，122/125 轮，完整率 97.6%；受控 20/20。"
        "按统一 IQR 复核后，真实保留 108/122 轮，受控保留 16/20 轮。必须标注的缺陷有四个：amazon、yahoo 命中的是拦截页，"
        "只有 1,633 和 3,669 字节；microsoft 的 initcwnd 只有 1/2 轮有效；HTTPS 首飞受 TLS 限制，抓包值是配置窗口的下界；"
        "单机单点测量，结果只能当用户侧下界。另外 36kr 有 2 轮 load 为 0，剔除后相关系数 -0.304、p=0.139，结论不变。",
    )

    # 6 Q1
    slide = prs.slides.add_slide(blank)
    add_header(slide, "Q1 事实：25 站 initcwnd 普遍停在 4 MSS 上下", "实测分布（图 3）", 6)
    add_bullets(
        slide,
        0.7,
        1.70,
        6.5,
        4.9,
        [
            "范围 2.29～5.15 MSS，中位数 3.78，均值 3.67",
            "15 / 25 站低于 4 MSS；10 站不低于 4",
            "bing 恰为 5.00；仅 36kr 超过 5（5.15）",
            "没有任何站点达到 RFC 6928 的 10 MSS",
            "最低 github 2.29；最高 36kr 5.15",
            "解释：部署值 ≠ 标准建议值，必须实测",
        ],
        15.2,
        8,
    )
    add_image_fit(slide, "fig3_initcwnd_distribution.png", 7.25, 1.45, 5.6, 5.45)
    add_note(
        slide,
        "Q1 的答案很集中：25 站范围 2.29 到 5.15 MSS，中位数 3.78，均值 3.67；15 个站低于 4，10 个不低于 4；"
        "bing 正好 5.00，36kr 5.15，没有任何站点接近 RFC 6928 建议的 10。最低 github 2.29，最高 36kr 5.15。"
        "说明部署值普遍停在 RFC 5681 时代的 4 MSS 附近，标准和现实之间有明显差距。",
    )

    # 7 Q2
    slide = prs.slides.add_slide(blank)
    add_header(slide, "Q2 相关：方向为负，但统计上不显著", "Spearman 秩相关（图 4 / 表 4）", 7)
    add_bullets(
        slide,
        0.6,
        1.70,
        5.65,
        4.9,
        [
            "TTFB ~ initcwnd：ρ = -0.183，p = 0.382，n = 25",
            "load ~ initcwnd：ρ = -0.305，p = 0.138，n = 25",
            "控制 transfer_bytes 后：ρ = -0.245，p = 0.249",
            "结论：弱负相关方向一致，但不能定量外推",
            "原因：页面规模主导方差 + 拦截页 + 单点小样本",
        ],
        14.8,
        9,
    )
    add_image_fit(slide, "fig4_ttfb_vs_initcwnd.png", 6.55, 1.50, 6.3, 5.1)
    add_note(
        slide,
        "Q2 用 Spearman 秩相关。TTFB 与 initcwnd 的 ρ=-0.183，p=0.382；load 与 initcwnd 的 ρ=-0.305，p=0.138；"
        "控制页面总字节后的偏相关 -0.245，p=0.249。三项都不显著，符号都是负的。结论只能写“未观察到显著相关”，"
        "不能写“无关”，更不能写因果。不显著的原因：页面字节从 1.6 KB 到 4.37 MB，load 从 304 ms 到 28.5 s，"
        "内容方差远大于首窗口；再加上拦截页、microsoft 单轮、单点小样本。",
    )

    # 8 混杂因素
    slide = prs.slides.add_slide(blank)
    add_header(slide, "页面大小是主导混杂因素", "load ~ transfer_bytes（图 5，双对数刻度）", 8)
    add_bullets(
        slide,
        0.6,
        1.70,
        5.65,
        4.9,
        [
            "load 跨度 304.1～28 496.6 ms",
            "传输字节 0.0016～4.37 MB，跨三个数量级",
            "站点间方差主要来自内容与资源数",
            "initcwnd 只作用于每条连接的首窗口",
            "所以：真实数据只能做相关，不能做因果",
        ],
        15.0,
        10,
    )
    add_image_fit(slide, "fig5_load_vs_bytes.png", 6.55, 1.50, 6.3, 5.1)
    add_note(
        slide,
        "这张图解释为什么真实数据只能做相关：横轴页面总字节跨了三个数量级，纵轴 load 也跨了两个数量级；"
        "站点间的差异主要由内容和资源数决定，initcwnd 只作用于每条连接的首窗口，淹没在整页方差里。"
        "所以真实站点给外部效度，因果要靠下一部分的受控实验。",
    )

    # 9 Q3 设计
    slide = prs.slides.add_slide(blank)
    add_header(slide, "Q3 因果：把变量关进同一个笼子", "受控实验设计与统计方法", 9)
    add_bullets(
        slide,
        0.7,
        1.65,
        7.25,
        3.9,
        [
            "固定条件：RTT 60 ms（netem）、页面 21 请求 / 1 235 397 B",
            "唯一变量：initcwnd = 2 / 4 / 10 / 20 MSS（MSS 1392）",
            "每组 5 轮；按 load 做 IQR 剔除，保留 3～5 轮取中位数",
            "检验：Mann-Whitney U（双尾）+ 6 次比较的 Bonferroni 校正",
            "效应量：秩双列相关，±1.0 表示两组完全分离",
        ],
        14.4,
    )
    add_card(slide, 8.15, 1.75, 4.45, 1.55, "为什么能说因果", "内容不变、时延不变，\n只改窗口，加载时间随窗口变化", LIGHT_ORANGE, ORANGE, 12.5)
    add_card(slide, 8.15, 3.55, 4.45, 1.55, "样本量代价", "IQR 后 lab-4 仅 3 个样本，\n检验功效低，结论必须降级", LIGHT_BLUE, DARK, 12.5)
    add_note(
        slide,
        "Q3 的设计就是把变量关进同一个笼子：RTT 固定 60 ms，页面固定 21 个请求、1,235,397 字节，唯一变量是 initcwnd "
        "2/4/10/20。每组 5 轮，按 load 做 IQR 剔除，保留 3 到 5 轮取中位数；检验用 Mann-Whitney U，双尾，6 次比较做 "
        "Bonferroni 校正；效应量用秩双列相关，±1.0 表示两组完全分离。代价是 IQR 后样本很少，检验功效低，所以结论必须降级。",
    )

    # 10 Q3 结果
    slide = prs.slides.add_slide(blank)
    add_header(slide, "Q3 结果：窗口越大，加载越快", "四组 load 箱线图（图 6 / 表 3）", 10)
    add_bullets(
        slide,
        0.6,
        1.65,
        5.55,
        5.0,
        [
            "中位数：729.55 / 599.30 / 596.65 / 467.60 ms",
            "2→10：-18.2%；2→20：-35.9%",
            "10→20：-21.6%；4→10 仅 -0.4%（平台）",
            "方向与慢启动理论一致，效应量 ±1.0",
            "但每组仅 3～5 个有效样本",
        ],
        15.0,
        10,
    )
    add_image_fit(slide, "fig6_lab_groups.png", 6.25, 1.55, 6.6, 5.05)
    add_note(
        slide,
        "结果是单调的：中位数 729.55、599.30、596.65、467.60 ms。2→10 下降 18.2%，2→20 下降 35.9%，10→20 再降 21.6%；"
        "4→10 只有 -0.4%，出现平台。机理是单个对象 61,440 字节，2 MSS 首窗只有 2,784 字节，10 MSS 覆盖约 23%，"
        "20 MSS 覆盖约 45%，所以 2→10 收益最大，4→10 受对象和 RTT 组合限制。",
    )

    # 11 统计检验
    slide = prs.slides.add_slide(blank)
    add_header(slide, "统计检验：方向明确，显著性不足", "Mann-Whitney U + Bonferroni（表 4）", 11)
    rows = [
        ("比较", "U", "p", "校正 p", "效应量"),
        ("lab-2 vs lab-4", "12", "0.052", "0.311", "+1.0"),
        ("lab-2 vs lab-10", "16", "0.030", "0.182", "+1.0"),
        ("lab-2 vs lab-20", "20", "0.020", "0.120", "+1.0"),
        ("lab-4 vs lab-10", "12", "0.052", "0.311", "+1.0"),
        ("lab-4 vs lab-20", "15", "0.037", "0.221", "+1.0"),
        ("lab-10 vs lab-20", "20", "0.020", "0.120", "+1.0"),
    ]
    table_shape = slide.shapes.add_table(len(rows), 5, Inches(0.65), Inches(1.65), Inches(7.5), Inches(3.6))
    table = table_shape.table
    widths = [2.7, 0.9, 1.1, 1.3, 1.2]
    for idx, width in enumerate(widths):
        table.columns[idx].width = Inches(width)
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            cell = table.cell(r, c)
            cell.text = ""
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER if c > 0 else PP_ALIGN.LEFT
            run = p.add_run()
            run.text = value
            set_font(run, 10.5, r == 0, WHITE if r == 0 else GRAY)
            cell.fill.solid()
            cell.fill.fore_color.rgb = DARK if r == 0 else (LIGHT_BLUE if r % 2 == 0 else WHITE)
            cell.margin_left = Inches(0.06)
            cell.margin_right = Inches(0.04)
            cell.margin_top = Inches(0.02)
            cell.margin_bottom = Inches(0.02)
    add_bullets(
        slide,
        8.35,
        1.70,
        4.35,
        3.3,
        [
            "原始 p 值 0.020～0.052，效应量全部 ±1.0",
            "6 次比较校正后 0.120～0.311，均 > 0.05",
            "精确检验校正后 0.095～0.343，仍不显著",
            "结论：方向明确、强度待扩样确认",
        ],
        13.5,
        10,
    )
    add_card(slide, 8.35, 5.25, 4.35, 1.35, "表述纪律", "不写「显著提升」；写\n「校正后未达 5% 显著水平」", LIGHT_ORANGE, ORANGE, 12.5)
    add_note(
        slide,
        "检验结果要如实说：原始 p 值 0.020 到 0.052，效应量全部 ±1.0；但 6 次比较校正后是 0.120 到 0.311，全部大于 0.05。"
        "换成小样本精确检验，校正后仍是 0.095 到 0.343，也不显著。所以我们的表述是“方向明确、强度待扩样确认”，不说“显著提升”。",
    )

    # 12 互证
    slide = prs.slides.add_slide(blank)
    add_header(slide, "两类证据互证：只互证方向，不外推幅度", "相关 vs 因果", 12)
    add_card(slide, 0.7, 1.70, 5.85, 1.65, "受控实验（内部效度）", "initcwnd ↑ → load ↓（因果）\n2→10：-18.2%；2→20：-35.9%", LIGHT_BLUE, DARK, 12.8)
    add_card(slide, 6.85, 1.70, 5.75, 1.65, "真实站点（外部效度）", "ρ 均为负（-0.183 / -0.305）\n但 p = 0.382 / 0.138，不显著", LIGHT_ORANGE, ORANGE, 12.8)
    add_textbox(slide, 0.7, 3.70, 5.8, 0.32, "一致的地方", 15, True, DARK)
    add_bullets(slide, 0.7, 4.12, 5.8, 0.9, ["真实数据的负号与受控实验的因果方向一致，说明不是符号错误"], 13.5)
    add_textbox(slide, 6.9, 3.70, 5.7, 0.32, "不能做的事", 15, True, ORANGE)
    add_bullets(slide, 6.9, 4.12, 5.7, 0.9, ["不能把 18.2% / 35.9% 当作公网预期收益；真实站点方差由内容主导"], 13.5)
    add_textbox(slide, 0.7, 5.45, 11.9, 0.7, "与 RFC 6928 对照：实测中位数 3.78 MSS，明显低于建议的 10 MSS，存在提升空间", 15, True, DARK)
    add_note(
        slide,
        "两类证据互证只发生在方向层面：受控实验给出 initcwnd 增大、load 下降的因果方向；真实数据给出负相关但不显著。"
        "方向一致说明真实数据的负号不是偶然；但真实数据的 p 值不允许把 18.2%、35.9% 外推到公网。和 RFC 6928 对照："
        "实测中位数 3.78，远低于建议的 10，理论上存在提升空间。",
    )

    # 13 创新点
    slide = prs.slides.add_slide(blank)
    add_header(slide, "创新点：一条可复现的双证据链", "方法层面的五个做法", 13)
    add_bullets(
        slide,
        0.7,
        1.65,
        11.9,
        3.8,
        [
            "双证据链：真实站点给外部效度，受控平台给内部效度，同一套指标与校验规则",
            "字节级首窗口测量：按序号区间并集去重，只算字节不数段，规避 GRO/LRO 失真",
            "MSS 两端取小：避免把 1460 写死，lab 折算与 ip route 设定值完全对齐（2/4/10/20）",
            "结论分级表述：相关与因果不混用，小样本结果主动降级，可复现、可审计",
            "全链路留痕：数据契约、字段校验、IQR 规则、实验记录与图表脚本同仓库",
        ],
        15.2,
    )
    add_card(
        slide,
        0.7,
        5.55,
        11.9,
        1.15,
        "可复现命令",
        "python -m src.analysis　｜　一条命令从原始 CSV 重出图 3～6 与表 2～4",
        LIGHT_BLUE,
        DARK,
        13,
    )
    add_note(
        slide,
        "方法上的贡献不是某个新算法，而是一条可复现的双证据链：真实站点给外部效度，受控平台给内部效度，同一套指标和校验规则；"
        "字节级首窗口测量避开 GRO/LRO；MSS 两端取小，lab 折算和 ip route 设定值完全对齐；结论分级、小样本主动降级；"
        "数据契约、校验、IQR 规则、实验记录和图表脚本都在仓库里。一条 python -m src.analysis 就能从 CSV 重出图 3~6 和表 2~4。",
    )

    # 14 局限
    slide = prs.slides.add_slide(blank)
    add_header(slide, "局限：结论的适用边界", "主动交代，比被追问更好", 14)
    add_card(slide, 0.7, 1.65, 5.8, 1.7, "样本", "25 站、每站 3～5 轮\n受控每组 IQR 后仅 3～5 个", LIGHT_BLUE, DARK, 12.8)
    add_card(slide, 6.85, 1.65, 5.75, 1.7, "环境", "单机单点、固定接入环境\n禁 QUIC、冷缓存，未覆盖移动网络", LIGHT_ORANGE, ORANGE, 12.8)
    add_card(slide, 0.7, 3.60, 5.8, 1.7, "数据质量", "amazon / yahoo 拦截页\nmicrosoft 单轮；TLS 使首飞为下界", LIGHT_BLUE, DARK, 12.8)
    add_card(slide, 6.85, 3.60, 5.75, 1.7, "统计", "IQR 在极窄分布上会误删正常轮\n小样本检验功效不足", LIGHT_ORANGE, ORANGE, 12.8)
    add_textbox(slide, 0.7, 5.75, 11.9, 0.5, "应对：扩样、多点复测、补 FP/LCP 指标、启用 QUIC 做对照", 15, True, DARK)
    add_note(
        slide,
        "局限分四类：样本，25 站、每站 3 到 5 轮，受控每组 IQR 后只有 3 到 5 个；环境，单机单点、固定接入、禁 QUIC 冷缓存，"
        "没覆盖移动网络和 HTTP/3；数据质量，amazon/yahoo 拦截页、microsoft 单轮、TLS 使首飞成为下界；统计，IQR 在极窄分布上会误删正常轮，"
        "小样本功效不足。应对是扩样、多点复测、补 FP/LCP、启用 QUIC 做对照。",
    )

    # 15 结论
    slide = prs.slides.add_slide(blank)
    add_header(slide, "结论与建议", "事实 → 相关 → 因果 → 建议", 15)
    add_bullets(
        slide,
        0.7,
        1.65,
        11.9,
        4.0,
        [
            "Q1 事实：25 站 initcwnd 中位数 3.78 MSS，范围 2.29～5.15，普遍低于 RFC 6928 的 10 MSS",
            "Q2 相关：与 TTFB、load 均弱负相关且不显著，只能作相关性描述",
            "Q3 因果：控制 RTT 与页面后，2→10 降 18.2%、2→20 降 35.9%，效应量大但校正后不显著",
            "建议：大对象、短连接站点可把 initcwnd 调到不低于 10 MSS，20 作为候选；小范围灰度并复测",
            "不建议仅凭 25 站相关性结果对生产服务器做激进变更",
        ],
        15.5,
    )
    add_textbox(slide, 0.7, 6.10, 11.9, 0.6, "谢谢，欢迎提问", 24, True, DARK)
    add_note(
        slide,
        "最后收口三句话：第一，25 站 initcwnd 中位数 3.78 MSS，普遍低于 RFC 6928 的 10；第二，真实站点与 TTFB、load "
        "只是弱负相关且不显著，只能作相关性描述；第三，受控实验中 2→10 降 18.2%、2→20 降 35.9%，方向明确、效应量大，"
        "但校正后不显著。建议大对象、短连接站点可以把 initcwnd 调到不低于 10 MSS、20 作为候选，小范围灰度复测；"
        "不建议仅凭 25 站相关性结果对生产服务器做激进变更。谢谢，欢迎提问。",
    )

    prs.core_properties.title = "服务器初始拥塞窗口与网站加载性能测量"
    prs.core_properties.subject = "计算机网络技术课程项目答辩"
    prs.core_properties.author = "A"
    return prs


def main() -> int:
    prs = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUTPUT)
    print(f"wrote {OUTPUT} ({len(prs.slides)} slides)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
