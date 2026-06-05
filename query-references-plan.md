# Implementation Plan — Query References & Config-Driven Export

## Goal

Let queries reference other queries so the user can build a portfolio of small,
reusable component queries and compose them into larger ones. A query that is
split into sub-queries should be able to consume those sub-queries by name, and
those sub-queries should be reusable by any number of other queries.

This is delivered through three coupled changes:

1. **Single-table query contract** — `run(data)` returns one DataFrame, not a
   sheet dict.
2. **`DEPENDS_ON`** — a query declares the other queries it consumes; their
   output tables are injected into its `data` dict, exactly like named sources.
3. **Config-driven export (`exports.json`)** — queries are never exported by
   default. A committed export definition says which queries become which files,
   in which format (CSV = one query; XLSX = sheet→query map). The runner only
   executes queries reachable from `exports.json` plus their `DEPENDS_ON`
   closure; everything else is pruned.

This is a **breaking framework change** (developer mode). It lands as its own
tested commit, then the two existing queries are migrated, then a worked
component-query example is added.

---

## Confirmed design decisions

- A query's `run(data)` returns a **single** `pl.DataFrame`.
- A reference is `data["other_query"]` — the table that query produced.
- All queries live in `queries/`; there is **no** component folder and **no**
  per-query export flag. "Component" vs "deliverable" is decided solely by what
  references a query.
- `exports.json` lives at repo root and is **committed** (it is structure, not
  secrets — unlike the gitignored `config.json`).
- Queries are passed between each other **in memory** (preserves `Decimal`; no
  round-trip through Excel).
- A query reachable from neither `exports.json` nor any `DEPENDS_ON` is silently
  skipped but logged as skipped.
- Cyclic `DEPENDS_ON` is a hard error that fails the run before any query
  executes.
- `run.py --all` = "produce everything in `exports.json`". `--query <name>` runs
  one query plus its dependency closure (debug aid) and writes any export files
  that depend only on the executed set.

---

## New artifacts & contracts

### Query contract (changed)

```python
# queries/<name>/query.py
DEPENDS_ON = ["base_sales"]          # optional; default [] if absent

def load():                          # real sources only (I/O)
    return {"regions": read_excel("regions", "Sheet1")}

def run(data):                       # pure; no I/O
    base    = data["base_sales"]     # upstream query's single output table
    regions = data["regions"]
    ...
    return summary                   # ONE pl.DataFrame
```

### `exports.json` (new, committed)

```json
{
  "outputs": [
    {
      "filename": "region_report.xlsx",
      "format": "xlsx",
      "sheets": { "Summary": "region_summary", "By Month": "region_monthly" }
    },
    {
      "filename": "fx_rates.csv",
      "format": "csv",
      "query": "fx_rates_clean"
    }
  ]
}
```

- `format: "xlsx"` requires `sheets` (sheet name → query name; ≥1 entry).
- `format: "csv"` requires `query` (single query name).
- Every referenced query name must exist in `queries/`; validated before any run.

### Test contract (changed)

```python
# queries/<name>/test.py
FIXTURES = {                         # sources AND DEPENDS_ON outputs, by name
    "regions":    "testData/regions.csv",
    "base_sales": "testData/base_sales_output.csv",   # canned upstream output
}
EXPECTED = "testData/expected_region_summary.csv"      # single file, not a dict
```

A query is still tested in isolation: its dependencies are supplied as canned
fixtures and never re-run, preserving the finance rule that a test must not
merely prove the query agrees with itself.

---

## Phase 1 — Engine (developer mode, one tested commit)

### 1.1 `engine/export_config.py` (new)
- `load_export_config(path) -> ExportConfig`: parse + validate `exports.json`.
- Validate: known `format`; xlsx has non-empty `sheets`; csv has `query`;
  unique `filename`s; valid Excel sheet names (reuse `_validate_sheet_name`
  logic, move it here or to a shared util); referenced query names exist.
- `referenced_queries(config) -> set[str]`: all query names any output needs.
- Clear, user-readable errors (the user edits this file).

