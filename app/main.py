"""FastAPI app: JSON API plus the static dashboard.

The API is stateless. The browser holds the employee list and sends it with
every request, so nothing about the employees is stored on the server.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import engine, excel_io, pdf

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_FILE = ROOT / "data" / "employees.xlsx"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

log = logging.getLogger("sozialplan")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Sozialplan Calculator", version="0.1.0")


class ParamsIn(BaseModel):
    divisor: float = Field(100, gt=0, le=1000)
    child_bonus: float = Field(2500, ge=0)
    disability_bonus: float = Field(5000, ge=0)
    minimum: float = Field(3000, ge=0)
    maximum: float = Field(100000, ge=0)
    cutoff: date = date(2026, 12, 31)

    def to_engine(self) -> engine.Params:
        try:
            return engine.Params(**self.model_dump())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc


class EmployeeIn(BaseModel):
    id: str
    first_name: str
    last_name: str
    department: str = "Unassigned"
    location: str = ""
    birth_date: date
    entry_date: date
    monthly_gross: float = Field(ge=0)
    children: int = Field(0, ge=0)
    severely_disabled: bool = False

    @field_validator("entry_date")
    @classmethod
    def entry_after_birth(cls, v: date, info):
        birth = info.data.get("birth_date")
        if birth and v < birth:
            raise ValueError("entry_date is before birth_date")
        return v

    def to_engine(self) -> engine.Employee:
        return engine.Employee(**self.model_dump())


class CalcRequest(BaseModel):
    employees: list[EmployeeIn]
    params: ParamsIn = ParamsIn()


class SingleRequest(BaseModel):
    employee: EmployeeIn
    params: ParamsIn = ParamsIn()


def _employee_json(e: engine.Employee) -> dict:
    return {**e.__dict__, "birth_date": e.birth_date.isoformat(), "entry_date": e.entry_date.isoformat()}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.get("/api/sample")
def sample() -> dict:
    employees = excel_io.read_employees(SAMPLE_FILE.read_bytes())
    return {"source": SAMPLE_FILE.name, "client": "Sample data", "employees": [_employee_json(e) for e in employees]}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 5 MB")
    try:
        employees = excel_io.read_employees(data)
    except excel_io.ExcelFormatError as exc:
        raise HTTPException(422, str(exc)) from exc
    # Log counts only, never names or salaries.
    log.info("upload accepted: %d employees", len(employees))
    return {"source": file.filename, "client": file.filename, "employees": [_employee_json(e) for e in employees]}


@app.post("/api/calculate")
def calculate(req: CalcRequest) -> dict:
    params = req.params.to_engine()
    employees = [e.to_engine() for e in req.employees]
    results = [engine.calculate(e, params) for e in employees]
    return {"results": [r.to_dict() for r in results], "summary": engine.summarize(employees, results)}


@app.post("/api/pdf")
def employee_pdf(req: SingleRequest) -> Response:
    params, emp = req.params.to_engine(), req.employee.to_engine()
    body = pdf.employee_pdf(emp, engine.calculate(emp, params), params)
    return Response(body, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="severance_{emp.id}.pdf"'})


@app.post("/api/pdf/all")
def all_pdfs(req: CalcRequest) -> Response:
    params = req.params.to_engine()
    items = [(e, engine.calculate(e, params)) for e in (x.to_engine() for x in req.employees)]
    body = pdf.all_pdfs_zip(items, params)
    log.info("generated %d PDFs", len(items))
    return Response(body, media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="severance_statements.zip"'})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
