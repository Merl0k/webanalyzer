"""PDF export via ReportLab."""

from __future__ import annotations

import html
import os
from datetime import datetime
from io import BytesIO
from urllib.parse import urlparse

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _register_fonts() -> tuple[str, str]:
    """
    Register fonts with Cyrillic support.
    Dockerfile installs fonts-dejavu-core, so these files should exist.
    """
    regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    if os.path.exists(regular):
        pdfmetrics.registerFont(TTFont("DejaVuSans", regular))
        base_font = "DejaVuSans"
    else:
        base_font = "Helvetica"

    if os.path.exists(bold):
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold))
        bold_font = "DejaVuSans-Bold"
    else:
        bold_font = "Helvetica-Bold"

    return base_font, bold_font


def _safe_text(value) -> str:
    if value is None:
        return ""

    return html.escape(str(value))


def _percent(value) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except Exception:
        return "0%"


def _domain_from_source(source: dict) -> str:
    domain = source.get("domain")

    if domain:
        return str(domain)

    url = source.get("url") or ""

    try:
        return urlparse(url).netloc
    except Exception:
        return ""


def generate_pdf(row: dict) -> bytes:
    """
    Generate a PDF report for one analysis result.

    This implementation uses ReportLab instead of WeasyPrint to avoid
    native rendering-library issues in Docker.
    """
    base_font, bold_font = _register_fonts()

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=f"analysis_{row.get('id', '')}",
        author="WebAnalyzer v3",
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="TitleCustom",
            parent=styles["Title"],
            fontName=bold_font,
            fontSize=18,
            leading=23,
            textColor=colors.HexColor("#111827"),
            alignment=TA_LEFT,
            spaceAfter=8,
        )
    )

    styles.add(
        ParagraphStyle(
            name="MetaCustom",
            parent=styles["Normal"],
            fontName=base_font,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#6B7280"),
            spaceAfter=10,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionTitleCustom",
            parent=styles["Heading2"],
            fontName=bold_font,
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#2563EB"),
            spaceBefore=10,
            spaceAfter=6,
        )
    )

    styles.add(
        ParagraphStyle(
            name="BodyCustom",
            parent=styles["BodyText"],
            fontName=base_font,
            fontSize=10,
            leading=15,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=6,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SmallCustom",
            parent=styles["BodyText"],
            fontName=base_font,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#4B5563"),
        )
    )

    story = []

    query = _safe_text(row.get("query", "Без назви"))
    story.append(Paragraph("web.analyzer · v3", styles["SmallCustom"]))
    story.append(Paragraph(query, styles["TitleCustom"]))

    meta = (
        f"{_safe_text(row.get('created_at', ''))} · "
        f"{_safe_text(row.get('depth', 'standard'))} · "
        f"{_safe_text(row.get('lang', 'auto'))} · "
        f"{_safe_text(row.get('sources_cnt', 0))} джерел"
    )

    story.append(Paragraph(meta, styles["MetaCustom"]))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#E5E7EB")))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Резюме", styles["SectionTitleCustom"]))
    story.append(Paragraph(_safe_text(row.get("summary", "")), styles["BodyCustom"]))

    sentiment = row.get("sentiment") or {}
    overall = _safe_text(row.get("overall", sentiment.get("overall", "neutral")))

    story.append(Paragraph("Тональність", styles["SectionTitleCustom"]))

    sent_data = [
        ["Загальна", overall],
        ["Позитивна", _percent(sentiment.get("positive", 0))],
        ["Негативна", _percent(sentiment.get("negative", 0))],
        ["Нейтральна", _percent(sentiment.get("neutral", 0))],
    ]

    sent_table = Table(sent_data, colWidths=[42 * mm, 110 * mm])
    sent_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), base_font),
                ("FONTNAME", (0, 0), (0, -1), bold_font),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#374151")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    story.append(sent_table)

    if sentiment.get("explanation"):
        story.append(Spacer(1, 6))
        story.append(Paragraph(_safe_text(sentiment.get("explanation")), styles["BodyCustom"]))

    facts = row.get("key_facts") or []

    if facts:
        story.append(Paragraph("Ключові факти", styles["SectionTitleCustom"]))

        items = [
            ListItem(
                Paragraph(_safe_text(fact), styles["BodyCustom"]),
                leftIndent=12,
            )
            for fact in facts
        ]

        story.append(
            ListFlowable(
                items,
                bulletType="1",
                start="1",
                leftIndent=16,
            )
        )

    sources = row.get("sources") or []

    if sources:
        story.append(Paragraph("Джерела", styles["SectionTitleCustom"]))

        table_data = [["Домен", "Назва / URL"]]

        for source in sources:
            domain = _safe_text(_domain_from_source(source))
            title = _safe_text(source.get("title") or source.get("url") or "Джерело")
            url = _safe_text(source.get("url", ""))

            table_data.append(
                [
                    Paragraph(domain, styles["SmallCustom"]),
                    Paragraph(f"{title}<br/><font color='#2563EB'>{url}</font>", styles["SmallCustom"]),
                ]
            )

        src_table = Table(table_data, colWidths=[42 * mm, 110 * mm], repeatRows=1)
        src_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), base_font),
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF6FF")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )

        story.append(src_table)

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB")))
    story.append(
        Paragraph(
            f"Згенеровано WebAnalyzer v3 · {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            styles["SmallCustom"],
        )
    )

    doc.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    return pdf