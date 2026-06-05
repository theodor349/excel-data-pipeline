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
├── exports.json            # COMMITTED — declares which queries become which output files
│
├── engine/                 # FRAMEWORK — implemented by developer, not touched by user
│   ├── loader.py           # Functions for reading Excel, CSV and SQL sources
│   ├── exporter.py         # Writes output files (xlsx + csv) from the result cache
│   ├── export_config.py    # Parses and validates exports.json
│   ├── runner.py           # Builds the query DAG, executes it, handles errors
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
    ├── region_base/        # a COMPONENT query: reused by others, not exported itself
    │   ├── query.py        # load + run; run(data) returns ONE DataFrame
    │   ├── test.py         # FIXTURES (incl. DEPENDS_ON) + single EXPECTED path
    │   └── testData/
    │       ├── sales.csv                     # Fixture for one source
    │       └── expected_region_base.csv      # The single expected output table
    └── region_summary/     # a DELIVERABLE: DEPENDS_ON ["region_base"]
        ├── query.py
        ├── test.py
        └── testData/
            ├── region_base.csv               # canned upstream output (the dependency)
            └── expected_region_summary.csv
```

Whether a query is a "component" or a "deliverable" is decided solely by what
references it — there is no folder convention and no per-query flag. A query
listed in `exports.json` (directly, or reachable through another query's
`DEPENDS_ON`) runs; everything else is pruned.

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

### `exporter.py` and `export_config.py`

Writes output files from the in-memory result cache, driven by `exports.json`.

```python
export_outputs(results: dict[str, DataFrame], config: ExportConfig, output_folder) -> dict[str, OutputResult]
```

- `results` maps query name → that query's single output table (the runner's cache)
- `config` is the parsed `exports.json` (see `export_config.py`); each output is either an `xlsx` (a `sheets` map of sheet name → query name) or a `csv` (a single `query` name)
- One query can feed many files / sheets; an `xlsx` can assemble sheets from several different queries
- Each output is written to a temporary file in the same folder, then atomically renamed over the target. This avoids partial writes and works around the common case where Power BI is holding the previous file open — the temp write succeeds and the rename fails loudly with a clear "file in use" error rather than producing a corrupt half-written file. The temp file is cleaned up on any failure
- An output whose query failed or was skipped is **not** written; it is marked `failed` in `summary.json`. No silent partial files
- Outputs are independent — one failed output does not stop the others
- **xlsx**: `Decimal` columns are written with Excel's number format so Power BI sees them as numeric. Excel has no decimal type, so the stored value is float64 with a Decimal-aware display format — exact for the ~15 significant digits finance figures occupy, but not arbitrary precision
- **csv**: `Decimal` columns are rendered as their exact string form (never through float), so CSV preserves precision exactly. UTF-8

`export_config.py` parses and validates `exports.json` before any query runs:
known `format`; xlsx has a non-empty `sheets` map with valid Excel sheet names;
csv has a `query`; filenames are unique. Errors are user-facing (the end user
edits this file). It exposes `referenced_queries(config)` — the set of query
names any output needs, which seeds the runner's reachability analysis.

### `runner.py`

Discovers the queries in `queries/`, builds their dependency DAG, and executes
the part of it that `exports.json` actually needs.

- Auto-discovers query folders by scanning `queries/` for subfolders containing a `query.py` file
- Each `query.py` must expose `load()` and `run(data)`, and may declare `DEPENDS_ON = [...]` (see Query Layer). The runner reads `DEPENDS_ON` from every discovered query to build the DAG
- **Reachability pruning**: the execution set is the queries referenced by `exports.json` plus their transitive `DEPENDS_ON` closure. A query reachable from neither is skipped and logged as such — it never runs. This is what lets the user keep a portfolio of component queries that only execute when something depends on them
- **Cycle detection**: a cyclic `DEPENDS_ON` is a hard error reported before any query executes — nothing runs
- **Single sequential topological walk**: dependencies run before dependents, one query at a time, in one process. Each query runs exactly once; its single output table is cached in memory and injected into the `data` dict of every dependent (merged with that dependent's own `load()` sources). Keeping everything in-process means polars `Decimal` columns are never pickled across a boundary, so precision is preserved by construction. (Process-level parallelism was considered and deliberately rejected here: the executed set is small, the cost is I/O in `load()`, and in-process execution removes the Decimal-pickling risk entirely. It can be revisited if a real run is ever measured to be slow.)
- **Name-collision guard**: if a `DEPENDS_ON` query name collides with a key returned by `load()`, the query fails with a clear error rather than silently clobbering one table with the other
- **Failure propagation**: a query whose dependency failed (or was itself skipped due to a failure) is marked `skipped`, not run against missing inputs
- Each `run(data)` must return a **single** DataFrame. After the queries run, the result cache is handed to `exporter.py`, which writes the files declared in `exports.json`
- If a query raises an exception, logs the full traceback and continues — one bad query does not abort the batch
- Writes a `summary.json` with a per-query section (`ok` / `failed` / `skipped`, with a reason) and a per-output-file section (`written` / `failed`, with a reason)
- Exits non-zero if **any** query failed or any output file failed
- `--query <name>` runs that query plus its dependency closure (a debug aid) and writes any output file whose queries are all within the executed set
- Production runs do **not** execute fixture tests — tests run only when invoked with `--test-only` (see Testing Strategy)

### `tester.py`

Runs fixture-based tests for a given query. Only invoked when the user passes `--test-only` to `run.py` (production / scheduled runs skip it entirely).

- Reads the query's `test.py`, which exposes `FIXTURES` (source-or-dependency name → fixture file path) and `EXPECTED` (a single expected-output file path — the query produces one table)
- `FIXTURES` covers both real sources **and** `DEPENDS_ON` queries: each dependency is supplied as a canned upstream-output CSV and is **never re-executed**. This preserves the finance rule that a test must not start depending on its upstream's sources. A `DEPENDS_ON` entry with no matching `FIXTURES` key is a hard error
- Loads each fixture file (CSV or XLSX) into a DataFrame and assembles the same `data` dict shape that `load()` + the runner's dependency injection would have produced
- Calls the query's `run(data)` directly with that dict — the real `load()` is bypassed, so no Excel files or SQL connections are touched during tests
- Compares the single output table against the expected file: row count, column names, and value-by-value (with a small tolerance for `Decimal`/float)
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

Each query file exposes `load()` (returns a named dict of source DataFrames) and
`run(data)` (transforms that dict and returns a **single** DataFrame). It may
also declare `DEPENDS_ON = [...]`, naming other queries whose output tables the
engine injects into `data` under their query names — exactly like named sources,
but passed in memory so `Decimal` survives intact. This split lets the test
runner substitute fixture data (sources *and* dependencies) for real execution
without modifying the query logic.

**Example (a deliverable that references a component query):**

```python
from functions.transforms import rename

