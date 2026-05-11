import datetime
import importlib.util
import logging
import math
from decimal import Decimal
from pathlib import Path

import pandas as pd

from engine.loader import _read_csv_path, _read_excel_path

_FLOAT_TOLERANCE = 1e-9


def _discover_queries(queries_dir: Path) -> list[tuple[str, Path]]:
    results = []
    for entry in sorted(queries_dir.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        if name == "__pycache__" or name.startswith(".") or name.startswith("_"):
            continue
        if (entry / "query.py").is_file() and (entry / "test.py").is_file():
            results.append((name, entry))
    return results


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_fixture(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return _read_csv_path(path)
    if path.suffix.lower() == ".xlsx":
        return _read_excel_path(path, "Sheet1")
    raise ValueError(f"unsupported fixture extension: {path}")


def _cells_equal(actual, expected) -> bool:
    if actual is None or (isinstance(actual, float) and math.isnan(actual)):
        return expected is None or (isinstance(expected, float) and math.isnan(expected))
    if expected is None or (isinstance(expected, float) and math.isnan(expected)):
        return False
    # Decimal vs float: coerce expected float to Decimal via str() so plain CSV
    # values can compare exactly against Decimal-typed query output.
    if isinstance(actual, Decimal) and isinstance(expected, (int, float)):
        return actual == Decimal(str(expected))
    if isinstance(expected, Decimal) and isinstance(actual, (int, float)):
        return Decimal(str(actual)) == expected
    if isinstance(actual, float) and isinstance(expected, float):
        return abs(actual - expected) <= _FLOAT_TOLERANCE
    if isinstance(actual, datetime.date) and isinstance(expected, str):
        return str(actual) == expected
    if isinstance(expected, datetime.date) and isinstance(actual, str):
        return actual == str(expected)
    return actual == expected


def _compare(actual: pd.DataFrame, expected: pd.DataFrame, sheet: str) -> list[str]:
    mismatches = []
    if len(actual) != len(expected):
        mismatches.append(
            f'  sheet "{sheet}": row count: expected {len(expected)}, actual {len(actual)}'
        )
        return mismatches
    if list(actual.columns) != list(expected.columns):
        mismatches.append(
            f'  sheet "{sheet}": columns: expected {list(expected.columns)}, '
            f"actual {list(actual.columns)}"
        )
        return mismatches
    for col in expected.columns:
        for i in range(len(expected)):
            a = actual.iloc[i][col]
            e = expected.iloc[i][col]
            if not _cells_equal(a, e):
                mismatches.append(
                    f'  sheet "{sheet}": column "{col}" row {i}: expected {e!r}, actual {a!r}'
                )
    return mismatches


def _test_one_query(name: str, folder: Path, log: logging.Logger) -> tuple[str, list[str]]:
    log.info("testing query %s", name)
    try:
        test_mod = _load_module(f"queries.{name}.test", folder / "test.py")
        fixtures = getattr(test_mod, "FIXTURES", {})
        expected = getattr(test_mod, "EXPECTED", {})

        data = {}
        for source_name, rel_path in fixtures.items():
            data[source_name] = _read_fixture(folder / rel_path)

        query_mod = _load_module(f"queries.{name}.query", folder / "query.py")
        result = query_mod.run(data)

        all_mismatches = []
        for sheet_name, rel_path in expected.items():
            if sheet_name not in result:
                all_mismatches.append(
                    f'  sheet "{sheet_name}": missing from query output'
                )
                continue
            expected_df = _read_fixture(folder / rel_path)
            all_mismatches.extend(_compare(result[sheet_name], expected_df, sheet_name))

        if all_mismatches:
            return "failed", all_mismatches
        return "ok", []

    except Exception as e:
        return "failed", [f"  {type(e).__name__}: {e}"]


def _report(name: str, status: str, mismatches: list[str]) -> None:
    if status == "ok":
        print(f"[OK] {name}")
    else:
        print(f"[FAILED] {name}")
        for line in mismatches:
            print(line)


def test_all(queries_dir: str | Path) -> int:
    queries_dir = Path(queries_dir)
    log = logging.getLogger("pipeline")
    log.info("test run started: all queries in %s", queries_dir)

    any_failed = False
    for name, folder in _discover_queries(queries_dir):
        status, mismatches = _test_one_query(name, folder, log)
        _report(name, status, mismatches)
        if status != "ok":
            any_failed = True

    return 1 if any_failed else 0


def test_one(queries_dir: str | Path, query_name: str) -> int:
    queries_dir = Path(queries_dir)
    log = logging.getLogger("pipeline")
    log.info("test run started: single query '%s' in %s", query_name, queries_dir)

    folder = queries_dir / query_name
    if not (folder / "query.py").is_file() or not (folder / "test.py").is_file():
        print(f"[FAILED] {query_name} — query.py and/or test.py not found in {folder}")
        return 1

    status, mismatches = _test_one_query(query_name, folder, log)
    _report(query_name, status, mismatches)
    return 0 if status == "ok" else 1
