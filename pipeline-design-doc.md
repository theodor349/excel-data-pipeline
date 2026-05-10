# Data Pipeline — Prototype Design Document

## Overview

This document describes the architecture of a Python-based data pipeline that replaces an Excel/Power Query workflow. It is written for a **developer implementing the framework**. The end user of the finished project is a non-technical person who will author and maintain queries with the assistance of an AI coding agent.

The first customer is a finance department of a medium-sized company that uses Excel + Power Query heavily to produce annual reports and similar deliverables. Design choices throughout this document are biased toward that use case (decimal precision for currency, date handling, robust handover to Power BI).

The system ingests data from Excel files and SQL databases, applies transformations defined as composable queries, runs validation tests, and exports results as Excel files for consumption by Power BI.

---

## Goals

- Replace a slow, opaque Excel/Power Query pipeline with a readable, version-controlled Python project
- Give a non-technical user (with AI agent assistance) the ability to create and maintain queries without touching the framework
- Make every query self-documenting, testable, and composable
- Run locally on Windows via Power Automate, with a clear path to Azure later

---

## Non-Goals

- This is not a general-purpose ETL platform
- The framework does not write to any SQL database — read access only
- No web UI or dashboard — output is Excel files consumed by Power BI

---

## Project Structure

```
pipeline/
│
├── run.py                  # Entry point — runs all queries or a specific one
│
├── engine/                 # FRAMEWORK — implemented by developer, not touched by user
│   ├── loader.py           # Functions for reading Excel, CSV and SQL sources
│   ├── exporter.py         # Functions for writing output Excel files
│   ├── runner.py           # Discovers and executes queries, handles errors
│   ├── tester.py           # Loads and runs fixture-based tests per query
│   ├── validator.py        # expect_columns / expect_non_empty helpers
│   └── logger.py           # Writes structured logs throughout execution
│
├── functions/              # SHARED FUNCTIONS — extended by user + agent over time
│   ├── aggregations.py     # avg(), sum(), count(), etc.
│   ├── transforms.py       # lowercase(), to_decimal(), to_date(), rename(), etc.
│   ├── joins.py            # merge(), append()
│   └── tests/              # pytest tests for the shared functions
│       ├── test_aggregations.py
│       ├── test_transforms.py
│       └── test_joins.py
│
└── queries/                # QUERIES — authored and maintained by user + agent
    ├── sales_by_region/
    │   ├── query.py        # The query definition (load + run)
    │   ├── test.py         # Fixture wiring (FIXTURES + EXPECTED dicts)
    │   └── testData/
    │       ├── sales.csv                     # Fixture for one source
    │       ├── regions.csv                   # Fixture for another source
    │       └── expected_sales_by_region.csv  # Expected output sheet
    └── monthly_summary/
        ├── query.py
        ├── test.py
        └── testData/
            ├── transactions.csv
            ├── expected_revenue.csv
            └── expected_units.csv
```

---

## Framework Layer (`engine/`)

The framework is implemented once by a developer. The user never needs to open or edit these files.

### `loader.py`

Provides three functions the user calls in their queries to load source data.

```python
read_excel(source_name: str, sheet_or_table: str) -> DataFrame
read_csv(source_name: str) -> DataFrame
read_sql(connection_name: str, query: str) -> DataFrame
```

- `read_excel` and `read_csv` take a *named source* (looked up under `excel_sources` / `csv_sources` in `config.json`), not a file path — the user never types absolute paths in queries
- `read_excel` reads a specific sheet (or named table) from the Excel file
- `read_sql` looks up a named connection from `config.json` and executes a read-only SQL query — it does not create, write, or alter any data
- SQL connections are named (e.g. `"sales_db"`) so the user never handles connection strings directly
- `read_csv` is also used internally by `tester.py` to load fixture files

### `exporter.py`

Writes output DataFrames to Excel files. Supports multiple sheets in a single output file.

```python
export(sheets: dict[str, DataFrame], output_folder: str, filename: str) -> None
```

- `sheets` is a dictionary mapping sheet name to DataFrame
- Creates the output folder if it does not exist
- Writes to a temporary file in the same folder, then atomically renames over the target. This avoids partial writes and works around the common case where Power BI is holding the previous file open — the temp write succeeds and the rename fails loudly with a clear "file in use" error rather than producing a corrupt half-written xlsx
- `Decimal` columns are written using Excel's currency/number format so Power BI sees them as numeric, not text

### `runner.py`

Discovers all queries in the `queries/` directory and executes them.

