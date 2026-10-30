"""Read employee lists from Excel (.xlsx)."""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

from openpyxl import load_workbook

from .engine import Employee

# Header text in the sheet -> Employee field. Matching ignores case and spaces,
# and accepts the German headers that HR exports usually have.
HEADER_ALIASES = {
    "id": "id", "personalnummer": "id", "personnelno": "id",
    "firstname": "first_name", "vorname": "first_name",
    "lastname": "last_name", "nachname": "last_name",
    "department": "department", "abteilung": "department",
    "location": "location", "standort": "location",
    "birthdate": "birth_date", "geburtsdatum": "birth_date",
    "entrydate": "entry_date", "eintrittsdatum": "entry_date",
    "monthlygross": "monthly_gross", "monthlygrosseur": "monthly_gross", "monthlygrosssalary": "monthly_gross",
    "monthlygrosssalaryeur": "monthly_gross", "bruttomonatsgehalt": "monthly_gross",
    "children": "children", "kinder": "children",
    "severelydisabled": "severely_disabled", "schwerbehindert": "severely_disabled",
}

REQUIRED = {"id", "first_name", "last_name", "birth_date", "entry_date", "monthly_gross"}


class ExcelFormatError(ValueError):
    pass


def _norm(header: object) -> str:
    return "".join(ch for ch in str(header or "").lower() if ch.isalnum())


def _to_date(value: object, row: int, col: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                pass
    raise ExcelFormatError(f"Row {row}: '{col}' is not a valid date ({value!r})")


def _to_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "ja", "x", "y"}


def read_employees(data: bytes) -> list[Employee]:
    try:
        wb = load_workbook(BytesIO(data), data_only=True, read_only=True)
    except Exception as exc:  # openpyxl raises several types for bad files
        raise ExcelFormatError("The file is not a readable .xlsx workbook") from exc

    ws = wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    try:
        header = next(rows)
    except StopIteration:
        raise ExcelFormatError("The sheet is empty") from None

    columns = {i: HEADER_ALIASES[_norm(h)] for i, h in enumerate(header) if _norm(h) in HEADER_ALIASES}
    missing = REQUIRED - set(columns.values())
    if missing:
        raise ExcelFormatError("Missing columns: " + ", ".join(sorted(missing)))

    employees = []
    for row_no, row in enumerate(rows, start=2):
        if row is None or all(v is None for v in row):
            continue
        rec = {field: row[i] for i, field in columns.items() if i < len(row)}
        try:
            employees.append(Employee(
                id=str(rec["id"]),
                first_name=str(rec.get("first_name") or ""),
                last_name=str(rec.get("last_name") or ""),
                department=str(rec.get("department") or "Unassigned"),
                location=str(rec.get("location") or ""),
                birth_date=_to_date(rec["birth_date"], row_no, "birth_date"),
                entry_date=_to_date(rec["entry_date"], row_no, "entry_date"),
                monthly_gross=float(rec["monthly_gross"]),
                children=int(rec.get("children") or 0),
                severely_disabled=_to_bool(rec.get("severely_disabled")),
            ))
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ExcelFormatError):
                raise
            raise ExcelFormatError(f"Row {row_no}: {exc}") from exc

    if not employees:
        raise ExcelFormatError("No employee rows found")
    return employees
