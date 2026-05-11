# excel-data-pipeline

Python replacement for an Excel/Power Query workflow. See `pipeline-design-doc.md` for the architecture.

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
uv run python run.py --query example --output ./output

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
