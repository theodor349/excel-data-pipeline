# excel-data-pipeline

Python pipeline for finance reporting. It replaces Excel / Power Query refresh
steps with repeatable Python queries, then writes CSV or Excel files for Power
BI and other reporting tools.

The project is designed for two kinds of work:

- Query authoring: describe report logic in business terms, then keep the code
  inside one `queries/<query_name>/` folder.
- Framework development: extend the shared engine or the named functions that
  queries are allowed to use.

For first-time setup, see `INSTALL.md`. For creating or changing report queries,
see `QUERIES.md`.

## How It Works

The repo has two main areas:

- `engine/`: runner, loaders, exporter, validator, and fixture-test support.
- `functions/`: shared named actions for filtering, joins, grouping, date work,
  text cleanup, column selection, and Decimal-safe calculations.
- `queries/`: one folder per report or reusable component query.
- `exports.json`: decides which query results become output files.

Each query follows the same shape:

- `load()` reads source tables only.
- `run(data)` transforms tables only.
- `run(data)` returns one table.
- `DEPENDS_ON = [...]` lets one query use another query result.

Queries should read like Power Query steps: clean text, filter rows, join tables,
calculate money, group totals, rename columns. Query files use named functions
from `functions/`; they do not use raw Polars operations.

## Current Example Queries

The repo currently includes showcase queries that demonstrate composition:

- `showcase_sales_base`: cleans order lines, removes cancelled rows, standardizes
  names and regions, converts dates and money, and calculates net sales.
- `showcase_product_margin`: cleans product and unit-cost data for margin work.
- `showcase_customer_margin`: joins the two component queries, calculates gross
  margin, groups by customer, and returns the final customer margin report.

These are examples for learning and testing. Real finance reports should follow
the same folder pattern and include small fixture tests with known-good expected
values.

## Setup

Install dependencies:

```bash
uv sync
```

Verify the framework tests:

```bash
uv run pytest
```

Verify all query fixture tests:

```bash
uv run python run.py --all --test-only
```

Run one query's fixture tests:

```bash
uv run python run.py --query showcase_customer_margin --test-only
```

## Running Real Data

Create `config.json` from the template, then fill in real source paths and
read-only database details:

```bash
cp config.example.json config.json
```

On Windows PowerShell:

```powershell
Copy-Item config.example.json config.json
```

`config.json` is gitignored because it can contain local paths and credentials.

Run all exported reports after `exports.json` lists the reports you want:

```bash
uv run python run.py --all --output ./output
```

Run one query against real sources. This also writes an output file when
`exports.json` has an entry that uses that query:

```bash
uv run python run.py --query showcase_customer_margin --output ./output
```

Only queries listed in `exports.json` produce files. Reusable component queries
can stay unexported.

## Configuration Files

- `config.example.json`: safe template for source names, local file paths, and
  read-only MSSQL connection settings.
- `config.json`: private local configuration; do not commit it.
- `settings.json`: committed finance policy. It controls default Decimal places.
- `exports.json`: committed run policy. It controls output filenames, formats,
  and workbook sheets.

Money is handled as Python `Decimal`. Rounding is half-up. Decimal places come
from `settings.json` unless a function call explicitly passes `places=`.

## Common Commands

```bash
# Install or refresh dependencies
uv sync

# Run framework unit tests
uv run pytest

# Run all query fixture tests, with no real source I/O
uv run python run.py --all --test-only

# Run one query fixture test
uv run python run.py --query showcase_customer_margin --test-only

# Produce output files for all queries listed in exports.json
uv run python run.py --all --output ./output

# Run one query against real sources; writes matching configured exports only
uv run python run.py --query showcase_customer_margin --output ./output
```

## Notes For Agents

Use Query Author Mode when changing report logic under `queries/<query_name>/`.
Use Developer Mode when changing `engine/`, `functions/`, top-level docs,
configuration templates, or the shared command runner.

When adding or changing finance logic, do not invent expected output. Ask the
domain user for known-good expected values, then encode those values in fixture
tests.
