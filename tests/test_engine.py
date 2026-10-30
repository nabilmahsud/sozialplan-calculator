from datetime import date

import pytest

from app import engine

P = engine.Params()


def emp(**kw):
    base = dict(id="T1", first_name="Test", last_name="Person", department="IT", location="Frankfurt",
                birth_date=date(1976, 6, 15), entry_date=date(2006, 6, 15), monthly_gross=4000.0)
    base.update(kw)
    return engine.Employee(**base)


def test_completed_years_like_datedif():
    assert engine.completed_years(date(2000, 12, 31), date(2026, 12, 31)) == 26
    assert engine.completed_years(date(2001, 1, 1), date(2026, 12, 31)) == 25
    assert engine.completed_years(date(2000, 2, 29), date(2026, 2, 28)) == 25
    assert engine.completed_years(date(2027, 1, 1), date(2026, 12, 31)) == 0


def test_base_formula():
    r = engine.calculate(emp(), P)
    # 50 years x 20 years x 4000 / 100
    assert (r.age, r.years_of_service) == (50, 20)
    assert r.base == 40000.00
    assert r.severance == 40000.00
    assert r.limit_applied is None


def test_bonuses_are_added():
    r = engine.calculate(emp(children=2, severely_disabled=True), P)
    assert r.child_amount == 5000.00
    assert r.disability_amount == 5000.00
    assert r.severance == 50000.00


def test_maximum_cap():
    r = engine.calculate(emp(birth_date=date(1962, 1, 1), entry_date=date(1985, 1, 1), monthly_gross=9000), P)
    assert r.uncapped > P.maximum
    assert r.severance == P.maximum
    assert r.limit_applied == "maximum"


def test_minimum_floor():
    r = engine.calculate(emp(entry_date=date(2026, 1, 1)), P)
    assert r.years_of_service == 0
    assert r.severance == P.minimum
    assert r.limit_applied == "minimum"


def test_lower_divisor_raises_amount():
    low = engine.calculate(emp(), engine.Params(divisor=80))
    assert low.base == 50000.00


def test_rounding_half_up_like_excel():
    # 0.125 rounds to 0.13 in Excel; Python's round() would give 0.12
    assert engine._money(0.125) == 0.13
    assert engine._money(2.675) == 2.68


@pytest.mark.parametrize("bad", [dict(divisor=0), dict(minimum=-1), dict(minimum=10, maximum=5)])
def test_invalid_params(bad):
    with pytest.raises(ValueError):
        engine.Params(**bad)


def test_summary():
    employees = [emp(id="A"), emp(id="B", department="Sales", entry_date=date(2026, 1, 1))]
    results = [engine.calculate(e, P) for e in employees]
    s = engine.summarize(employees, results)
    assert s["count"] == 2
    assert s["total"] == 43000.00
    assert s["at_minimum"] == 1
    assert sum(h["count"] for h in s["histogram"]) == 2
