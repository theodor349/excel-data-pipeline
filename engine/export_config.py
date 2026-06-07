"""Parsing and validation of the committed `exports.json` file.

`exports.json` is structure, not secrets, so (unlike `config.json`) it is
committed. It declares which queries become which output files. Queries are
never exported by default — only those reachable from this file (plus their
`DEPENDS_ON` closure) ever run.

The end user edits this file, so every validation error must read clearly.
"""

import json
from dataclasses import dataclass
from pathlib import Path

# Excel sheet-name rules — shared with the exporter.
_INVALID_SHEET_CHARS = frozenset(r"/\?*[]:")
_MAX_SHEET_NAME_LEN = 31


def _validate_sheet_name(name: str) -> None:
    if len(name) > _MAX_SHEET_NAME_LEN:
        raise ValueError(
            f"Sheet name '{name}' exceeds {_MAX_SHEET_NAME_LEN} characters"
        )
    bad = _INVALID_SHEET_CHARS & set(name)
    if bad:
        raise ValueError(
            f"Sheet name '{name}' contains invalid Excel characters: {bad}"
        )


@dataclass(frozen=True)
class Output:
    """One output file declared in `exports.json`."""

    filename: str
    format: str  # "xlsx" | "csv"
    # xlsx: sheet name -> query name (>= 1 entry). None for csv.
    sheets: dict[str, str] | None = None
    # csv: the single query name. None for xlsx.
    query: str | None = None

    def query_names(self) -> set[str]:
        if self.format == "xlsx":
            return set(self.sheets.values())
        return {self.query}


@dataclass(frozen=True)
class ExportConfig:
    outputs: list[Output]


class ExportConfigError(ValueError):
    """Raised when exports.json is missing or malformed. Message is user-facing."""


def referenced_queries(config: ExportConfig) -> set[str]:
    """All query names any output needs."""
    names: set[str] = set()
    for out in config.outputs:
        names |= out.query_names()
    return names


def load_export_config(path: str | Path) -> ExportConfig:
    """Parse and structurally validate `exports.json`.

    Validates: file exists and is JSON; each output has a known format; xlsx has
    a non-empty `sheets` map with valid Excel sheet names; csv has a `query`;
    filenames are unique. It does NOT check that referenced queries exist — the
    runner does that once it has discovered the available queries.
    """
    path = Path(path)
    if not path.is_file():
        raise ExportConfigError(
            f"exports.json not found at {path}. It must exist at the repo root "
            f"and declare which queries become output files."
        )

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ExportConfigError(f"exports.json is not valid JSON: {e}") from e

    if not isinstance(raw, dict) or "outputs" not in raw:
        raise ExportConfigError(
            "exports.json must be an object with an 'outputs' array."
        )
    raw_outputs = raw["outputs"]
    if not isinstance(raw_outputs, list) or not raw_outputs:
        raise ExportConfigError("exports.json 'outputs' must be a non-empty array.")

    outputs: list[Output] = []
    seen_filenames: set[str] = set()

    for i, item in enumerate(raw_outputs):
        where = f"outputs[{i}]"
        if not isinstance(item, dict):
            raise ExportConfigError(f"{where} must be an object.")

        filename = item.get("filename")
        if not isinstance(filename, str) or not filename:
            raise ExportConfigError(f"{where} is missing a non-empty 'filename'.")
        if filename in seen_filenames:
            raise ExportConfigError(
                f"duplicate output filename '{filename}' in exports.json."
            )
        seen_filenames.add(filename)

        fmt = item.get("format")
        if fmt not in ("xlsx", "csv"):
            raise ExportConfigError(
                f"{where} ('{filename}') has unknown format {fmt!r}; "
                f"expected 'xlsx' or 'csv'."
            )

        if fmt == "xlsx":
            sheets = item.get("sheets")
            if not isinstance(sheets, dict) or not sheets:
                raise ExportConfigError(
                    f"{where} ('{filename}') is xlsx and needs a non-empty "
                    f"'sheets' map (sheet name -> query name)."
                )
            for sheet_name, query_name in sheets.items():
                try:
                    _validate_sheet_name(sheet_name)
                except ValueError as e:
                    raise ExportConfigError(f"{where} ('{filename}'): {e}") from e
                if not isinstance(query_name, str) or not query_name:
                    raise ExportConfigError(
                        f"{where} ('{filename}') sheet '{sheet_name}' must map to "
                        f"a non-empty query name."
                    )
            if "query" in item:
                raise ExportConfigError(
                    f"{where} ('{filename}') is xlsx; use 'sheets', not 'query'."
                )
            outputs.append(Output(filename=filename, format="xlsx", sheets=dict(sheets)))
        else:  # csv
            query_name = item.get("query")
            if not isinstance(query_name, str) or not query_name:
                raise ExportConfigError(
                    f"{where} ('{filename}') is csv and needs a single "
                    f"non-empty 'query' name."
                )
            if "sheets" in item:
                raise ExportConfigError(
                    f"{where} ('{filename}') is csv; use 'query', not 'sheets'."
                )
            outputs.append(Output(filename=filename, format="csv", query=query_name))

    return ExportConfig(outputs=outputs)
