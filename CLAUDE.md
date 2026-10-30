# CLAUDE.md

Guidance for coding agents working in this repo.

## What this is
A web app that replaces a grown Excel model for Sozialplan severance payments.
Python (FastAPI) backend, plain HTML/CSS/JS dashboard, no build step.

## Commands
- Install: `pip install -r requirements.txt`
- Run: `uvicorn app.main:app --reload` then open http://localhost:8000
- Test: `python -m pytest -q`
- Regenerate fake data: `python data/generate_data.py`, then recalc the legacy model (see README)

## Layout
- `app/engine.py`: the only place where money is calculated. Pure functions, no I/O.
- `app/excel_io.py`: reads employee lists; accepts English and German headers.
- `app/pdf.py`: one-page statement per employee, zip for all.
- `app/main.py`: stateless JSON API + static files.
- `static/`: dashboard. All numbers come from `/api/calculate`; never recompute money in JS.
- `data/legacy_sozialplan_model.xlsx`: the reference model with live formulas.

## Rules
1. **The Excel model is the spec.** Any change to the formula must keep
   `tests/test_excel_parity.py` green, or change the Excel model in the same commit.
2. Money is rounded half away from zero to cents (`engine._money`), same as Excel `ROUND`.
3. **Client data.** Never log names, salaries or dates. Employee data never leaves the
   machine: no external APIs. Do not commit real employee files. Only `data/employees.xlsx` (fictional) is allowed.
4. The API stays stateless. Do not add a database or server-side storage of employees.
5. Keep the UI dependency-free (no CDN scripts): the app must work on an offline laptop.
6. Run the tests before you say a change is done.

## Splitting work across agents
The modules have clean boundaries, so parallel work rarely collides:
engine + tests / API / PDF / dashboard. The engine owner reviews any change that
touches money. If an agent changes a number in a test to make it pass, reject it.