DEPENDS_ON = ["region_base"]          # optional; defaults to [] if absent

def load():
    return {}                          # no sources of its own; consumes a dependency

def run(data):
    base = data["region_base"]         # the upstream query's single output table

    summary = base.sort("amount", descending=True)
    summary = rename(summary, "region", "Region")
    summary = rename(summary, "amount", "Total Sales")

    return summary                     # ONE DataFrame
```

**Rules for query files:**
- `load()` only loads — no transformations
- `run(data)` never calls loader functions — all data comes from the `data` dict (sources from `load()`, dependencies from `DEPENDS_ON`)
- `run(data)` returns exactly one DataFrame
- A `DEPENDS_ON` name must not collide with a `load()` source key (the runner rejects it)
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
    "region_base": "testData/region_base.csv",   # a DEPENDS_ON dependency, canned
    # "sales": "testData/sales.csv",              # ...and/or real sources
}
EXPECTED = "testData/expected_region_summary.csv"  # single path — one output table
```

`FIXTURES` lists every name the query reads — real sources *and* `DEPENDS_ON`
dependencies. A dependency is supplied as a canned upstream-output CSV so the
test stays isolated (the upstream query is never re-run). `EXPECTED` is a single
file path because each query produces exactly one table.

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

### `exports.json` — what gets exported

A second root file, `exports.json`, declares which queries become which output
files. Unlike `config.json`, it holds **no secrets** (just structure) and is
therefore **committed**.

```json
{
  "outputs": [
    { "filename": "region_report.xlsx", "format": "xlsx",
      "sheets": { "Summary": "region_summary", "By Month": "region_monthly" } },
    { "filename": "fx_rates.csv", "format": "csv", "query": "fx_rates_clean" }
  ]
}
```

- `format: "xlsx"` requires a `sheets` map (sheet name → query name, ≥ 1 entry); a single xlsx can pull sheets from several different queries
- `format: "csv"` requires a single `query` name
- Queries are **never exported by default**. Only queries reachable from this file (plus their `DEPENDS_ON` closure) run; everything else is pruned. This is the sole switch that distinguishes a "deliverable" from a reusable "component" query
- Validated before any run: known formats, non-empty sheet maps, valid Excel sheet names, unique filenames, and that every referenced query actually exists

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

Each query's `run(data)` returns a single DataFrame, cached in memory by name.
The output files are then assembled from that cache according to `exports.json` —
file names and formats come from the export config, not from the query folder
names. One query can feed several files or sheets; a component query feeds none
directly.

```
output/
├── region_report.xlsx        # sheets assembled from region_summary, region_monthly
├── fx_rates.csv              # the region_base component is NOT here — only depended upon
├── summary.json              # Per-query AND per-output-file status for monitoring
└── logs/
    └── pipeline-2026-05-12-1200-56.log
```

`summary.json` carries two sections — `queries` (`ok` / `failed` / `skipped`
with reasons) and `outputs` (`written` / `failed` with reasons):

```json
{
  "queries": {
    "region_base":    { "status": "ok" },
    "region_summary": { "status": "ok" }
  },
  "outputs": {
    "fx_rates.csv": { "status": "written" }
  }
}
```

Power BI connects to the output folder and refreshes from these files. Logs and `summary.json` live alongside but are ignored by Power BI's folder connector.

If Power BI has a file open when the pipeline tries to overwrite it, the atomic temp-file-then-rename pattern (see `exporter.py`) will fail loudly rather than producing a corrupt half-written workbook. The failure is logged and recorded in `summary.json` so the user can close Power BI and re-run.

---

## Future Considerations

- **Azure migration**: `runner.py` and `run.py` are designed to be called from any scheduler. Moving to Azure Functions or Azure Container Apps requires no changes to queries or functions — only the trigger mechanism changes.
- **Additional connectors**: `loader.py` can be extended with `read_sharepoint()`, etc. without affecting existing queries.
- **Query references & `DEPENDS_ON`** *(implemented)*: queries reference other queries by name via `DEPENDS_ON`; the runner builds a DAG, prunes to what `exports.json` needs, detects cycles, and executes in topological order. See `runner.py` / `export_config.py` above.
- **Parallelism**: execution is a single sequential topological walk, chosen deliberately over process parallelism so that `Decimal` tables are never pickled across process boundaries (see `runner.py`). If the executed set ever grows large enough that wall-clock time matters, independent queries within a dependency "wave" could be run concurrently — but only after verifying polars `Decimal` columns survive the chosen IPC mechanism exactly.
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
