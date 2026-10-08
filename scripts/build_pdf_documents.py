"""Build the proposal and SRS as polished, illustrated PDF documents."""
from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf"
OUTPUT.mkdir(parents=True, exist_ok=True)
FONT_PATH = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
if not FONT_PATH.exists():
    FONT_PATH = Path("/Library/Fonts/Arial Unicode.ttf")
pdfmetrics.registerFont(TTFont("ProjectChinese", str(FONT_PATH)))

PAGE_W, PAGE_H = A4
INK = colors.HexColor("#28231f")
BROWN = colors.HexColor("#8b513a")
LIGHT_BROWN = colors.HexColor("#efe3d8")
PAPER = colors.HexColor("#fbf8f3")
LINE = colors.HexColor("#d8c9bc")
GREEN = colors.HexColor("#dcece4")
FONT = "ProjectChinese"


def clean_text(value: str) -> str:
    return value.replace("\u2011", "-").replace("\u2012", "-").replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")


def inline_markup(value: str) -> str:
    value = html.escape(clean_text(value), quote=False)
    value = re.sub(r"\[([^]]+)]\((https?://[^)]+)\)", r'<a href="\2" color="#6f3f2e"><u>\1</u></a>', value)
    value = re.sub(r"`([^`]+)`", r'<font name="Courier" size="8">\1</font>', value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    return value


styles = getSampleStyleSheet()
body = ParagraphStyle("BodyZH", fontName=FONT, fontSize=9.6, leading=16, textColor=INK,
                      alignment=TA_JUSTIFY, spaceAfter=6, wordWrap="CJK")
h1 = ParagraphStyle("Heading1", parent=body, fontSize=19, leading=25, textColor=BROWN,
                    spaceBefore=10, spaceAfter=9, keepWithNext=True)
h2 = ParagraphStyle("Heading2", parent=body, fontSize=14.5, leading=20, textColor=INK,
                    spaceBefore=9, spaceAfter=6, keepWithNext=True)
h3 = ParagraphStyle("Heading3", parent=body, fontSize=11.5, leading=17, textColor=BROWN,
                    spaceBefore=7, spaceAfter=4, keepWithNext=True)
bullet = ParagraphStyle("BulletZH", parent=body, leftIndent=12, firstLineIndent=-8, bulletIndent=2)
caption = ParagraphStyle("CaptionZH", parent=body, fontSize=8.5, leading=13, textColor=colors.HexColor("#60554d"), alignment=TA_LEFT, spaceBefore=4, spaceAfter=10)
small = ParagraphStyle("SmallZH", parent=body, fontSize=8.2, leading=12, textColor=colors.HexColor("#655b54"))
cover_title = ParagraphStyle("CoverTitle", parent=body, fontSize=28, leading=38, textColor=INK, alignment=TA_CENTER, spaceAfter=12)
cover_subtitle = ParagraphStyle("CoverSubtitle", parent=body, fontSize=14, leading=22, textColor=BROWN, alignment=TA_CENTER, spaceAfter=25)
cover_meta = ParagraphStyle("CoverMeta", parent=body, fontSize=10, leading=18, alignment=TA_CENTER, textColor=colors.HexColor("#645a52"))
code_style = ParagraphStyle("CodeZH", parent=body, fontName="Courier", fontSize=7.5, leading=11,
                            leftIndent=8, rightIndent=8, backColor=colors.HexColor("#f2eee9"), borderPadding=7)


class ProjectDoc(BaseDocTemplate):
    def __init__(self, filename: str, document_title: str):
        super().__init__(filename, pagesize=A4, leftMargin=19*mm, rightMargin=19*mm,
                         topMargin=19*mm, bottomMargin=18*mm, title=document_title,
                         author="AI Prompt Studio 專題小組")
        self.document_title = document_title
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="body")
        self.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=self.decorate))

    def decorate(self, canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(colors.HexColor("#776b62"))
        if doc.page > 1:
            canvas.drawString(self.leftMargin, PAGE_H - 10*mm, self.document_title[:36])
            canvas.setStrokeColor(LINE)
            canvas.line(self.leftMargin, PAGE_H - 12*mm, PAGE_W - self.rightMargin, PAGE_H - 12*mm)
        canvas.drawRightString(PAGE_W - self.rightMargin, 9*mm, f"第 {doc.page} 頁")
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in {"Heading1", "Heading2"}:
            level = 0 if flowable.style.name == "Heading1" else 1
            plain = re.sub(r"<[^>]+>", "", flowable.getPlainText())
            self.notify("TOCEntry", (level, plain, self.page))


def table_from_lines(lines: list[str], width: float):
    rows = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        rows.append([Paragraph(inline_markup(cell), small) for cell in cells])
    if not rows:
        return Spacer(1, 1)
    cols = len(rows[0])
    table = Table(rows, colWidths=[width / cols] * cols, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BROWN),
        ("TEXTCOLOR", (0, 0), (-1, 0), INK),
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PAPER]),
    ]))
    return table


