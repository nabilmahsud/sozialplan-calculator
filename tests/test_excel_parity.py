"""The web app must give exactly the same numbers as the legacy Excel model.

data/legacy_sozialplan_model.xlsx contains live formulas plus the values
Excel/LibreOffice calculated. We read those cached values and compare them,
cent by cent, with the Python engine for every employee.
"""

from datetime import datetime
from pathlib import Path

import pytest
from openpyxl import load_workbook

from app import engine

MODEL = Path(__file__).resolve().parent.parent / "data" / "legacy_sozialplan_model.xlsx"


def _d(v):
    return v.date() if isinstance(v, datetime) else v


def _load():
    wb = load_workbook(MODEL, data_only=True)
    p = wb["Parameters"]
    params = engine.Params(divisor=p["B2"].value, child_bonus=p["B3"].value,
                           disability_bonus=p["B4"].value, minimum=p["B5"].value,
                           maximum=p["B6"].value, cutoff=_d(p["B7"].value))
    rows = list(wb["Calculation"].iter_rows(min_row=2, values_only=True))
    return params, rows


PARAMS, ROWS = _load()


def test_model_has_cached_values():
    # If this fails, the workbook was saved without calculated values. See README.
    assert ROWS and all(r[16] is not None for r in ROWS)


@pytest.mark.parametrize("row", ROWS, ids=[r[0] for r in ROWS])
def test_matches_excel(row):
    emp = engine.Employee(id=row[0], first_name=row[1], last_name=row[2], department=row[3],
                          location=row[4], birth_date=_d(row[5]), entry_date=_d(row[6]),
                          monthly_gross=row[7], children=row[8], severely_disabled=row[9] == "yes")
    res = engine.calculate(emp, PARAMS)
    assert res.age == row[10]
    assert res.years_of_service == row[11]
    assert res.base == pytest.approx(row[12], abs=0.001)
    assert res.child_amount == pytest.approx(row[13], abs=0.001)
    assert res.disability_amount == pytest.approx(row[14], abs=0.001)
    assert res.uncapped == pytest.approx(row[15], abs=0.001)
    assert res.severance == pytest.approx(row[16], abs=0.001)
