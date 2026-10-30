# Sozialplan Calculator

Turns a grown Excel model for Sozialplan severance payments into a web app that a
lawyer can use: upload the employee list, move the factor, see the total cost
change instantly, and download a PDF statement for every employee.

All employee data in this repo is fictional.

## What it does
- **Dashboard**: total severance volume, average, median, number of people at the cap
  or minimum, volume by department, distribution of payments, searchable employee table.
- **Parameters**: divisor (factor), child bonus, severe disability bonus, minimum,
  maximum, cut-off date. Every change recalculates all employees immediately.
- **Scenarios**: save the current settings as a baseline, change the factor, and see the
  difference in EUR and percent.
- **Excel upload**: any `.xlsx` with the columns ID, first name, last name, birth date,
  entry date, monthly gross (German headers such as *Geburtsdatum* work too).
- **PDFs**: one-page statement per employee, or all of them as a zip.
- **Breakdown**: click an employee to see the calculation step by step.
- **Offline**: no external services. Employee data never leaves the machine.

## The formula

    severance = age × years of service × monthly gross ÷ divisor
              + children × child bonus
              + disability bonus (if severely disabled)
    then limited to [minimum, maximum]

Age and years of service are completed years at the cut-off date, like Excel
`DATEDIF(…, "y")`. Amounts are rounded to cents half away from zero, like Excel `ROUND`.

## Tested against the Excel model
`data/legacy_sozialplan_model.xlsx` is the "grown Excel model": the same 64 employees
with live formulas. `tests/test_excel_parity.py` reads the values Excel calculated and
checks, cent by cent, that the Python engine gives the same age, years, base, bonuses
and final amount for every employee. If someone changes the formula in one place only,
CI goes red.

## Run it

    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload

Open http://localhost:8000. Works with Python 3.9 or newer.

Run the tests with `python -m pytest -q`.

### Regenerating the fake data

    python data/generate_data.py
    soffice --headless --calc --convert-to xlsx --outdir /tmp/recalc data/legacy_sozialplan_model.xlsx
    cp /tmp/recalc/legacy_sozialplan_model.xlsx data/

The second step lets LibreOffice calculate the formulas and store the results in the
file (opening and saving it in Excel does the same).

## Engineering notes
- **Stateless API.** The browser holds the employee list; the server keeps nothing.
- **Logs** contain counts only, never names or salaries.
- **Releases.** Every release is a git tag (`v0.1.0`, …). Rolling back means deploying
  the previous tag; there is no database to migrate.
- **CI** runs the full test suite on every push (`.github/workflows/ci.yml`).
- **Agent setup.** `CLAUDE.md` holds the rules agents follow in this repo, and
  `.claude/settings.json` runs the tests after every file edit, so an agent sees a
  broken calculation immediately.

## Project layout
    app/engine.py      calculation (pure functions)
    app/excel_io.py    Excel import
    app/pdf.py         PDF statements
    app/main.py        FastAPI routes
    static/            dashboard (HTML, CSS, JS, no dependencies)
    data/              fictional data + legacy Excel model + generator
    tests/             engine, API and Excel parity tests