def image_flow(path: Path, alt: str, max_width: float):
    img = Image(str(path))
    ratio = min(max_width / img.imageWidth, 105*mm / img.imageHeight)
    img.drawWidth = img.imageWidth * ratio
    img.drawHeight = img.imageHeight * ratio
    img.hAlign = "CENTER"
    return img


def parse_markdown(source: Path, usable_width: float):
    lines = source.read_text(encoding="utf-8").splitlines()
    # Cover information is rendered separately; begin the body at the first chapter.
    first_chapter = next((i for i, line in enumerate(lines) if line.startswith("## ")), 0)
    lines = lines[first_chapter:]
    story = []
    index = 0
    while index < len(lines):
        raw = lines[index].rstrip()
        stripped = raw.strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("```"):
            code = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            story.append(Paragraph(html.escape(clean_text("\n".join(code))).replace("\n", "<br/>"), code_style))
            continue
        image_match = re.fullmatch(r"!\[([^]]*)]\(([^)]+)\)", stripped)
        if image_match:
            img_path = (source.parent / image_match.group(2)).resolve()
            story.append(Spacer(1, 3*mm))
            story.append(image_flow(img_path, image_match.group(1), usable_width))
            index += 1
            continue
        if stripped.startswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index])
                index += 1
            story.extend([table_from_lines(table_lines, usable_width), Spacer(1, 3*mm)])
            continue
        heading = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading:
            level = len(heading.group(1))
            style = {1: h1, 2: h2, 3: h3}[level]
            story.append(Paragraph(inline_markup(heading.group(2)), style))
            index += 1
            continue
        if re.match(r"^[-*]\s+", stripped):
            item = re.sub(r"^[-*]\s+", "", stripped)
            story.append(Paragraph(inline_markup(item), bullet, bulletText="•"))
            index += 1
            continue
        numbered = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if numbered:
            story.append(Paragraph(inline_markup(numbered.group(2)), bullet, bulletText=f"{numbered.group(1)}."))
            index += 1
            continue
        paragraph_lines = [stripped]
        index += 1
        while index < len(lines):
            next_line = lines[index].strip()
            if not next_line or re.match(r"^(#{1,3})\s+", next_line) or next_line.startswith("|") or next_line.startswith("```") or re.match(r"^[-*]\s+", next_line) or re.match(r"^\d+\.\s+", next_line) or re.fullmatch(r"!\[[^]]*]\([^)]+\)", next_line):
                break
            paragraph_lines.append(next_line)
            index += 1
        text = " ".join(paragraph_lines)
        style = caption if re.match(r"^圖\s*(?:S-)?\d+", text) else body
        story.append(Paragraph(inline_markup(text), style))
    return story


def create_pdf(source_name: str, output_name: str, title: str, subtitle: str, meta: str):
    target = OUTPUT / output_name
    doc = ProjectDoc(str(target), title)
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("TOC1", fontName=FONT, fontSize=10.5, leading=18, leftIndent=0, textColor=INK),
        ParagraphStyle("TOC2", fontName=FONT, fontSize=9, leading=15, leftIndent=14, textColor=colors.HexColor("#655b54")),
    ]
    cover = [Spacer(1, 38*mm), Paragraph(title, cover_title), Paragraph(subtitle, cover_subtitle),
             Spacer(1, 8*mm), Paragraph(meta + "<br/><br/>學生：____________　系級：____________<br/>指導老師：____________", cover_meta), Spacer(1, 24*mm),
             Table([[Paragraph("專題文件", cover_meta), Paragraph("2026-10-08", cover_meta)]],
                   colWidths=[55*mm, 55*mm], style=TableStyle([
                       ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BROWN), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                       ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 10),
                       ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                   ])), PageBreak(), Paragraph("目錄", h1), toc, PageBreak()]
    body_story = parse_markdown(ROOT / "docs" / source_name, doc.width)
    doc.multiBuild(cover + body_story)
    return target


if __name__ == "__main__":
    outputs = [
        create_pdf("專題企劃書.md", "AI提示詞視覺化管理App_完整企劃書.pdf",
                   "AI 提示詞視覺化管理 App",
                   "精簡企劃書｜本機提示詞管理、專案記憶與 Token 輸入負擔",
                   "版本 V1.4｜含操作介面、研究方法、時程、風險與評估設計"),
        create_pdf("SPEC.md", "AI提示詞視覺化管理App_軟體需求規格書.pdf",
                   "AI Prompt Studio",
                   "軟體需求與技術規格書（SRS）",
                   "版本 V1.4｜含介面規格、功能需求、資料結構、API、安全與驗收"),
    ]
    for output in outputs:
        print(output)
