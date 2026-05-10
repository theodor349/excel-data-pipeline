# Authoring Queries

This guide is for the person who will author queries with the help of an AI coding agent. You shouldn't need to touch anything in `engine/` or `functions/`.

## What a query is

A query is one folder under `queries/` that produces one Excel output file for Power BI. Inside the folder:

```
queries/sales_by_region/
├── query.py        # the actual transformation logic
├── test.py         # tells the framework which fixture files to use
└── testData/
    ├── sales.csv               # one fixture per source the query loads
    ├── regions.csv
    └── expected_sales_by_region.csv   # what the output should look like
```

Look at `queries/example/` for a working reference — it covers every pattern: named sources, fiscal year, Decimal money, parameter table, and a fixture test.

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

## Things to keep in mind

- **Money columns must use `to_decimal(df, "amount", places=2)`.** Do not use `to_float` for money. The framework preserves Decimal precision end-to-end; floats silently drift on large sums and break ledger reconciliation.
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
- `output/summary.json` lists every query's status (`ok` or `failed` with a reason). Power Automate can read this without parsing logs.
- If Power BI has an output file open when the pipeline runs, the affected query will fail with a clear "file in use" error. Close Power BI and re-run.