### 1.2 `engine/runner.py` (rewrite execution model)
- Read `DEPENDS_ON` (default `[]`) from each discovered query module.
- Build the dependency DAG.
- **Cycle detection** → hard error listing the cycle; nothing runs.
- **Reachability pruning**: execution set = `referenced_queries(exports.json)`
  ∪ transitive `DEPENDS_ON`. Log every query that is skipped (not reachable).
- **Topological order**; run independent queries concurrently in dependency
  waves (replaces the current run-everything-at-once `as_completed` pool).
- **In-memory result cache**: each query runs once; its output table is injected
  into the `data` dict of every dependent (merged with that dependent's
  `load()` sources). Cross-process sharing: pass upstream outputs as args to the
  worker, or keep results in the parent — must pickle (polars DataFrames do).
- **Failure propagation**: a query whose dependency failed is `skipped`
  (new status), not run against missing inputs.
- After queries succeed, hand the result cache to the exporter, which writes
  files per `exports.json`.
- `summary.json` extended: per-query `ok | failed | skipped` (+ reason), and a
  new per-output-file section `written | failed` (+ reason). An output file
  whose query failed/was skipped is not written and is marked failed.
- Exit non-zero if any query failed/was skipped-due-to-failure or any output
  file failed.
- `run_one` runs the named query + its dependency closure; writes any export
  file whose queries are all in the executed set.

### 1.3 `engine/exporter.py` (rewrite entry point)
- New `export_outputs(results: dict[str, pl.DataFrame], config, output_folder)`:
  iterate `exports.json` outputs; build each file from the result cache.
- Keep the existing xlsx writer internals (Decimal-aware number format, atomic
  temp-then-rename, openpyxl). `sheets` now maps sheet name → the result table
  of the named query.
- Add a **CSV writer**: atomic temp-then-rename; write `Decimal` columns as
  exact decimal strings (never via float) to preserve precision; UTF-8.
- Preserve the "target open in Power BI" behavior: temp write succeeds, rename
  fails loudly; logged and recorded in `summary.json`.
- Keep the single-DataFrame, multi-output semantics — one query can feed many
  files / sheets.

