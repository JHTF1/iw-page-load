"""把 docs/报告_终稿_合并稿.md 排成符合 GB/T 7713.1 的 DOCX。

用法：python scripts/build_report.py
输出：docs/报告_终稿_初始拥塞窗口与网页加载性能.docx
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "报告_终稿_合并稿.md"
OUTPUT = ROOT / "docs" / "报告_终稿_初始拥塞窗口与网页加载性能.docx"

BODY_FONT = "宋体"
HEADING_FONT = "黑体"
LATIN_FONT = "Times New Roman"
CODE_FONT = "Consolas"

TABLE_WIDTHS = {
    4: [3.0, 2.1, 3.0, 7.4],
    6: [3.0, 2.6, 2.6, 2.6, 2.6, 2.1],
    7: [5.0, 2.6, 1.8, 1.6, 1.9, 1.6, 1.0],
    8: [2.1, 2.1, 1.4, 2.3, 2.2, 2.2, 1.6, 1.6],
}


def set_run_font(run, name: str, size: float, bold: bool | None = None) -> None:
    run.font.name = LATIN_FONT if name == BODY_FONT else name
    run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    r_pr = run._element.get_or_add_rPr()
    r_fonts = r_pr.find(qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.append(r_fonts)
    r_fonts.set(qn("w:eastAsia"), name)
    r_fonts.set(qn("w:ascii"), LATIN_FONT if name == BODY_FONT else name)
    r_fonts.set(qn("w:hAnsi"), LATIN_FONT if name == BODY_FONT else name)


def add_inline(p, text: str, size: float = 12, font: str = BODY_FONT) -> None:
    token = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\[\d+\])")
    position = 0
    for match in token.finditer(text):
        if match.start() > position:
            run = p.add_run(text[position:match.start()])
            set_run_font(run, font, size)
        value = match.group(0)
        if value.startswith("**"):
            inner = value[2:-2]
            for part in re.split(r"(`[^`]+`)", inner):
                if not part:
                    continue
                if part.startswith("`") and part.endswith("`"):
                    run = p.add_run(part[1:-1])
                    set_run_font(run, CODE_FONT, size - 1, bold=True)
                else:
                    run = p.add_run(part)
                    set_run_font(run, font, size, bold=True)
        elif value.startswith("`"):
            run = p.add_run(value[1:-1])
            set_run_font(run, CODE_FONT, size - 1.0)
        else:
            run = p.add_run(value)
            set_run_font(run, font, size)
            run.font.superscript = True
        position = match.end()
    if position < len(text):
        run = p.add_run(text[position:])
        set_run_font(run, font, size)


def format_body(p, size: float = 12, indent: bool = True) -> None:
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    if indent:
        p.paragraph_format.first_line_indent = Pt(size * 2)
    else:
        p.paragraph_format.first_line_indent = None


def add_page_break(doc: Document) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run()
    run.add_break(6)


def add_heading(doc: Document, text: str, level: int, page_break: bool = False) -> None:
    p = doc.add_paragraph()
    p.style = doc.styles["Heading 1" if level == 1 else "Heading 2"]
    if page_break:
        p.paragraph_format.page_break_before = True
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(12 if level == 1 else 10)
    p.paragraph_format.space_after = Pt(10 if level == 1 else 6)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    set_run_font(run, HEADING_FONT, 16 if level == 1 else 14, bold=True)
    run.font.color.rgb = RGBColor(0, 0, 0)


def shade_paragraph(p, fill: str = "F2F2F2") -> None:
    p_pr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    p_pr.append(shd)


def add_code_block(doc: Document, lines: list[str]) -> None:
    text = "\n".join(lines)
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.6)
    p.paragraph_format.right_indent = Cm(0.6)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.first_line_indent = None
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    if text.strip().startswith("W0 ="):
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text.strip())
        set_run_font(run, "Cambria Math", 12)
        return
    shade_paragraph(p)
    for index, line in enumerate(lines):
        run = p.add_run(line)
        set_run_font(run, CODE_FONT, 9.5)
        if index < len(lines) - 1:
            run.add_break()


def add_figure(doc: Document, path: Path, caption: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.first_line_indent = None
    p.paragraph_format.keep_with_next = True
    with Image.open(path) as image:
        width_px, height_px = image.size
    max_width = Cm(14.5)
    max_height = Cm(19.5)
    width = max_width
    height = int(width * height_px / width_px)
    if height > max_height:
        height = max_height
        width = int(height * width_px / height_px)
    run = p.add_run()
    run.add_picture(str(path), width=width, height=height)

    caption_p = doc.add_paragraph()
    caption_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption_p.paragraph_format.space_before = Pt(0)
    caption_p.paragraph_format.space_after = Pt(8)
    caption_p.paragraph_format.first_line_indent = None
    add_inline(caption_p, caption, size=10.5)


def set_table_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge, size in (("top", "12"), ("bottom", "12")):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "000000")
        borders.append(element)
    for edge in ("left", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "none")
        element.set(qn("w:sz"), "0")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "auto")
        borders.append(element)
    tbl_pr.append(borders)

    margins = OxmlElement("w:tblCellMar")
    for side, width in (("top", "20"), ("left", "70"), ("bottom", "20"), ("right", "70")):
        element = OxmlElement(f"w:{side}")
        element.set(qn("w:w"), width)
        element.set(qn("w:type"), "dxa")
        margins.append(element)
    tbl_pr.append(margins)

    for cell in table.rows[0].cells:
        tc_pr = cell._tc.get_or_add_tcPr()
        tc_borders = OxmlElement("w:tcBorders")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "0")
        bottom.set(qn("w:color"), "000000")
        tc_borders.append(bottom)
        tc_pr.append(tc_borders)


def add_table(doc: Document, caption: str | None, rows: list[list[str]]) -> None:
    if caption:
        caption_p = doc.add_paragraph()
        caption_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption_p.paragraph_format.space_before = Pt(8)
        caption_p.paragraph_format.space_after = Pt(3)
        caption_p.paragraph_format.first_line_indent = None
        caption_p.paragraph_format.keep_with_next = True
        add_inline(caption_p, caption, size=10.5)

    n_cols = len(rows[0])
    table = doc.add_table(rows=len(rows), cols=n_cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.allow_autofit = False
    set_table_borders(table)

    widths = TABLE_WIDTHS.get(n_cols, [15.5 / n_cols] * n_cols)
    for row_idx, row in enumerate(rows):
        tr_pr = table.rows[row_idx]._tr.get_or_add_trPr()
        cant_split = OxmlElement("w:cantSplit")
        tr_pr.append(cant_split)
        if row_idx == 0:
            header = OxmlElement("w:tblHeader")
            tr_pr.append(header)
        for col_idx, value in enumerate(row):
            cell = table.cell(row_idx, col_idx)
            cell.width = Cm(widths[col_idx])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if col_idx == 0 else WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.first_line_indent = None
            add_inline(p, value, size=9)
            if row_idx == 0:
                for run in p.runs:
                    run.font.bold = True


def add_bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.left_indent = Cm(0.74)
    p.paragraph_format.first_line_indent = Cm(-0.37)
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    add_inline(p, "• " + text, size=12)


def add_quote(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.74)
    p.paragraph_format.first_line_indent = None
    p.paragraph_format.line_spacing = 1.3
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(3)
    add_inline(p, text, size=10.5)
    for run in p.runs:
        run.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
        run.font.italic = True


def is_table_separator(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and set(stripped) <= set("|-: ")


def parse_table(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        if is_table_separator(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows.append(cells)
    return rows


def add_markdown(doc: Document, markdown: str) -> None:
    lines = markdown.splitlines()
    index = 0
    first_h1 = True
    while index < len(lines):
        raw = lines[index]
        line = raw.strip()
        if not line:
            index += 1
            continue
        if line == "---":
            index += 1
            continue
        if line.startswith("```"):
            index += 1
            block: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                block.append(lines[index].rstrip())
                index += 1
            index += 1
            add_code_block(doc, block)
            continue
        if line.startswith("# "):
            title = line[2:].strip()
            add_heading(doc, title, 1, page_break=True)
            first_h1 = False
            index += 1
            continue
        if line.startswith("## "):
            add_heading(doc, line[3:].strip(), 2)
            index += 1
            continue
        if line.startswith("### "):
            add_heading(doc, line[4:].strip(), 2)
            index += 1
            continue
        if line.startswith("!["):
            match = re.match(r"!\[(.+?)\]\((.+?)\)", line)
            if match:
                caption, path_text = match.group(1), match.group(2)
                path = Path(path_text)
                if not path.is_absolute():
                    path = ROOT / path
                if path.exists():
                    add_figure(doc, path, caption)
                else:
                    p = doc.add_paragraph()
                    add_inline(p, f"[缺图：{path_text}]", size=10.5)
            index += 1
            continue
        if line.startswith("|"):
            table_lines: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            add_table(doc, None, parse_table(table_lines))
            continue
        if line.startswith("- "):
            add_bullet(doc, line[2:].strip())
            index += 1
            continue
        if line.startswith("> "):
            add_quote(doc, line[2:].strip())
            index += 1
            continue
        if line.startswith("表 "):
            lookahead = index + 1
            while lookahead < len(lines) and not lines[lookahead].strip():
                lookahead += 1
            if lookahead < len(lines) and lines[lookahead].strip().startswith("|"):
                table_lines = []
                index = lookahead
                while index < len(lines) and lines[index].strip().startswith("|"):
                    table_lines.append(lines[index].strip())
                    index += 1
                add_table(doc, line, parse_table(table_lines))
                continue
        p = doc.add_paragraph()
        format_body(p)
        add_inline(p, line, size=12)
        index += 1


def set_east_asian_style(style, font_name: str, size: float, bold: bool = False) -> None:
    style.font.name = font_name
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = RGBColor(0, 0, 0)
    r_pr = style.element.get_or_add_rPr()
    r_fonts = r_pr.find(qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.append(r_fonts)
    r_fonts.set(qn("w:eastAsia"), font_name)
    r_fonts.set(qn("w:ascii"), font_name)
    r_fonts.set(qn("w:hAnsi"), font_name)


def add_field(paragraph, instruction: str, placeholder: str = "") -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    run._r.append(begin)

    run = paragraph.add_run()
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    run._r.append(instr)

    run = paragraph.add_run()
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    run._r.append(separate)

    if placeholder:
        paragraph.add_run(placeholder)

    run = paragraph.add_run()
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(end)


def add_header_footer(section, title: str) -> None:
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False
    header = section.header.paragraphs[0]
    header.text = ""
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = header.add_run(title)
    set_run_font(run, BODY_FONT, 9)
    run.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
    p_pr = header._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "BFBFBF")
    p_bdr.append(bottom)
    p_pr.append(p_bdr)

    footer = section.footer.paragraphs[0]
    footer.text = ""
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_field(footer, "PAGE", "1")
    for run in footer.runs:
        set_run_font(run, BODY_FONT, 9)

    sect_pr = section._sectPr
    for old in sect_pr.findall(qn("w:pgNumType")):
        sect_pr.remove(old)
    pg_num_type = OxmlElement("w:pgNumType")
    pg_num_type.set(qn("w:start"), "1")
    sect_pr.append(pg_num_type)


def add_toc_heading(doc: Document) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.page_break_before = True
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(10)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("目  录")
    set_run_font(run, HEADING_FONT, 16, bold=True)
    run.font.color.rgb = RGBColor(0, 0, 0)


def build_cover(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.5)

    for _ in range(4):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("服务器初始拥塞窗口")
    set_run_font(run, HEADING_FONT, 26, bold=True)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("与网站加载性能测量")
    set_run_font(run, HEADING_FONT, 26, bold=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(18)
    run = p.add_run("——真实站点测量与受控实验的联合分析——")
    set_run_font(run, BODY_FONT, 14)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(24)
    p_pr = p._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), "1F4E79")
    p_bdr.append(bottom)
    p_pr.append(p_bdr)

    info = [
        ("课程", "计算机网络技术"),
        ("形式", "三人小组项目报告"),
        ("撰写", "A（第 1、3 章）　B（第 2、4 章）　C（第 5、6 章与统稿）"),
        ("答辩日期", "2026 年 11 月 8 日"),
        ("文档日期", "2026 年 11 月 4 日"),
    ]
    for label, value in info:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.8
        run = p.add_run(f"{label}：")
        set_run_font(run, HEADING_FONT, 12, bold=True)
        run = p.add_run(value)
        set_run_font(run, BODY_FONT, 12)


def build_front_matter(doc: Document) -> None:
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    add_header_footer(section, "服务器初始拥塞窗口与网站加载性能测量")

    add_heading(doc, "摘  要", 1, page_break=False)
    abstract = (
        "本文测量服务器初始拥塞窗口（initcwnd）的实际配置及其对网页加载性能的影响。"
        "对 25 个真实站点进行被动抓包与冷缓存页面测量，得到 initcwnd 的分布，并用 Spearman "
        "相关分析其与 TTFB、load 的关系；在 WSL2 受控平台上固定往返时延与页面内容，把 initcwnd "
        "设为 2、4、10、20 个 MSS，各采集 5 轮，用 Mann-Whitney U 检验比较。结果表明：25 个真实"
        "站点的 initcwnd 中位数为 3.78 MSS，范围 2.29～5.15 MSS，普遍低于 RFC 6928 建议的 10 MSS；"
        "真实数据中 initcwnd 与 TTFB、load 仅呈弱负相关，统计上均不显著，只能支撑相关性结论；"
        "受控实验中 load 中位数随窗口增大而下降，initcwnd 从 2 增至 10 下降 18.2%，从 2 增至 20 "
        "下降 35.9%，但每组仅 3～5 个有效样本，Bonferroni 校正后 p 值均大于 0.05，因果效应的方向"
        "明确而强度有待扩样确认。本文据此给出分级的结论与调优建议，并说明单点测量、拦截页与小样本等局限。"
    )
    p = doc.add_paragraph()
    format_body(p)
    add_inline(p, abstract, size=12)

    p = doc.add_paragraph()
    format_body(p, indent=False)
    p.paragraph_format.space_before = Pt(8)
    run = p.add_run("关键词：")
    set_run_font(run, HEADING_FONT, 12, bold=True)
    run = p.add_run("初始拥塞窗口；慢启动；页面加载性能；网络测量；受控实验")
    set_run_font(run, BODY_FONT, 12)

    add_heading(doc, "Abstract", 1, page_break=True)
    english = (
        "This report measures the actual configuration of the server's initial congestion window "
        "(initcwnd) and its impact on web page load performance. We passively captured the first-flight "
        "bytes of 25 real websites and measured their page load performance with a cold-cache Chrome "
        "browser. Spearman correlation was used to analyze the relationship between initcwnd and TTFB/load. "
        "On a controlled WSL2 testbed with fixed RTT and page content, we varied initcwnd over 2, 4, 10, "
        "and 20 MSS, five runs per group, and compared load times with the Mann-Whitney U test. The median "
        "initcwnd of the 25 sites is 3.78 MSS (range 2.29-5.15 MSS), well below the 10 MSS recommended by "
        "RFC 6928. The real-site correlations are weakly negative but not statistically significant, so they "
        "only support a correlation statement. In the controlled experiment, the median load decreases by "
        "18.2% from 2 to 10 MSS and by 35.9% from 2 to 20 MSS, but the Bonferroni-corrected p-values remain "
        "above 0.05 because only 3-5 valid samples per group survive IQR filtering. The causal direction is "
        "clear, while the effect strength needs confirmation with a larger sample. We give graded conclusions, "
        "tuning suggestions, and limitations."
    )
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.first_line_indent = Cm(0.85)
    run = p.add_run(english)
    run.font.name = LATIN_FONT
    run.font.size = Pt(12)

    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = None
    p.paragraph_format.space_before = Pt(8)
    run = p.add_run("Keywords: ")
    run.font.name = LATIN_FONT
    run.font.size = Pt(12)
    run.font.bold = True
    run = p.add_run("initial congestion window; slow start; web page load performance; network measurement; controlled experiment")
    run.font.name = LATIN_FONT
    run.font.size = Pt(12)

    add_toc_heading(doc)
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = None
    add_field(p, 'TOC \\o "1-2" \\h \\z \\u', "右键更新域以生成目录")
    note = doc.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    note.paragraph_format.first_line_indent = None
    run = note.add_run("（在 Word 中右键目录并选择“更新域”，即可生成页码）")
    set_run_font(run, BODY_FONT, 9)
    run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)


def build_tail(doc: Document) -> None:
    add_heading(doc, "参考文献", 1, page_break=True)
    references = [
        "[1] 中华人民共和国国家质量监督检验检疫总局, 中国国家标准化管理委员会. 学位论文编写规则: GB/T 7713.1—2006[S]. 北京: 中国标准出版社, 2006.",
        "[2] 中华人民共和国国家质量监督检验检疫总局, 中国国家标准化管理委员会. 信息与文献 参考文献著录规则: GB/T 7714—2015[S]. 北京: 中国标准出版社, 2015.",
        "[3] ALLMAN M, PAXSON V, BLANTON E. TCP congestion control: RFC 5681[S]. IETF, 2009.",
        "[4] CHU J, DUKKIPATI N, CHENG Y, et al. Increasing TCP's initial window: RFC 6928[S]. IETF, 2013.",
        "[5] DUKKIPATI N, REFICE T, CHENG Y, et al. An argument for increasing TCP's initial congestion window[J]. ACM SIGCOMM Computer Communication Review, 2010, 40(3): 26-33.",
        "[6] W3C. Navigation Timing Level 2[EB/OL]. (2022-05-24)[2026-11-04]. https://www.w3.org/TR/navigation-timing-2/.",
        "[7] GOOGLE. Chrome DevTools Protocol[EB/OL]. [2026-11-04]. https://chromedevtools.github.io/devtools-protocol/.",
    ]
    for item in references:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.left_indent = Cm(0.85)
        p.paragraph_format.first_line_indent = Cm(-0.85)
        p.paragraph_format.line_spacing = 1.3
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(item)
        set_run_font(run, BODY_FONT, 10.5)

    add_heading(doc, "附录 A  复现与数据文件", 1, page_break=True)
    p = doc.add_paragraph()
    format_body(p)
    add_inline(
        p,
        "本文的分析结果可由以下命令从两份 CSV 重新生成，字段校验、IQR 剔除、统计检验与绘图均在代码中完成。",
        size=12,
    )
    add_code_block(doc, ["python -m src.analysis", "python -m pytest"])
    p = doc.add_paragraph()
    format_body(p)
    add_inline(
        p,
        "数据文件：data/processed/initcwnd.csv（29 行）、data/processed/pageload.csv（142 条）；"
        "统计表：results/tables/（merged_by_site.csv、stats_summary.csv、lab_group_summary.csv）；"
        "图表：results/figures/（PNG 与 SVG）；实验记录：docs/实验记录.md。"
        "真实站点数据只用于相关分析，因果结论只来自 lab-2、lab-4、lab-10、lab-20 四组受控实验。",
        size=12,
    )


def main() -> int:
    markdown = SOURCE.read_text(encoding="utf-8")

    doc = Document()
    styles = doc.styles
    set_east_asian_style(styles["Normal"], BODY_FONT, 12)
    for name, size in (("Heading 1", 16), ("Heading 2", 14)):
        set_east_asian_style(styles[name], HEADING_FONT, size, bold=True)
    styles["Normal"].paragraph_format.line_spacing = 1.5

    build_cover(doc)
    build_front_matter(doc)
    add_markdown(doc, markdown)
    build_tail(doc)

    # Word 打开时自动更新目录与页码
    settings = doc.settings.element
    update_fields = OxmlElement("w:updateFields")
    update_fields.set(qn("w:val"), "true")
    settings.append(update_fields)

    doc.core_properties.title = "服务器初始拥塞窗口与网站加载性能测量"
    doc.core_properties.subject = "计算机网络技术课程项目报告"
    doc.core_properties.author = "A / B / C"
    doc.core_properties.comments = "真实站点测量与受控实验的联合分析"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
