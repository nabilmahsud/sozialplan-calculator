import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
SAMPLE = Path(__file__).resolve().parent.parent / "data" / "employees.xlsx"


def _sample():
    return client.get("/api/sample").json()["employees"]


def test_health_and_index():
    assert client.get("/api/health").json()["status"] == "ok"
    assert "Sozialplan" in client.get("/").text


def test_calculate_and_divisor_effect():
    employees = _sample()
    a = client.post("/api/calculate", json={"employees": employees, "params": {"divisor": 100}}).json()
    b = client.post("/api/calculate", json={"employees": employees, "params": {"divisor": 80}}).json()
    assert a["summary"]["count"] == len(employees) == len(a["results"])
    assert b["summary"]["total"] > a["summary"]["total"]


def test_invalid_params_rejected():
    r = client.post("/api/calculate", json={"employees": _sample(), "params": {"minimum": 10, "maximum": 5}})
    assert r.status_code == 422


def test_upload_roundtrip():
    with SAMPLE.open("rb") as fh:
        r = client.post("/api/upload", files={"file": ("employees.xlsx", fh)})
    assert r.status_code == 200
    assert len(r.json()["employees"]) == len(_sample())


def test_upload_rejects_garbage():
    r = client.post("/api/upload", files={"file": ("x.xlsx", b"not an excel file")})
    assert r.status_code == 422


def test_pdf_and_zip():
    employees = _sample()
    one = client.post("/api/pdf", json={"employee": employees[0]})
    assert one.status_code == 200 and one.content.startswith(b"%PDF")
    z = client.post("/api/pdf/all", json={"employees": employees[:3]})
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert len(names) == 3