### 1.4 `engine/tester.py` (adjust contract)
- `EXPECTED` is now a single path (compare `run(data)`'s single DataFrame to it)
  rather than a sheet dict. Keep Decimal-aware `_cells_equal` / `_compare`.
- `FIXTURES` may include `DEPENDS_ON` names; they are loaded as fixtures and
  injected into `data`. Dependencies are **not** executed during tests.
- Optional: warn if a `DEPENDS_ON` entry has no matching `FIXTURES` key.

### 1.5 `engine/validator.py`
- No change to `expect_columns` / `expect_non_empty`. Queries can (and should)
  validate injected dependency tables the same way they validate sources.

### 1.6 `run.py`
- Locate `exports.json` at repo root; pass to `run_all` / `run_one`.
- `--all` now means "produce everything in `exports.json`".
- Keep `--query`, `--output`, `--test-only`.
- Error clearly if `exports.json` is missing/invalid on a non-test run.

### 1.7 Engine tests (`engine/tests/`)
- `test_export_config.py`: valid/invalid configs, missing query refs, dup
  filenames, bad sheet names.
- `runner` tests: topo order; cycle detection; reachability pruning (unreferenced
  query never runs); dependency-failure → dependent `skipped`; output-file status.
- `exporter` tests: xlsx multi-sheet from multiple queries; csv output; Decimal
  preserved in **both** xlsx and csv (precision regression — e.g. 1000 ×
  `Decimal("0.10")` summed → exact `Decimal("100.00")` through the writer).
- `tester` tests: single-`EXPECTED` compare; `DEPENDS_ON` satisfied by fixtures.

**Gate:** `uv run pytest` fully green before moving on.

---

## Phase 2 — Migrate existing queries to the new contract

Existing queries return sheet dicts; the example `test.py` uses dict `EXPECTED`.
Both must move to single-table output, and an `exports.json` must reproduce
today's output files so nothing regresses.

### 2.1 `queries/example/`
- `query.py`: `return {"Summary": summary}` → `return summary`.
- `test.py`: `EXPECTED = {"Summary": ".../expected_summary.csv"}` →
  `EXPECTED = "testData/expected_summary.csv"`.

### 2.2 `queries/activity_hours/`
- `query.py`: `return {"ActivityHours": result}` → `return result`.
- `test.py`: `EXPECTED = {"ActivityHours": ...}` → single path.

### 2.3 `exports.json` (reproduce current outputs)
```json
{
  "outputs": [
    { "filename": "example.xlsx",        "format": "xlsx",
      "sheets": { "Summary": "example" } },
    { "filename": "activity_hours.xlsx", "format": "xlsx",
      "sheets": { "ActivityHours": "activity_hours" } }
  ]
}
```

**Gate:** `uv run pytest` green; `uv run python run.py --all --output ./output`
produces the same `example.xlsx` / `activity_hours.xlsx` as before;
`--test-only` passes.

---

## Phase 3 — Worked component-query example

Demonstrate referencing end to end so the pattern is teachable (and so
`QUERIES.md` has something to point at).

- Add a small component query, e.g. `queries/region_base/` that normalizes +
  aggregates a shared base table and returns one DataFrame.
- Add `queries/region_summary/` with `DEPENDS_ON = ["region_base"]` consuming
  `data["region_base"]`.
- `region_summary/test.py`: `FIXTURES` includes a canned `region_base` output
  CSV; `EXPECTED` is the user-computed result (per the finance rule — user
  computes expected values, agent encodes them).
- Extend `exports.json` so `region_summary` is exported and `region_base` is
  **not** directly exported — proving a component query runs only because it is
  depended upon.

**Gate:** `uv run pytest`; full run produces the report; intentionally breaking a
dependency shows the dependent `skipped` in `summary.json`.

---

## Phase 4 — Documentation

- `pipeline-design-doc.md`: replace the per-query-xlsx output model with the
  single-table contract + `exports.json`; document `DEPENDS_ON`, the DAG,
  pruning, cycle errors, and the new `summary.json` statuses. Fold in the
  realized "Parallelism" / "DEPENDS_ON" future-considerations notes.
- `CLAUDE.md`: update the query contract (single table), add `exports.json` to
  invariants, note that referencing is in-memory and Decimal-safe, and that
  adding a dependency does not change the two-mode rules.
- `QUERIES.md`: user-facing guide to splitting a query into components, wiring
  `DEPENDS_ON`, supplying a canned upstream fixture in tests, and adding an
  entry to `exports.json`.
- `config.example.json` unchanged; add a committed `exports.json` example (the
  Phase 2 file serves as the reference).

---

## Risks & invariants to guard

- **Decimal end-to-end.** In-memory references are safe, but the new CSV writer
  is a fresh float-widening risk — write `Decimal` as exact strings and add a
  precision regression test for CSV and xlsx alike.
- **Test isolation.** Dependencies must be canned fixtures in tests, never
  re-executed — otherwise a query's test starts depending on its upstream's
  sources and the "agrees with itself" failure mode returns.
- **Cross-process result passing.** The current `ProcessPoolExecutor` model must
  now move upstream outputs to downstream workers (or collapse to in-parent
  execution). Verify polars DataFrames with `Decimal` columns survive pickling
  exactly.
- **Cycle & missing-reference errors** must be clear and pre-execution — the
  non-technical user will hit these while composing queries.
- **No silent partial files.** An output file whose query failed/was skipped is
  not written; it is marked failed in `summary.json` and the run exits non-zero.

---

## Sequencing summary

1. Phase 1 — engine change + engine tests (one commit). Gate: pytest green.
2. Phase 2 — migrate `example` + `activity_hours`, add `exports.json`. Gate:
   same outputs, pytest + `--test-only` green.
3. Phase 3 — component-query worked example. Gate: referencing works, pruning &
   skip-on-failure demonstrated.
4. Phase 4 — docs (`pipeline-design-doc.md`, `CLAUDE.md`, `QUERIES.md`).
