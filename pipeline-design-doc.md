# Data Pipeline — Prototype Design Document

## Overview

This document describes the architecture of a Python-based data pipeline that replaces an Excel/Power Query workflow. It is written for a **developer implementing the framework**. The end user of the finished project is a non-technical person who will author and maintain queries with the assistance of an AI coding agent.

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
│   ├── loader.py           # Functions for reading Excel and SQL sources
│   ├── exporter.py         # Functions for writing output Excel files
│   ├── runner.py           # Discovers and executes queries, handles errors
│   ├── tester.py           # Loads and runs fixture-based tests per query
│   └── logger.py           # Writes structured logs throughout execution
│
├── functions/              # SHARED FUNCTIONS — extended by user + agent over time
│   ├── aggregations.py     # avg(), sum(), count(), etc.
│   ├── transforms.py       # lowercase(), to_int(), rename(), filter_rows(), etc.
│   └── joins.py            # merge(), append()
│
└── queries/                # QUERIES — authored and maintained by user + agent
    ├── sales_by_region/
    │   ├── query.py        # The query definition
    │   ├── test.py         # Fixture-based test
    │   └── testData/
    │       ├── input.xlsx  # Sample input data
    │       └── expected.xlsx # Expected output data
    └── monthly_summary/
        ├── query.py
        ├── test.py
        └── testData/
            ├── input.xlsx
            └── expected.xlsx
```

---

## Framework Layer (`engine/`)

The framework is implemented once by a developer. The user never needs to open or edit these files.

### `loader.py`

Provides two functions the user calls in their queries to load source data.

```python
read_excel(file_path: str, table_name: str) -> DataFrame
read_sql(connection_name: str, query: str) -> DataFrame
```

- `read_excel` reads a specific table from a local Excel file and returns a DataFrame
- `read_sql` looks up a named connection from a config file (see Configuration) and executes a read-only SQL query — it does not create, write, or alter any data
- SQL connections are named (e.g. `"sales_db"`) so the user never handles connection strings directly

### `exporter.py`

Writes output DataFrames to Excel files. Supports multiple sheets in a single output file.

```python
export(sheets: dict[str, DataFrame], output_folder: str, filename: str) -> None
```

- `sheets` is a dictionary mapping sheet name to DataFrame
- Creates the output folder if it does not exist
- Overwrites existing files with the same name

### `runner.py`

Discovers all queries in the `queries/` directory and executes them.

- Auto-discovers query folders by scanning `queries/` for subfolders containing a `query.py` file
- Each `query.py` must expose a `run()` function that returns a dict of sheet name → DataFrame
- Calls `exporter.py` with the result of each `run()`
- If a query raises an exception or warnings, logs the full report and continues to the next query
- Accepts an optional query name to run a single query instead of all

### `tester.py`

Runs fixture-based tests for a given query.

- Loads `testData/input.xlsx` and passes it to the query's `run()` function
- Compares the result against `testData/expected.xlsx` sheet by sheet
- Reports any row count mismatches, column mismatches, or value differences
- Tests are run before the query exports its output — a failing test logs a warning but does not block execution (see Testing section)

### `logger.py`

Writes structured logs to a `pipeline.log` file in the output folder.

- Logs query start, query success, query failure (with full traceback), and test results
- Log format is readable by both humans and AI agents for debugging
- Does not attempt to produce plain-English error summaries — raw tracebacks are preserved

---

## Shared Functions Layer (`functions/`)

These are standalone functions that operate on DataFrames. They are the vocabulary the user uses to write queries. The developer seeds this layer with common functions; the user and AI agent extend it over time.

### Design rules for functions

- Every function takes a DataFrame as its first argument and returns a DataFrame
- Functions are pure — they do not modify the input, they return a new DataFrame
- Functions are small and do one thing
- Function signatures should be readable out loud: `lowercase(df, "name")` reads as "lowercase the name column"

### `aggregations.py` — starter set

```python
avg(df, group_by: str | list, column: str) -> DataFrame
sum(df, group_by: str | list, column: str) -> DataFrame
count(df, group_by: str | list) -> DataFrame
```

### `transforms.py` — starter set

```python
lowercase(df, column: str) -> DataFrame
to_int(df, column: str) -> DataFrame
to_float(df, column: str) -> DataFrame
rename(df, old_name: str, new_name: str) -> DataFrame
keep_columns(df, columns: list) -> DataFrame
filter_rows(df, column: str, value) -> DataFrame
drop_nulls(df, column: str) -> DataFrame
```

### `joins.py` — starter set

```python
merge(left: DataFrame, right: DataFrame, on: str | list, how: str) -> DataFrame
append(top: DataFrame, bottom: DataFrame) -> DataFrame
```

- `how` in `merge` must be explicit: `"left"`, `"inner"`, `"outer"`, `"right"`
- `append` requires both DataFrames to have the same columns

---

## Query Layer (`queries/`)

This is the part of the project the user owns. Each query lives in its own folder.

### Query file (`query.py`)

Each query file has a single `run()` function. It calls loader functions to get data, applies transformations using functions from `functions/`, and returns a dictionary of sheet name → DataFrame.

**Example:**

```python
from engine.loader import read_excel, read_sql
from functions.transforms import lowercase, to_int, rename
from functions.aggregations import avg

