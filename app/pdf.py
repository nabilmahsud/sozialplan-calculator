"""One-page PDF statement per employee."""

from __future__ import annotations

import zipfile
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .engine import Employee, Params, Result

NAVY = colors.HexColor("#1F2A44")
GREY = colors.HexColor("#6B7280")
LINE = colors.HexColor("#E5E7EB")


def _eur(value: float) -> str:
    # German number format: 12.345,67 EUR
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " EUR"


def _date(d) -> str:
    return d.strftime("%d.%m.%Y")


def employee_pdf(emp: Employee, res: Result, params: Params) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm,
                            title=f"Severance statement {emp.id}", author="Sozialplan Calculator")
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=NAVY, fontSize=17, spaceAfter=2)
    small = ParagraphStyle("small", parent=styles["Normal"], textColor=GREY, fontSize=8.5, leading=11)
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14)
    h2 = ParagraphStyle("h2", parent=styles["Heading3"], textColor=NAVY, spaceBefore=10, spaceAfter=4)

    def table(rows, widths, bold_last=False):
        t = Table(rows, colWidths=widths)
        style = [
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("TEXTCOLOR", (0, 0), (0, -1), GREY),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ]
        if bold_last:
            style += [("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                      ("TEXTCOLOR", (0, -1), (-1, -1), NAVY),
                      ("LINEABOVE", (0, -1), (-1, -1), 1, NAVY)]
        t.setStyle(TableStyle(style))
        return t

    story = [
        Paragraph("Severance statement (Sozialplan)", h1),
        Paragraph(f"Cut-off date {_date(params.cutoff)} &nbsp;|&nbsp; Personnel no. {emp.id}", small),
        Spacer(1, 8),
        Paragraph("Employee", h2),
        table([
            ["Name", emp.name],
            ["Department / location", f"{emp.department} / {emp.location}"],
            ["Date of birth", _date(emp.birth_date)],
            ["Entry date", _date(emp.entry_date)],
            ["Monthly gross salary", _eur(emp.monthly_gross)],
            ["Children", str(emp.children)],
            ["Severely disabled", "Yes" if emp.severely_disabled else "No"],
        ], [65 * mm, 101 * mm]),
        Paragraph("Calculation", h2),
    ]

    rows = [
        ["Age at cut-off", f"{res.age} years"],
        ["Years of service at cut-off", f"{res.years_of_service} years"],
        [f"Base amount ({res.age} x {res.years_of_service} x salary / {params.divisor:g})", _eur(res.base)],
    ]
    if res.child_amount:
        rows.append([f"Child bonus ({emp.children} x {_eur(params.child_bonus)})", _eur(res.child_amount)])
    if res.disability_amount:
        rows.append(["Severe disability bonus", _eur(res.disability_amount)])
    rows.append(["Subtotal", _eur(res.uncapped)])
    if res.limit_applied == "maximum":
        rows.append([f"Capped at maximum ({_eur(params.maximum)})", _eur(res.severance - res.uncapped)])
    elif res.limit_applied == "minimum":
        rows.append([f"Raised to minimum ({_eur(params.minimum)})", "+" + _eur(res.severance - res.uncapped)])
    rows.append(["Severance payment (gross)", _eur(res.severance)])
    story.append(table(rows, [120 * mm, 46 * mm], bold_last=True))

    story += [
        Paragraph("Parameters used", h2),
        Paragraph(
            f"Divisor {params.divisor:g} &nbsp;|&nbsp; Child bonus {_eur(params.child_bonus)} &nbsp;|&nbsp; "
            f"Disability bonus {_eur(params.disability_bonus)} &nbsp;|&nbsp; "
            f"Minimum {_eur(params.minimum)} &nbsp;|&nbsp; Maximum {_eur(params.maximum)}", body),
        Spacer(1, 18),
        Paragraph(
            "This statement is a model calculation for planning purposes. It is not a legal "
            "assessment and does not replace the individual review by the responsible lawyer. "
            "Gross amounts before tax and social security.", small),
    ]
    doc.build(story)
    return buf.getvalue()


def all_pdfs_zip(items: list[tuple[Employee, Result]], params: Params) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for emp, res in items:
            safe = f"{emp.id}_{emp.last_name}_{emp.first_name}".replace(" ", "_")
            zf.writestr(f"severance_{safe}.pdf", employee_pdf(emp, res, params))
    return buf.getvalue()
