"""
PDF export (spec §8.3, "shareable report") — renders a `FusedReport` to a
PDF using `reportlab` (pure-Python, no system dependencies beyond pip,
unlike wkhtmltopdf/weasyprint which need a native renderer installed).
"""

from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.scoring.fusion import FusedReport

_STYLES = getSampleStyleSheet()
_TITLE = ParagraphStyle("PoiseTitle", parent=_STYLES["Title"], textColor=colors.HexColor("#111827"))
_H2 = ParagraphStyle("PoiseH2", parent=_STYLES["Heading2"], textColor=colors.HexColor("#4C1D95"), spaceBefore=16)
_BODY = ParagraphStyle("PoiseBody", parent=_STYLES["BodyText"], leading=15)
_MUTED = ParagraphStyle("PoiseMuted", parent=_STYLES["BodyText"], textColor=colors.HexColor("#6B7280"), fontSize=9)


def render_report_pdf(report: FusedReport) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )
    story = []

    title = "IELTS Speaking Report" if report.mode == "ielts" else "Interview Practice Report"
    story.append(Paragraph(title, _TITLE))
    subtitle_bits = [f"Session {report.session_id[:8]}", f"{report.duration_minutes:.0f} min"]
    if report.jd_title:
        subtitle_bits.append(report.jd_title)
    story.append(Paragraph(" · ".join(subtitle_bits), _MUTED))
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph(f"Overall Score: {report.overall_score:.0f}/100", _H2))

    dim_rows = [["Dimension", "Score", "Weight"]]
    for d in report.dimensions:
        score_display = "N/A" if not d.available else f"{d.score:.0f}/100"
        dim_rows.append([d.name, score_display, f"{d.weight * 100:.0f}%"])
    dim_table = Table(dim_rows, colWidths=[3 * inch, 1.5 * inch, 1.5 * inch])
    dim_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDE9FE")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#4C1D95")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
            ]
        )
    )
    story.append(dim_table)
    story.append(Spacer(1, 0.25 * inch))

    if report.strengths:
        story.append(Paragraph("Strengths", _H2))
        for s in report.strengths:
            story.append(Paragraph(f"• {s}", _BODY))

    if report.improvements:
        story.append(Paragraph("Areas to Improve", _H2))
        for s in report.improvements:
            story.append(Paragraph(f"• {s}", _BODY))

    if report.action_items:
        story.append(Paragraph("Recommended Next Steps", _H2))
        for item in report.action_items:
            story.append(
                Paragraph(
                    f"<b>[{item.priority.upper()}]</b> {item.description} — <i>{item.suggested_practice}</i>",
                    _BODY,
                )
            )

    if report.per_question_breakdown:
        story.append(Paragraph("Per-Question Breakdown", _H2))
        for i, qb in enumerate(report.per_question_breakdown, start=1):
            story.append(Paragraph(f"<b>Q{i}.</b> {qb.question}", _BODY))
            story.append(Paragraph(f"Score: {qb.score:.0f}/100", _MUTED))
            story.append(Spacer(1, 0.08 * inch))

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(f"Generated {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')} by Poise", _MUTED))

    doc.build(story)
    return buf.getvalue()
