# excel-data-pipeline

Python (Polars) replacement for an Excel/Power Query workflow. It reads Excel + CSV + JSONL + MSSQL, transforms data through composable queries, and writes Excel/CSV files for Power BI consumption. See `INSTALL.md` for first-time setup (non-developer, step-by-step), `QUERIES.md` for authoring queries, and `CLAUDE.md` for the architecture and conventions.

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

**Functions-only queries.** Queries are written purely from the shared vocabulary
in `functions/` — there is no raw Polars in any query (the reference queries
contain zero `pl.*` calls). This keeps each query readable as a recipe by a
non-developer. The trade-off is enforced on the framework side: **every function
in `functions/` ships with a unit test**, and money-handling functions ship with
an exact-Decimal precision test. The readability of queries is only safe because
the functions beneath them are verified — including any AI-authored ones.

## Setup

**First time / non-developer?** Follow `INSTALL.md` — a step-by-step guide from a clean
machine (install Python, install `uv`, get the project, `uv sync`, verify, configure) for
someone who maintains queries but isn't a developer.

**Developer extending the framework** (modifying `engine/`, `functions/`, or adding
shared transforms):

```bash
uv sync
uv run pytest
```

Read `CLAUDE.md` for the full architecture and testing requirements.

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

`settings.json` (committed) holds finance policy: `decimal_places`, the default precision for money (currently 2; override per column with `places=`). Rounding is hardcoded **half-up** and is intentionally not configurable.

## Performance

| Query | Python pipeline | Excel Power Query |
|---|---|---|
| activity_hours | 0.28 s | 4.5 s |

## User guide

See `QUERIES.md` for instructions on authoring new queries.
