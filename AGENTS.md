## Project Summary

This is a Python pipeline replacing an Excel/Power Query workflow for finance reporting. It reads Excel and MSSQL sources, transforms data through composable queries, and writes Excel/CSV outputs for Power BI consumption.

## Working Modes

Figure out which mode applies before editing.

### Developer Mode

Use this when changing the framework or shared vocabulary.

- Touch: `engine/`, `functions/`, `pyproject.toml`, `config.example.json`, `run.py`, top-level docs.
- Do not touch user queries except the reference queries: `queries/region_base`, `queries/region_summary`, `queries/activity_hours`.
- Every shared function needs a unit test under `functions/tests/`.
- Every engine module change needs coverage under `engine/tests/`.
- Money-touching changes need exact `Decimal` precision regression tests.
- Run `uv run pytest` before declaring work complete.

### Query Author Mode

Use this when helping the end user create or modify a report query.

- Touch only the relevant `queries/<query_name>/` folder, plus `exports.json` when the query should produce an output file.
- Queries must call named functions only. Do not import Polars in `query.py`; do not call `pl.*`, `.with_columns`, `.dt.*`, `.cast`, or `.sort` directly.
- If a needed operation is missing, switch to Developer Mode first and add a small named tested function.
- Keep `load()` for sources only and `run(data)` for transforms only.
- `run(data)` returns a single DataFrame.
- Use `DEPENDS_ON = ["other_query"]` to consume another query output.
- Query tests use non-empty `TESTS = [...]`, with each case defining `name`, `FIXTURES`, and `EXPECTED`.
- Do not invent expected finance output. Ask the user for known-good expected values before encoding expected CSVs.

## Critical Invariants

- Functions-only queries; every function is tested.
- Preserve money as `Decimal` end to end.
- Use `Decimal(str(value))`, never `Decimal(value)`.
- Rounding is hardcoded half-up; only decimal places are configurable.
- `settings.json` is committed finance policy.
- `config.json` is gitignored and must not be committed.
- `exports.json` is committed and controls which queries run.
- SQL support is read-only.

## Commands

```bash
uv sync
uv run pytest
uv run pytest functions/tests/test_transforms.py -q
uv run python run.py --all --output ./output
uv run python run.py --query region_summary --output ./output
uv run python run.py --all --test-only
uv run python run.py --query region_summary --test-only
```

## Useful References

- `README.md`: running the pipeline.
- `QUERIES.md`: user-facing query-author workflow.
- `queries/region_base` and `queries/region_summary`: composition examples.
- `queries/activity_hours`: joins and aggregations example.
