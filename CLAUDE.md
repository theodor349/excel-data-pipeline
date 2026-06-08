# CLAUDE.md

Guidance for Claude (or any AI agent) working in this repo. `README.md` covers running the pipeline; `QUERIES.md` is the query-author workflow. Read the reference queries under `queries/` before doing non-trivial work.

## What this project is

A Python pipeline that replaces an Excel/Power Query workflow for a finance department. It reads Excel + MSSQL, transforms data through composable queries, and writes Excel files for Power BI consumption. Runs locally on Windows via Power Automate; designed for a future Azure migration with no query changes.

## Two modes — figure out which one applies before editing

The project is split so a non-technical end user can maintain queries indefinitely without touching the framework. Decide which mode the request fits:

### Mode 1 — Developer (human or AI extending the framework)

You own everything outside `queries/`. Typical tasks: implementing a new loader, adding a shared function (transform/aggregation/join), fixing a bug in the engine, improving error messages, writing precision regression tests.

- Touch freely: `engine/`, `functions/`, `pyproject.toml`, `config.example.json`, `run.py`, top-level docs.
- Don't touch `queries/` except the reference queries (`region_base`, `region_summary`, `activity_hours`) — the rest belong to the user.
- **Every shared function needs a unit test under `functions/tests/` — no exceptions.** A function without a test does not ship. Tests must cover the does-not-mutate behavior and, for anything touching money, exact-Decimal precision. Every engine module also needs a test under `engine/tests/`.
- The functions you add are the *entire vocabulary* a non-developer query author has. When a query needs an operation, the right move is to add a small, named, tested function here — not to let raw Polars leak into a query (see the functions-only invariant below). Name functions for what they do in plain language (`epoch_to_datetime`, `divide`, `sort`), not after the Polars call they wrap.
- Run `uv run pytest` before declaring anything done. The full suite must stay green.

### Mode 2 — Query author (helping the end user)

The user describes a reporting need ("I need to summarize sales by region for FY 2026"). Your job is to author a query inside `queries/`. The end user is non-technical — they will read your output, so favor clarity over cleverness.

