# Authoring Queries

Queries live under `queries/`. Each query reads named sources, calls shared
functions, and returns one table. Edit `engine/` or `functions/` only when a
needed operation is missing.

Think of a query as the Python version of one Power Query step chain: it starts
with source tables, applies a repeatable recipe, and ends with one report table.
You can author these with an agent by describing the business logic and checking
the expected result.

## Structure

```text
queries/sales_by_region/
|-- query.py
|-- test.py
`-- testData/
    `-- happy_path/
        |-- sales.csv
        |-- regions.csv
        `-- expected.csv
```

- `query.py`: `load()` reads sources; `run(data)` transforms and returns one DataFrame.
- `test.py`: defines non-empty `TESTS`.
- `testData/<case>/`: one folder per case with fixtures and `expected.csv`.
- `exports.json`: chooses which queries produce files.

Fixtures are small sample input files used only for testing. `expected.csv` is
the table you expect from those samples. Keeping them together makes each test
case easy to review in Excel or a text editor.

Useful examples: `queries/region_base`, `queries/region_summary`, and
`queries/activity_hours`.

## Workflow

1. Describe sources, joins, filters, calculations, grouping, and output columns.
2. Agent creates `query.py`, `test.py`, and small fixture CSVs.
3. You provide known-good expected output from Excel, hand calculation, or a
   trusted prior run.
4. Agent writes `expected.csv`.
5. Run the query test:

```bash
uv run python run.py --query <query_name> --test-only
```

Finance expected values must come from you. If the agent invents both query and
expected output, the test is not meaningful.

Good prompts are specific. Name the real columns, say which rows should be kept
or removed, describe calculations in business terms, and include one or two
example rows when possible.

## Tests

```python
TESTS = [
    {
        "name": "Happy Path",
        "FIXTURES": {
            "sales": "testData/happy_path/sales.csv",
            "regions": "testData/happy_path/regions.csv",
        },
        "EXPECTED": "testData/happy_path/expected.csv",
    },
]
```

Add separate cases for important branches: empty input, refunds, missing
categories, boundary dates, and similar risks. Keep fixtures small, usually
10-20 rows.

When a test fails, the runner reports the mismatched cells. That is usually
faster to review than comparing whole spreadsheets by eye.

## Exports

Queries write files only when listed in `exports.json`.

```json
{
  "outputs": [
    {
      "filename": "sales_by_region.xlsx",
      "format": "xlsx",
      "sheets": { "Sales by Region": "sales_by_region" }
    },
    {
      "filename": "fx_rates.csv",
      "format": "csv",
      "query": "fx_rates_clean"
    }
  ]
}
```

Use `sheets` for Excel workbooks and `query` for CSV files. Leave reusable
component queries unexported.

To ship a new report, first get the query test passing, then add one entry to
`exports.json`. Queries not listed there do not become files on their own.

## Dependencies

Use `DEPENDS_ON` when a query consumes another query:

```python
DEPENDS_ON = ["region_base"]

def run(data):
    base = data["region_base"]
    ...
```

In dependent query tests, provide the dependency output as a fixture:

```python
TESTS = [
    {
        "name": "Happy Path",
        "FIXTURES": {"region_base": "testData/happy_path/region_base.csv"},
        "EXPECTED": "testData/happy_path/expected.csv",
    },
]
```

The dependency is not re-run during that test.

This lets one shared cleanup query feed several report queries. For example,
`region_base` can standardize raw sales data once, while `region_summary` turns
that cleaned table into the final report.

## Rules

- Queries call named functions only.
- Do not import Polars in `query.py`.
- Do not call `pl.*`, `.with_columns`, `.dt.*`, `.cast`, or `.sort` directly.
- If an operation is missing, add a small tested shared function first.
- `load()` loads sources only; `run(data)` transforms only.
- Validate early with `expect_non_empty` and `expect_columns`.
- Use named sources from `config.json`, never raw paths.
- Convert money with `to_decimal(df, "amount")`, never float.
- Use `Decimal(str(value))`, not `Decimal(value)`.
- Rounding is half-up; decimal places come from `settings.json` or `places=`.
- Use arithmetic helpers for formulas:

```python
df = multiply(df, "units", "price", new_column="amount", places=4)
df = divide(df, "amount", "months", new_column="monthly")
```

For non-money ratios or unit conversions, pass `as_decimal=False`.

These rules keep query files readable for business review. Each line should look
like a named action, not low-level dataframe code.

## Commands

```bash
uv run python run.py --all --output ./output
uv run python run.py --query region_summary --output ./output
uv run python run.py --all --test-only
uv run python run.py --query region_summary --test-only
```

Production runs do not run fixture tests automatically.

Use test commands while changing a query. Use output commands when you want the
actual Excel or CSV files.

## Failures

- Failures print `[FAILED] <name> - see logs/<filename>`.
- Tracebacks are under `output/logs/`.
- `output/summary.json` records query and output status.
- A failed or skipped query does not write partial output.
- Cycles and typoed query names stop the run before execution.
- Open output files, usually in Power BI, must be closed before re-running.
