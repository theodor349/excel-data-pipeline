# excel-data-pipeline

Python (Polars) replacement for an Excel/Power Query workflow. It reads Excel + CSV + JSONL + MSSQL, transforms data through composable queries, and writes Excel/CSV files for Power BI consumption. See `QUERIES.md` for authoring queries and `CLAUDE.md` for the architecture and conventions.

## Architecture

The repo is split into **system space** (the framework — developers only) and
**user space** (queries — maintained by the non-technical end user):

- **System space** — `engine/` (loaders, runner, exporter, tester, validator),
  `functions/` (shared transforms/aggregations/joins), and `run.py`. This is the
  framework; query authors never edit it.
- **User space** — `queries/<name>/` (one folder per query) and `exports.json`
  (which queries become output files). This is where reporting logic lives.

A query splits `load()` (read sources) from `run(data)` (transform only), returns
one table, and can reuse another query via `DEPENDS_ON`. See `QUERIES.md`.

## Setup (developer)

```bash
uv sync
uv run pytest
```

## Running the pipeline

```bash
# Run all queries
uv run python run.py --all --output ./output

# Run a single query
uv run python run.py --query region_summary --output ./output

# Run tests for queries (no I/O, no export)
uv run python run.py --all --test-only
```

## Configuration

Copy `config.example.json` to `config.json` and fill in real source paths and credentials. `config.json` is gitignored.

## Performance

| Query | Python pipeline | Excel Power Query |
|---|---|---|
| activity_hours | 0.28 s | 4.5 s |

## User guide

See `QUERIES.md` for instructions on authoring new queries.
