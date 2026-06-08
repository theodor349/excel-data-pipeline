## Project Summary

This is a Python pipeline replacing an Excel/Power Query workflow for finance reporting. It reads Excel and MSSQL sources, transforms data through composable queries, and writes Excel/CSV outputs for Power BI consumption.

## Target Audience

The target user is not a developer. They are a domain expert who can describe
business logic, review sample rows, and sanity-check output. Write docs
and query-author guidance in plain language, using Power Query / Excel concepts
where helpful.

When creating or changing queries, the agent handles the code. The user must
provide or confirm known-good expected values for tests.

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
- Communicate in business terms first: sources, columns, filters, joins, calculations, grouping, and expected output.
- Queries must call named functions only. Do not import Polars in `query.py`; do not call `pl.*`, `.with_columns`, `.dt.*`, `.cast`, or `.sort` directly.
- If a needed operation is missing, switch to Developer Mode first and add a small named tested function.
- Keep `load()` for sources only and `run(data)` for transforms only.
- `run(data)` returns a single DataFrame.
- Use `DEPENDS_ON = ["other_query"]` to consume another query output.
- Query tests use non-empty `TESTS = [...]`, with each case defining `name`, `FIXTURES`, and `EXPECTED`.
- Do not invent expected finance output. Ask the user for known-good expected values before encoding expected CSVs.

## Critical Invariants

- Queries use shared named functions only.
- Shared functions must be tested.
- Preserve money as `Decimal` end to end.
- Use `Decimal(str(value))`, never `Decimal(value)`.
- Rounding is hardcoded half-up; only decimal places are configurable.
- `settings.json` is committed finance policy; `exports.json` is committed run policy.
- `config.json` is gitignored and must not be committed.
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