- Touch only the new `queries/<query_name>/` folder, plus an entry in `exports.json` if the query should produce an output file.
- **Queries call named functions only — no raw Polars.** `query.py` may `import` from `functions/` and `engine/`, but must not `import polars` or call `pl.*` / `.with_columns` / `.dt.*` / `.cast` / `.sort` directly. A non-developer has to be able to read every line as a recipe step. If you catch yourself reaching for the Polars API inside a query, stop: the operation needs a named, tested function instead.
- Never modify `engine/` or `functions/` to make a query work — if a function is missing, switch to developer mode and add it as a separate, tested change first.
- `query.py` must split `load()` (sources only) from `run(data)` (transforms only). The test runner depends on this split to substitute fixtures for real sources.
- `run(data)` returns a **single** DataFrame. To reuse one query inside another, declare `DEPENDS_ON = ["other_query"]`; the engine injects that query's output table into `data` under its name (in memory, so `Decimal` is preserved). A `DEPENDS_ON` name must not collide with a `load()` source key. Adding a dependency does **not** change the two-mode rules — composing queries is still Mode 2.
- A query runs only if it is reachable from `exports.json` (directly or via another query's `DEPENDS_ON`). "Component" vs "deliverable" is decided by `exports.json` alone — no per-query flag.
- In `test.py`: define `TESTS = [...]`, a non-empty list of test-case dicts. Each case has `"name"` (a label for reporting), `"FIXTURES"` (a dict of source -> path), and `"EXPECTED"` (a single file path). `FIXTURES` covers real sources **and** every `DEPENDS_ON` dependency (as a canned upstream-output CSV — dependencies are never re-run in tests). Multiple cases let one query be checked against several fixture/expected pairs (happy path, edge cases); every case must pass or the query fails. The old top-level `FIXTURES`/`EXPECTED` format is no longer accepted.
- Use named sources from `config.json` (e.g. `read_excel("sales", "Sheet1")`) — never raw file paths.
- Write small CSV fixtures (10–20 rows) into `testData/`. Give each test case its own subfolder — `testData/<case>/` holds that case's input fixtures plus an `expected.csv` (e.g. `testData/happy_path/sales.csv` + `testData/happy_path/expected.csv`). Paths in `FIXTURES`/`EXPECTED` are explicit, so this is a convention, not an engine requirement — but keep the reference queries following it.
- **Do not compute the expected output yourself.** Ask the user to compute it (in Excel, by hand, or against a known-good prior run) and only then encode their values into the expected CSV. Otherwise the test just proves the query agrees with itself, which is worthless for finance reconciliation.

`QUERIES.md` is the user-facing version of this mode — keep both in sync if the workflow changes.

## Invariants that apply in both modes

- **Functions-only queries; every function is tested.** Queries are written purely in terms of the shared vocabulary in `functions/` — no raw Polars in `query.py` (the reference queries contain zero `pl.*` calls; keep it that way). The flip side of that promise is that the vocabulary must be trustworthy: **every function in `functions/` ships with a unit test**, and money-touching functions ship with an exact-Decimal precision test. These two rules are a pair — the readability of queries is only safe because the functions underneath them are verified. AI-authored transforms are no exception: a generated function without a human-checked test is exactly the silent-precision-bug risk this project exists to remove.
- **Decimal end-to-end is load-bearing.** Money columns must use `to_decimal(df, col)` (places defaults from `settings.json`). Never use `to_float` for money. Money arithmetic (`add`/`subtract`/`multiply`/`divide` in `functions/transforms.py`, and `avg`) is computed through Python `Decimal`, **not** Polars' native Decimal cast/ops — the native path rounds half-even at the wrong scale and can silently drop precision (e.g. `1.10 * 1.05 -> 1.16`). If you add or modify aggregation/transform/join code, add a precision regression test (e.g. `1000 × Decimal("0.10") == Decimal("100.00")` exactly, no float tolerance).
- **`Decimal(str(value))`, never `Decimal(value)`.** The latter captures the IEEE-754 binary expansion; the former gives the literal the user typed. This matters wherever floats are converted to Decimal (loading, the arithmetic functions, CSV comparison in the tester, etc.).
- **Rounding is hardcoded half-up — not configurable.** Finance convention, enforced for real in `functions/_rounding.py` and used by `to_decimal`, the arithmetic functions, and `avg`. It is deliberately *not* a setting: a swappable rounding mode would let the same data round two ways and make tests depend on the environment. Only the number of decimal `places` is configurable.
- **`settings.json` is committed.** It holds finance policy that must be identical everywhere and auditable in git history — currently just `decimal_places` (the default for money). It is *not* the gitignored `config.json` (paths + credentials). Every money function takes a per-call `places=` that overrides the default (e.g. FX rates at 4). `divide(..., as_decimal=False)` opts out of Decimal entirely for non-money ratios/unit conversions (returns float).
- **`run(data)` never calls loader functions.** All I/O happens in `load()`; transforms operate on the `data` dict only. The tester relies on this to bypass real sources.
- **`config.json` is gitignored.** Don't commit it. Use `config.example.json` as the shared reference. Never put real credentials in code or examples.
- **`exports.json` is committed.** It is structure, not secrets — it declares which queries become which output files. It is the only switch that makes a query run; queries are never exported by default. Validate it before any run (the end user edits it).
- **Query references are in-memory and Decimal-safe.** `DEPENDS_ON` outputs are passed between queries as live DataFrames, never round-tripped through a file, so `Decimal` precision is preserved. The new CSV writer renders `Decimal` as exact strings; xlsx is float64 + Decimal display format (Excel has no decimal type). If you touch the exporter, keep a precision regression test for **both** writers.
- **Read-only on SQL.** `read_sql` is the only DB function and it's only ever called for SELECTs. Don't add write paths.

## Stack

- Package manager: `uv` (`uv sync`, `uv run pytest`, `uv run python run.py …`)
- Python 3.11+
- Polars + openpyxl (xlsx write) + calamine (xlsx read) + pyodbc (MSSQL) + pytest

## Common commands

```bash
uv sync                                      # install deps
uv run pytest                                # full test suite
uv run pytest functions/tests/test_transforms.py -q  # one file
uv run python run.py --all --output ./output # production run
uv run python run.py --query region_summary --output ./output
uv run python run.py --all --test-only       # fixture tests, no I/O
uv run python run.py --query region_summary --test-only
```

## Layout reference

```
engine/      # framework — developer mode only
  loader.py exporter.py export_config.py runner.py tester.py validator.py logger.py settings.py
functions/   # shared vocabulary — developer mode (extend over time)
  aggregations.py transforms.py joins.py _rounding.py  # _rounding: hardcoded half-up Decimal helper
queries/     # user mode — one folder per query
  region_base/       # reference COMPONENT query (not exported; only depended upon)
  region_summary/    # reference DELIVERABLE that DEPENDS_ON region_base
  activity_hours/    # reference DELIVERABLE — jsonl sources, joins, aggregations
run.py       # CLI entry point
exports.json         # committed — which queries become which output files
settings.json        # committed — finance policy (decimal_places); rounding is hardcoded half-up
config.example.json  # shared reference; real config.json is gitignored
```

## When in doubt

- Reach for the reference queries (`region_base` + `region_summary` for composition, `activity_hours` for joins/aggregations) for worked examples.
- If a request blurs the two modes (e.g. "this query needs a function we don't have"), do the developer-mode change as its own commit first, then the user-mode change as a follow-up. Don't entangle them.