- Auto-discovers query folders by scanning `queries/` for subfolders containing a `query.py` file
- Each `query.py` must expose `load()` and `run(data)` (see Query Layer). The runner calls `load()` to fetch source DataFrames, then `run(data)` to produce the output dict of sheet name → DataFrame
- Calls `exporter.py` with the result of each `run(data)`
- If a query raises an exception, logs the full traceback and continues to the next query — one bad query does not abort the batch
- Writes a `summary.json` to the output folder with per-query status (`ok` / `failed` / reason). Power Automate / Power BI tooling can read this to detect partial-failure runs
- Exits with a non-zero status code if **any** query failed, so the surrounding scheduler can alert on it
- Accepts an optional query name to run a single query instead of all
- Production runs do **not** execute fixture tests — tests run only when invoked with `--test-only` (see Testing Strategy)

### `tester.py`

Runs fixture-based tests for a given query. Only invoked when the user passes `--test-only` to `run.py` (production / scheduled runs skip it entirely).

- Reads the query's `test.py`, which exposes two dicts: `FIXTURES` (source name → fixture file path) and `EXPECTED` (sheet name → expected output file path)
- Loads each fixture file (CSV or XLSX) into a DataFrame and assembles the same `data` dict shape that `load()` would have returned
- Calls the query's `run(data)` directly with that dict — the real `load()` is bypassed, so no Excel files or SQL connections are touched during tests
- Compares each output sheet against its expected file: row count, column names, dtypes, and value-by-value (with a small tolerance for `Decimal`/float)
- Reports all mismatches in a single readable block; does **not** export
- Returns non-zero exit status if any test fails, so CI / pre-commit can gate on it

### `logger.py`

Writes structured logs to a timestamped file in a dedicated `logs/` subfolder of the output folder. Each run creates a new file so history is preserved and runs do not overwrite each other. Logs live in their own subfolder so the output folder Power BI watches stays clean (only `.xlsx` and `summary.json`).

```
output/
├── sales_by_region.xlsx
├── monthly_summary.xlsx
├── summary.json
└── logs/
    ├── pipeline-2026-05-12-1200-56.log
    ├── pipeline-2026-05-13-0800-01.log
    └── ...
```

- Filename format: `pipeline-YYYY-MM-DD-HHMM-SS.log`
- Logs query start, query success, query failure (with full traceback), and (when `--test-only` is used) test results
- Log format is readable by both humans and AI agents for debugging
- Does not attempt to produce plain-English error summaries — raw tracebacks are preserved

---

## Shared Functions Layer (`functions/`)

These are standalone functions that operate on DataFrames. They are the vocabulary the user uses to write queries. The developer seeds this layer with common functions; the user and AI agent extend it over time.

Each file in `functions/` has a corresponding test file under `functions/tests/` that verifies each function's behavior with small, inline DataFrames. These tests are run with `pytest` and must pass before the pipeline is handed over to the user.

```
functions/
├── aggregations.py
├── transforms.py
├── joins.py
└── tests/
    ├── test_aggregations.py
    ├── test_transforms.py
    └── test_joins.py
```

### Design rules for functions

- Every function takes a DataFrame as its first argument and returns a DataFrame
- Functions are pure — they do not modify the input, they return a new DataFrame
- Functions are small and do one thing
- Function signatures should be readable out loud: `lowercase(df, "name")` reads as "lowercase the name column"
- Money columns are `Decimal` end-to-end (see `to_decimal` below). All aggregations preserve `Decimal` dtype — they never silently widen to float. This is mandatory for the finance use case: float arithmetic accumulates rounding errors over large sums and breaks reconciliations against source-of-truth ledgers.

> **Note to developer — Decimal end-to-end is load-bearing.** Pandas defaults to float for numeric operations; preserving `Decimal` through `groupby().sum()`, `merge()`, `read_excel`, etc. requires `dtype="object"` columns and deliberate handling at every step. This is the single highest-risk implementation detail in the framework — a silent widen-to-float anywhere in the pipeline will produce reports that look right but quietly disagree with the customer's ledgers. The starter `pytest` tests under `functions/tests/` **must** include precision regression tests, e.g. *"1000 rows of `Decimal('0.10')` summed equals exactly `Decimal('100.00')`"*, plus equivalent checks for `avg`, `merge`-then-`sum`, and the round-trip through `exporter.py` → `read_excel`. Treat any test that passes only with float tolerance as a bug.

### `aggregations.py` — starter set