def run():
    # Load
    sales = read_excel("data/sales.xlsx", "Sheet1")
    regions = read_sql("sales_db", "SELECT id, name FROM regions")

    # Normalize
    sales = lowercase(sales, "customer_name")
    sales = to_int(sales, "amount")
    regions = lowercase(regions, "name")
    regions = rename(regions, "name", "region_name")

    # Combine
    combined = merge(sales, regions, on="region_id", how="left")

    # Summarize
    result = avg(combined, group_by="region_name", column="amount")

    return {"Sales by Region": result}
```

**Rules for query files:**
- Always import from `engine.loader`, `engine.exporter` is handled by the runner
- Every intermediate step should be a named variable — avoid chaining on one line
- Variable names should describe what the data represents, not how it was made
- Comments above each block (`# Load`, `# Normalize`, `# Combine`) are encouraged

### Test file (`test.py`)

Each query has a fixture-based test. The developer sets up the test structure; the user and agent author the actual fixture data.

```python
# test.py — this structure is always the same, generated by the agent
FIXTURE_INPUT = "testData/input.xlsx"
FIXTURE_EXPECTED = "testData/expected.xlsx"
FIXTURE_SHEET = "Sheet1"          # Sheet to use as input
EXPECTED_SHEET = "Sales by Region" # Sheet to compare against in output
```

The test runner (`tester.py`) reads these constants and does the comparison automatically. The user's job is to fill in `testData/input.xlsx` with a small representative sample (e.g. 10–20 rows) and `testData/expected.xlsx` with the result they expect for that sample.

**Workflow for authoring a test (user + agent):**
1. User describes what the query should do in plain language
2. Agent creates a small `input.xlsx` with representative data
3. Agent calculates what the expected output should be
4. Agent creates `expected.xlsx`
5. User runs the test and checks whether the result makes sense

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
  }
}
```

- SQL passwords are stored here — the file should not be committed to version control (add to `.gitignore`)
- Excel source paths are named so queries reference them by name, not by path

---

## Entry Point (`run.py`)

```
# Run all queries
python run.py --output C:/reports/output

# Run a single query
python run.py --query sales_by_region --output C:/reports/output

# Run tests only (no export)
python run.py --test-only

# Run a single query's test
python run.py --query sales_by_region --test-only
```

- Power Automate calls `run.py --all --output <folder>` on a schedule
- During development, the user runs individual queries via the agent in a terminal
- Output folder is created if it does not exist
- A `pipeline.log` file is written to the output folder on every run

---

## Error Handling

- Query failures do not stop other queries from running
- The full Python traceback is written to `pipeline.log`
- A summary line is printed to stdout for each query: `[OK] sales_by_region` or `[FAILED] sales_by_region — see pipeline.log`
- Test failures log a warning but do not block export — the query still runs and exports
- The AI agent is the primary consumer of error logs, so no plain-English wrapping is applied

---

## Testing Strategy

Three levels of validation per query:

| Level | What it checks | When it runs |
|---|---|---|
| Input validation | Source data has expected columns and is not empty | At the start of every `run()` |
| Step validation | Intermediate DataFrames have expected shape after key transforms | Inline in `run()`, optional |
| End-to-end test | Full output matches fixture expected output | Via `--test-only` or before export |

Input validation is handled by a helper the framework provides:

```python
from engine.validator import expect_columns, expect_non_empty

def run():
    sales = read_excel("sales", "Sheet1")
    expect_non_empty(sales, "sales")
    expect_columns(sales, ["customer_name", "amount", "region_id"])
    ...
```

If validation fails, the query raises an error immediately with a clear message about what was missing.

---

## Output Format

Each query's `run()` returns a dict of sheet name → DataFrame. The runner passes this to `exporter.py`, which writes an Excel file named after the query folder.

```
output/
├── sales_by_region.xlsx      # Contains sheet "Sales by Region"
├── monthly_summary.xlsx      # Contains sheets "Revenue", "Units"
└── pipeline.log
```

Power BI connects to the output folder and refreshes from these Excel files.

---

## Future Considerations

- **Azure migration**: `runner.py` and `run.py` are designed to be called from any scheduler. Moving to Azure Functions or Azure Container Apps requires no changes to queries or functions — only the trigger mechanism changes.
- **Additional connectors**: `loader.py` can be extended with `read_sharepoint()`, etc. without affecting existing queries.
- **Parallelism**: Queries are currently run sequentially. If volume grows, `runner.py` can be updated to run queries in parallel — no query changes needed.
- **Power Automate**: The local Power Automate client runs `python run.py --output <folder>` as a shell command on a schedule. No other integration is required.

---

## Developer Checklist

Before handing over to the user, the developer should complete:

- [ ] Implement `engine/loader.py` with `read_excel`, `read_csv` and `read_sql`
- [ ] Implement `engine/exporter.py`
- [ ] Implement `engine/runner.py` with auto-discovery and error handling
- [ ] Implement `engine/tester.py` with fixture comparison
- [ ] Implement `engine/logger.py`
- [ ] Implement `engine/validator.py` with `expect_columns` and `expect_non_empty`
- [ ] Seed `functions/` with starter aggregations, transforms, and joins
- [ ] Create `config.json` with correct connection strings and file paths
- [ ] Create one example query end-to-end (`queries/example/`) as a reference for the user
- [ ] Verify `run.py --all` and `run.py --query example --test-only` work correctly
- [ ] Add `config.json` and `output/` to `.gitignore`
- [ ] Write a short `QUERIES.md` guide for the user explaining how to create a new query with agent help
