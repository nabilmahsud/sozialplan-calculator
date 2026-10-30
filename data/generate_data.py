"""Generate the fictional employee list and the legacy Excel model.

Run from the project root:

    python data/generate_data.py

Writes:
  data/employees.xlsx                 employee list the dashboard loads
  data/legacy_sozialplan_model.xlsx   the "grown Excel model" with live formulas

The legacy model is what the web app replaces. tests/test_excel_parity.py
reads the values Excel (or LibreOffice) calculated and checks that the Python
engine gives exactly the same result for every employee. After running this
script, open and save the legacy model once in Excel or run

    soffice --headless --convert-to xlsx --outdir data/recalc data/legacy_sozialplan_model.xlsx

so the formula results are cached in the file (see README).
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

SEED = 20261030
COUNT = 64
HERE = Path(__file__).resolve().parent

FIRST = ["Anna", "Lukas", "Mia", "Leon", "Emma", "Finn", "Sofia", "Jonas", "Hannah", "Elias", "Lea",
         "Paul", "Marie", "Felix", "Laura", "Noah", "Julia", "Ben", "Sarah", "Tim", "Aylin", "Mehmet",
         "Katarzyna", "Piotr", "Elena", "Luca", "Fatima", "Ahmed", "Ingrid", "Klaus", "Petra", "Jürgen"]
LAST = ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker", "Schulz",
        "Hoffmann", "Koch", "Richter", "Klein", "Wolf", "Neumann", "Schwarz", "Zimmermann", "Braun",
        "Krüger", "Hofmann", "Hartmann", "Lange", "Yilmaz", "Kowalski", "Rossi", "Nowak", "Werner"]
DEPARTMENTS = {  # name: (salary range EUR/month, weight)
    "Warehouse": ((2700, 3600), 6),
    "Transport": ((2900, 3900), 4),
    "Customer Service": ((3000, 4100), 3),
    "Administration": ((3400, 5200), 2),
    "IT": ((4500, 7200), 1),
    "Sales": ((3800, 6500), 2),
}
LOCATIONS = ["Frankfurt am Main", "Offenbach", "Hanau"]
CUTOFF = date(2026, 12, 31)

COLUMNS = ["ID", "First name", "Last name", "Department", "Location", "Birth date", "Entry date",
           "Monthly gross (EUR)", "Children", "Severely disabled"]


def make_employees(rng: random.Random) -> list[list]:
    depts = [d for d, (_, w) in DEPARTMENTS.items() for _ in range(w)]
    rows = []
    for i in range(COUNT):
        dept = rng.choice(depts)
        lo, hi = DEPARTMENTS[dept][0]
        birth = date(rng.randint(1961, 2002), rng.randint(1, 12), rng.randint(1, 28))
        earliest_entry = date(birth.year + 18, birth.month, birth.day)
        span = (date(2025, 6, 30) - max(earliest_entry, date(1985, 1, 1))).days
        entry = max(earliest_entry, date(1985, 1, 1)) + timedelta(days=rng.randint(0, max(span, 1)))
        tenure_bonus = min(CUTOFF.year - entry.year, 30) * rng.uniform(15, 30)
        salary = round(rng.uniform(lo, hi) + tenure_bonus, 2)
        children = rng.choices([0, 1, 2, 3, 4], weights=[40, 22, 25, 9, 4])[0]
        disabled = "yes" if rng.random() < 0.08 else "no"
        rows.append([f"P{1001 + i}", rng.choice(FIRST), rng.choice(LAST), dept, rng.choice(LOCATIONS),
                     birth, entry, salary, children, disabled])
    return rows


def _style_header(ws, ncols: int) -> None:
    fill = PatternFill("solid", fgColor="1F2A44")
    for c in range(1, ncols + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions[get_column_letter(c)].width = 16
    ws.freeze_panes = "A2"


def write_employees(rows: list[list]) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Employees"
    ws.append(COLUMNS)
    for r in rows:
        ws.append(r)
    for row in ws.iter_rows(min_row=2):
        row[5].number_format = row[6].number_format = "DD.MM.YYYY"
        row[7].number_format = "#,##0.00"
    _style_header(ws, len(COLUMNS))
    path = HERE / "employees.xlsx"
    wb.save(path)
    return path


def write_legacy_model(rows: list[list]) -> Path:
    wb = Workbook()
    p = wb.active
    p.title = "Parameters"
    params = [("Parameter", "Value"), ("Divisor", 100), ("Child bonus (EUR)", 2500),
              ("Severe disability bonus (EUR)", 5000), ("Minimum (EUR)", 3000),
              ("Maximum (EUR)", 100000), ("Cut-off date", CUTOFF)]
    for r in params:
        p.append(r)
    p["B7"].number_format = "DD.MM.YYYY"
    _style_header(p, 2)
    p.column_dimensions["A"].width = 32

    ws = wb.create_sheet("Calculation")
    ws.append(COLUMNS + ["Age", "Years of service", "Base", "Child bonus", "Disability bonus",
                         "Subtotal", "Severance"])
    for i, r in enumerate(rows, start=2):
        ws.append(r + [
            f'=DATEDIF(F{i},Parameters!$B$7,"y")',
            f'=DATEDIF(G{i},Parameters!$B$7,"y")',
            f"=ROUND(K{i}*L{i}*H{i}/Parameters!$B$2,2)",
            f"=ROUND(I{i}*Parameters!$B$3,2)",
            f'=IF(J{i}="yes",Parameters!$B$4,0)',
            f"=ROUND(M{i}+N{i}+O{i},2)",
            f"=MIN(MAX(P{i},Parameters!$B$5),Parameters!$B$6)",
        ])
        ws[f"F{i}"].number_format = ws[f"G{i}"].number_format = "DD.MM.YYYY"
        for col in "HMNOPQ":
            ws[f"{col}{i}"].number_format = "#,##0.00"
    _style_header(ws, 17)
    path = HERE / "legacy_sozialplan_model.xlsx"
    wb.save(path)
    return path


if __name__ == "__main__":
    data = make_employees(random.Random(SEED))
    print("wrote", write_employees(data))
    print("wrote", write_legacy_model(data))