```python
avg(df, group_by: str | list, column: str) -> DataFrame
sum(df, group_by: str | list, column: str) -> DataFrame
count(df, group_by: str | list) -> DataFrame
min(df, group_by: str | list, column: str) -> DataFrame
max(df, group_by: str | list, column: str) -> DataFrame
```

- All aggregations accept `Decimal` columns and return `Decimal` results
- `avg` over a `Decimal` column rounds to the column's existing precision (use `to_decimal(..., places=N)` to control it)

### `transforms.py` — starter set

```python
lowercase(df, column: str) -> DataFrame
to_int(df, column: str) -> DataFrame
to_decimal(df, column: str, places: int = 2) -> DataFrame   # use this for money
to_float(df, column: str) -> DataFrame                       # only for non-money numerics
to_date(df, column: str, format: str | None = None) -> DataFrame
fiscal_year(df, date_column: str, fy_start_month: int = 1, new_column: str = "fiscal_year") -> DataFrame
period_end(df, date_column: str, granularity: str, new_column: str = "period_end") -> DataFrame  # "month" | "quarter" | "year"
rename(df, old_name: str, new_name: str) -> DataFrame
keep_columns(df, columns: list) -> DataFrame                 # equivalent to Power Query "Choose Columns"
filter_rows(df, column: str, value) -> DataFrame
drop_nulls(df, column: str) -> DataFrame
```

- `to_decimal` is the default for any monetary column. `to_float` exists for measurements/ratios where binary precision is acceptable
- `to_date` accepts an optional `format` string; if omitted, uses pandas' permissive parser
- `fiscal_year` defaults to a calendar year (Jan start). For a customer with a non-calendar fiscal year, set `fy_start_month` (e.g. `7` for a July-start FY)

### `joins.py` — starter set

```python
merge(left: DataFrame, right: DataFrame, on: str | list | None = None,
      left_on: str | list | None = None, right_on: str | list | None = None,
      how: str = "left") -> DataFrame
append(top: DataFrame, bottom: DataFrame) -> DataFrame
```

- `how` must be explicit when not `"left"`: `"left"`, `"inner"`, `"outer"`, `"right"`
- Either `on` (same column on both sides) or both `left_on` and `right_on` must be provided
- `append` requires both DataFrames to have the same columns; raises a clear error listing missing/extra columns on either side
- Joins are also the v1 mechanism for parameterising a query: put parameters (e.g. `fiscal_year=2025`) in a small CSV or Excel "parameter" source and `merge` against it. This avoids adding a CLI parameter system to the framework for now.

---

## Query Layer (`queries/`)

This is the part of the project the user owns. Each query lives in its own folder.

### Query file (`query.py`)

Each query file exposes two functions: `load()` returns a named dict of source DataFrames; `run(data)` transforms that dict and returns an output dict of sheet name → DataFrame. This separation lets the test runner substitute fixture data for real sources without modifying the query logic.

**Example:**

```python
from engine.loader import read_excel, read_sql
from functions.transforms import lowercase, to_decimal, rename
from functions.aggregations import avg
from functions.joins import merge

def load():
    return {
        "sales":   read_excel("sales", "Sheet1"),
        "regions": read_sql("sales_db", "SELECT id, name FROM regions"),
    }

def run(data):
    sales   = data["sales"]
    regions = data["regions"]

    # Normalize
    sales   = lowercase(sales,   "customer_name")
    sales   = to_decimal(sales,  "amount", places=2)
    regions = lowercase(regions, "name")
    regions = rename(regions,    "name", "region_name")
    regions = rename(regions,    "id",   "region_id")   # align join key

    # Combine
    combined = merge(sales, regions, on="region_id", how="left")

    # Summarize
    result = avg(combined, group_by="region_name", column="amount")

    return {"Sales by Region": result}
```

**Rules for query files:**
- `load()` only loads — no transformations
- `run(data)` never calls loader functions — all data comes from the `data` dict
- Every intermediate step should be a named variable — avoid chaining on one line
- Variable names should describe what the data represents, not how it was made
- Comments above each block (`# Normalize`, `# Combine`, `# Summarize`) are encouraged

### Test file (`test.py`)

Each query has a fixture-based test. The developer sets up the test structure; the user and agent author the actual fixture data.

Fixture files can be either `.xlsx` or `.csv`. CSV is preferred for simplicity and readability in version control; use `.xlsx` only when column types cannot be preserved in CSV (e.g. multi-sheet inputs the user wants to keep grouped).

