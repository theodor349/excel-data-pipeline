# Authoring Queries

This guide is for the person who will author queries with the help of an AI coding agent. You shouldn't need to touch anything in `engine/` or `functions/`.

## What a query is

A query is one folder under `queries/` that produces **one table**. Inside the folder:

```
queries/sales_by_region/
├── query.py        # the actual transformation logic — returns one table
├── test.py         # tells the framework which fixture files to use
└── testData/
    ├── sales.csv               # one fixture per source the query loads
    ├── regions.csv
    └── expected_sales_by_region.csv   # what the output table should look like
```

A query's table only becomes a file (xlsx or csv) when you list it in
`exports.json` (see "Exporting", below). Queries that aren't listed there don't
run on their own — they exist to be reused by other queries.

Look at `queries/example/` for a working reference (named sources, fiscal year,
Decimal money, parameter table, fixture test), and at `queries/region_base/` +
`queries/region_summary/` for how one query reuses another.

## How to create a new query (with the agent)

1. **Describe what you want, in plain language.** Tell the agent what data to read, what to do with it, and what the output should look like. Be concrete — name columns, give an example row.
2. **Agent creates `query.py` and the testData fixtures.** It will use named sources from `config.json` (never a raw file path).
3. **You compute the expected output by hand** — in Excel, on paper, or against a known-good prior run. **This step is non-negotiable for finance work.** If the agent both writes the query *and* computes the expected output, the test only proves the query agrees with itself, not with reality.
4. **Agent encodes your expected values into the expected CSV.**
5. **Run the test:**
   ```bash
   uv run python run.py --query <query_name> --test-only
   ```
   The output is `[OK] <query_name>` or a list of cell-level mismatches.

## Exporting — turning a query into a file

Queries don't produce files on their own. The committed `exports.json` at the
repo root says which query becomes which file:

```json
{
  "outputs": [
    { "filename": "sales_by_region.xlsx", "format": "xlsx",
      "sheets": { "Sales by Region": "sales_by_region" } },
    { "filename": "fx_rates.csv", "format": "csv", "query": "fx_rates_clean" }
  ]
}
```

- An **xlsx** lists `sheets` — each sheet name maps to a query name. You can put several queries' tables into one workbook as separate sheets.
- A **csv** lists a single `query`.
- If a query isn't referenced here (directly or through another query that needs it), it simply doesn't run.

To ship a new report: write the query, get its test passing, then add one entry
to `exports.json`.

## Splitting a query into reusable components

When several reports share the same cleanup/aggregation, write that part once as
its own query and let the others reference it. The shared query is a
**component**; you do not export it.

1. Write the component query (e.g. `region_base`) like any other — it returns one table.
2. In the query that needs it, declare the dependency at the top of `query.py`:
   ```python
   DEPENDS_ON = ["region_base"]

   def run(data):
       base = data["region_base"]    # the component's output table, ready to use
       ...
   ```
   The framework runs `region_base` first and hands its table to you in `data`,
   under the same name. (It's passed in memory, so Decimal money stays exact.)
3. In the dependent query's `test.py`, supply the component's output as a **canned fixture** — list it in `FIXTURES` under the dependency name:
   ```python
   FIXTURES = { "region_base": "testData/region_base.csv" }
   EXPECTED = "testData/expected_region_summary.csv"
   ```
   You (or the agent) create `region_base.csv` as a small, representative sample
   of what `region_base` produces. The component is **not** re-run during the
   test — that keeps the test focused on the dependent query's own logic.
4. Add only the deliverable (e.g. `region_summary`) to `exports.json`; the
   component runs automatically because the deliverable depends on it.

`queries/region_base/` + `queries/region_summary/` are a working example of all four steps.

## Things to keep in mind

- **Money columns must use `to_decimal(df, "amount", places=2)`.** Do not use `to_float` for money. The framework preserves Decimal precision end-to-end; floats silently drift on large sums and break ledger reconciliation.
- **Return one table from `run(data)`.** Each query produces a single table; `exports.json` decides where it goes. If you need two outputs, that's two queries.
- **Don't load files in `run(data)`.** All loading happens in `load()`; `run(data)` only transforms. This is what lets the test runner swap real sources for fixture files.
- **Keep fixtures small.** 10–20 rows is enough — they exist to prove the logic, not to stress-test.
- **Validate inputs at the top of `run(data)`** with `expect_non_empty` and `expect_columns`. This catches missing columns or empty source files immediately, with a clear error.
- **Naming a new source.** When you want to read from a new Excel file or database, the developer adds it to `config.json` under `excel_sources`, `csv_sources`, or `connections`. Once named, you reference it by name only.

## Running the pipeline

```bash
# Run all queries (production-style — writes Excel files)
uv run python run.py --all --output ./output

# Run one query
uv run python run.py --query example --output ./output

# Run all fixture tests (no Excel/SQL is touched, no files written)
uv run python run.py --all --test-only

# Test one query
uv run python run.py --query example --test-only
```

Production runs deliberately do **not** run fixture tests. Tests gate the *change* (when you edit a query); they don't run on every scheduled refresh.

## When something goes wrong

- A query failure prints `[FAILED] <name> — see logs/<filename>` to the console. Open that log file under `output/logs/` to see the full traceback.
- The framework keeps going if one query fails — the others still run and export.
- `output/summary.json` has two sections: `queries` (each is `ok`, `failed` with a reason, or `skipped`) and `outputs` (each file is `written` or `failed`). Power Automate can read this without parsing logs.
- `skipped` means a query didn't run — either nothing referenced it, or one of its `DEPENDS_ON` dependencies failed. A file whose query failed or was skipped is **not** written (no half-finished files).
- A cyclic dependency (A needs B, B needs A) or a typo'd query name in `exports.json` / `DEPENDS_ON` stops the whole run up front with a clear message — fix the name and re-run.
- If Power BI has an output file open when the pipeline runs, that file will fail with a clear "file in use" error. Close Power BI and re-run.
