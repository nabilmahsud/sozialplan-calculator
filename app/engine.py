"""Severance calculation engine for a German Sozialplan.

Formula (one common Sozialplan model):

    base      = age x years_of_service x monthly_gross / divisor
    bonuses   = children x child_bonus + (disability_bonus if severely disabled)
    severance = clamp(base + bonuses, minimum, maximum)

Age and years of service are completed years at the cut-off date, the same
as Excel's DATEDIF(start, cutoff, "y"). Money is rounded to cents at each
step, the same way the legacy Excel model does it, so both give identical
results.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from statistics import median


@dataclass(frozen=True)
class Params:
    divisor: float = 100.0
    child_bonus: float = 2500.0
    disability_bonus: float = 5000.0
    minimum: float = 3000.0
    maximum: float = 100000.0
    cutoff: date = date(2026, 12, 31)

    def __post_init__(self) -> None:
        if self.divisor <= 0:
            raise ValueError("divisor must be greater than 0")
        if self.minimum < 0 or self.maximum < 0:
            raise ValueError("minimum and maximum must not be negative")
        if self.minimum > self.maximum:
            raise ValueError("minimum must not be greater than maximum")


@dataclass(frozen=True)
class Employee:
    id: str
    first_name: str
    last_name: str
    department: str
    location: str
    birth_date: date
    entry_date: date
    monthly_gross: float
    children: int = 0
    severely_disabled: bool = False

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass(frozen=True)
class Result:
    employee_id: str
    age: int
    years_of_service: int
    base: float
    child_amount: float
    disability_amount: float
    uncapped: float
    severance: float
    limit_applied: str | None  # "minimum", "maximum" or None
    explanation_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def completed_years(start: date, end: date) -> int:
    """Whole years between two dates, like Excel DATEDIF(start, end, "y")."""
    if end < start:
        return 0
    years = end.year - start.year
    if (end.month, end.day) < (start.month, start.day):
        years -= 1
    return years


def _money(value: float) -> float:
    """Round to cents, half away from zero, like Excel ROUND(x, 2).

    Python's round() rounds half to even, which differs from Excel on
    values such as 0.125, so we go through Decimal.
    """
    return float(Decimal(repr(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) + 0.0


def calculate(employee: Employee, params: Params) -> Result:
    age = completed_years(employee.birth_date, params.cutoff)
    tenure = completed_years(employee.entry_date, params.cutoff)

    base = _money(age * tenure * employee.monthly_gross / params.divisor)
    child_amount = _money(employee.children * params.child_bonus)
    disability_amount = _money(params.disability_bonus if employee.severely_disabled else 0.0)
    uncapped = _money(base + child_amount + disability_amount)

    limit_applied = None
    severance = uncapped
    if uncapped > params.maximum:
        severance, limit_applied = _money(params.maximum), "maximum"
    elif uncapped < params.minimum:
        severance, limit_applied = _money(params.minimum), "minimum"

    steps = [
        f"Base amount: {age} years of age x {tenure} years of service x "
        f"{employee.monthly_gross:,.2f} EUR / {params.divisor:g} = {base:,.2f} EUR",
    ]
    if child_amount:
        steps.append(f"Child bonus: {employee.children} x {params.child_bonus:,.2f} EUR = {child_amount:,.2f} EUR")
    if disability_amount:
        steps.append(f"Severe disability bonus: {disability_amount:,.2f} EUR")
    if limit_applied == "maximum":
        steps.append(f"Capped at the maximum of {params.maximum:,.2f} EUR")
    elif limit_applied == "minimum":
        steps.append(f"Raised to the minimum of {params.minimum:,.2f} EUR")
    steps.append(f"Severance: {severance:,.2f} EUR")

    return Result(
        employee_id=employee.id,
        age=age,
        years_of_service=tenure,
        base=base,
        child_amount=child_amount,
        disability_amount=disability_amount,
        uncapped=uncapped,
        severance=severance,
        limit_applied=limit_applied,
        explanation_steps=steps,
    )


def summarize(employees: list[Employee], results: list[Result]) -> dict:
    """Totals and breakdowns for the dashboard."""
    if not results:
        return {"count": 0, "total": 0.0, "average": 0.0, "median": 0.0,
                "at_maximum": 0, "at_minimum": 0, "by_department": [], "histogram": []}

    amounts = [r.severance for r in results]
    by_dept: dict[str, dict] = {}
    for emp, res in zip(employees, results):
        d = by_dept.setdefault(emp.department, {"department": emp.department, "count": 0, "total": 0.0})
        d["count"] += 1
        d["total"] = _money(d["total"] + res.severance)

    edges = [0, 10_000, 25_000, 50_000, 75_000, 100_000, 125_000, float("inf")]
    labels = ["< 10k", "10-25k", "25-50k", "50-75k", "75-100k", "100-125k", "125k+"]
    histogram = [{"label": lab, "count": 0} for lab in labels]
    for a in amounts:
        for i in range(len(labels)):
            if edges[i] <= a < edges[i + 1]:
                histogram[i]["count"] += 1
                break

    return {
        "count": len(results),
        "total": _money(sum(amounts)),
        "average": _money(sum(amounts) / len(amounts)),
        "median": _money(median(amounts)),
        "at_maximum": sum(1 for r in results if r.limit_applied == "maximum"),
        "at_minimum": sum(1 for r in results if r.limit_applied == "minimum"),
        "by_department": sorted(by_dept.values(), key=lambda d: d["total"], reverse=True),
        "histogram": histogram,
    }