Because queries often load from multiple sources, `query.py` is split into `load()` and `run(data)` (see the example above). The test runner bypasses `load()` entirely, builds the `data` dict from the fixture files declared in `test.py`, and calls `run(data)` directly.

```python
# test.py — this structure is always the same, generated by the agent
FIXTURES = {
    "sales":   "testData/sales.csv",
    "regions": "testData/regions.csv",
}
EXPECTED = {
    "Sales by Region": "testData/expected_sales_by_region.csv",
}
```

The user's job is to fill in the fixture files with a small representative sample (e.g. 10–20 rows) and the expected output for that sample.

**Workflow for authoring a test (user + agent):**
1. User describes what the query should do in plain language
2. Agent creates small CSV fixture files with representative data for each input source
3. **User** computes what the expected output should be — by hand, in Excel, or against a known-good prior run. This is critical for a finance customer: if the agent both writes the query and computes the expected output, the test only proves the query agrees with itself
4. Agent encodes the user's expected values into the expected CSV file(s)
5. User runs the test and confirms the result matches

---

## Configuration

A single `config.json` file at the project root holds environment-specific settings. The user never edits query files when credentials change — only this file.

```json
{
  "connections": {
    "sales_db": {
      "type": "mssql",
      "host": "server-name",
      "database": "SalesDB",
      "username": "readonly_user",
      "password": "..."
    }
  },
  "excel_sources": {
    "sales": "C:/data/sales.xlsx",
    "products": "C:/data/products.xlsx"
  },
  "csv_sources": {
    "fx_rates": "C:/data/fx_rates.csv"
  }
}
```

- SQL passwords are stored here — the file **must** be in `.gitignore` and the developer should ship a `config.example.json` (with placeholder values) as the committed reference
- Excel and CSV source paths are named so queries reference them by name, not by path
- Known limitation for v1: passwords are plaintext on the workstation. For a finance department this is acceptable only if the workstation itself is locked down. A future revision should switch to Windows Credential Manager or `Trusted_Connection=yes` for SQL Server with AD auth — both are drop-in replacements that don't require touching any query.

---

## Entry Point (`run.py`)

```bash
# Run all queries
python run.py --all --output C:/reports/output

# Run a single query
python run.py --query sales_by_region --output C:/reports/output

# Run tests for all queries (no export, no SQL/Excel I/O)
python run.py --all --test-only

# Run a single query's test
python run.py --query sales_by_region --test-only
```

- Exactly one of `--all` or `--query <name>` is required
- `--output` is required for non-test runs and ignored for `--test-only`
- Power Automate calls `python run.py --all --output <folder>` on a schedule
- During development, the user runs individual queries via the agent in a terminal
- Output folder is created if it does not exist
- A timestamped log file is written to `<output>/logs/` on every run (see `logger.py`)
- Exit code is `0` if every query (or every test) passed, non-zero otherwise — the surrounding scheduler can use this to alert

---

## Error Handling

- Query failures do not stop other queries from running
- The full Python traceback is written to the run's log file under `<output>/logs/`
- A summary line is printed to stdout for each query: `[OK] sales_by_region` or `[FAILED] sales_by_region — see logs/pipeline-...log`
- A `summary.json` is written to the output folder with `{query_name: "ok" | "failed", reason?: "..."}`. Power Automate / monitoring can read this without parsing logs
- `run.py` exits non-zero if any query failed, so the scheduler can alert
- Tests are not run during production exports (see Testing Strategy). Test failures only surface under `--test-only`
- The AI agent is the primary consumer of error logs, so no plain-English wrapping is applied

---

## Testing Strategy

Three levels of validation per query:

| Level | What it checks | When it runs |
|---|---|---|
| Input validation | Source data has expected columns and is not empty | At the start of every `run(data)`, in production and in tests |
| Step validation | Intermediate DataFrames have expected shape after key transforms | Inline in `run(data)`, optional |
| End-to-end test | Full output matches fixture expected output | **Only** via `--test-only` (not part of scheduled production runs) |

Input validation is handled by a helper the framework provides. It runs against the `data` dict at the top of `run(data)`, so it catches both real-source and fixture-source problems:

```python
from engine.validator import expect_columns, expect_non_empty

def run(data):
    sales = data["sales"]
    expect_non_empty(sales, "sales")
    expect_columns(sales, ["customer_name", "amount", "region_id"])
    ...
```

If validation fails, the query raises an error immediately with a clear message about what was missing.

End-to-end tests are deliberately **not** run before each scheduled export. Production runs would otherwise read fixture CSVs, re-execute every query against fixture data, and emit pass/fail noise on every cron tick. Tests gate the *change* (developer or agent edits a query → runs `--test-only`), not the *run*.

---

## Output Format

Each query's `run(data)` returns a dict of sheet name → DataFrame. The runner passes this to `exporter.py`, which writes an Excel file named after the query folder.

```
output/
├── sales_by_region.xlsx      # Contains sheet "Sales by Region"
├── monthly_summary.xlsx      # Contains sheets "Revenue", "Units"
├── summary.json              # Per-query status for monitoring
└── logs/
    └── pipeline-2026-05-12-1200-56.log
```

Power BI connects to the output folder and refreshes from these Excel files. Logs and `summary.json` live alongside but are ignored by Power BI's folder connector (it filters on `.xlsx`).

If Power BI has a file open when the pipeline tries to overwrite it, the atomic temp-file-then-rename pattern (see `exporter.py`) will fail loudly rather than producing a corrupt half-written workbook. The failure is logged and recorded in `summary.json` so the user can close Power BI and re-run.

---

## Future Considerations

- **Azure migration**: `runner.py` and `run.py` are designed to be called from any scheduler. Moving to Azure Functions or Azure Container Apps requires no changes to queries or functions — only the trigger mechanism changes.
- **Additional connectors**: `loader.py` can be extended with `read_sharepoint()`, etc. without affecting existing queries.
- **Parallelism**: Queries are currently run sequentially. If volume grows, `runner.py` can be updated to run queries in parallel. This will require a dependency declaration per query (e.g. a `DEPENDS_ON = ["other_query"]` constant in `query.py`) so that the runner can build a dependency tree and schedule queries only after their upstream outputs are available.
- **Power Automate**: The local Power Automate client runs `python run.py --all --output <folder>` as a shell command on a schedule. No other integration is required.
- **Query parameters**: v1 deliberately has no CLI parameter system. If the user needs per-run parameters (fiscal year, currency, scenario), they put them in a small CSV/Excel "parameter" source and `merge` against it inside the query. If a future need outgrows that pattern, add `run.py --param key=value` and a `params: dict` argument to `run(data, params)` — neither change touches existing queries.
- **Credential storage**: v1 stores SQL passwords in plaintext in `config.json` (gitignored). A future revision should adopt Windows integrated auth (`Trusted_Connection=yes`) or Windows Credential Manager. `read_sql` is the only function affected.
- **Incremental loads**: Annual-report queries may eventually scan large historical tables. If full re-reads become slow, add a per-query `since` cursor stored in `output/state.json` and pass it to the SQL query — no change to `load()`/`run(data)` shape required.

---

## Developer Checklist

Before handing over to the user, the developer should complete:

- [ ] Implement `engine/loader.py` with `read_excel`, `read_csv`, and `read_sql` (all using *named sources* from `config.json`, never raw paths)
- [ ] Implement `engine/exporter.py` with atomic temp-file-then-rename writes and Decimal-aware number formatting
- [ ] Implement `engine/runner.py` with auto-discovery, per-query error isolation, `summary.json` output, and non-zero exit code on any failure
- [ ] Implement `engine/tester.py` — reads `FIXTURES`/`EXPECTED` from each query's `test.py`, bypasses `load()`, calls `run(data)`, compares with Decimal-aware tolerance
- [ ] Implement `engine/logger.py` — timestamped logs in `<output>/logs/`
- [ ] Implement `engine/validator.py` with `expect_columns` and `expect_non_empty`
- [ ] Seed `functions/` with the starter aggregations, transforms (including `to_decimal`, `to_date`, `fiscal_year`, `period_end`), and joins (`merge` with `on` / `left_on` / `right_on`)
- [ ] Write `pytest` tests for all seeded functions under `functions/tests/`, including Decimal-precision tests for sums/averages
- [ ] Create a committed `config.example.json` and document that the real `config.json` is gitignored
- [ ] Create one example query end-to-end (`queries/example/`) demonstrating: named sources, parameter table via join, Decimal money, fiscal-year transform, and a passing fixture test
- [ ] Verify `python run.py --all --output <folder>` and `python run.py --query example --test-only` both work and exit with the right status codes
- [ ] Verify `exporter.py` fails cleanly when the target xlsx is open in Power BI (manual smoke test on Windows)
- [ ] Add `config.json` and `output/` to `.gitignore`
- [ ] Write a short `QUERIES.md` guide for the user explaining how to create a new query with agent help, including the "user computes expected values, agent encodes them" rule
