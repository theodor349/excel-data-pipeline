import datetime
import importlib.util
import logging
import math
from decimal import Decimal
from pathlib import Path

import polars as pl

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


def _read_fixture(path: Path) -> pl.DataFrame:
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
    # Decimal vs numeric/string: coerce to Decimal for exact comparison.
    if isinstance(actual, Decimal):
        if isinstance(expected, (int, float)):
            return actual == Decimal(str(expected))
        if isinstance(expected, str):
            try:
                return actual == Decimal(expected)
            except Exception:
                return False
    if isinstance(expected, Decimal):
        if isinstance(actual, (int, float)):
            return Decimal(str(actual)) == expected
        if isinstance(actual, str):
            try:
                return Decimal(actual) == expected
            except Exception:
                return False
    if isinstance(actual, float) and isinstance(expected, float):
        return abs(actual - expected) <= _FLOAT_TOLERANCE
    if isinstance(actual, datetime.date) and isinstance(expected, str):
        return str(actual) == expected
    if isinstance(expected, datetime.date) and isinstance(actual, str):
        return actual == str(expected)
    return actual == expected


def _compare(actual: pl.DataFrame, expected: pl.DataFrame, label: str) -> list[str]:
    mismatches = []
    if len(actual) != len(expected):
        mismatches.append(
            f'  query "{label}": row count: expected {len(expected)}, actual {len(actual)}'
        )
        return mismatches
    if list(actual.columns) != list(expected.columns):
        mismatches.append(
            f'  query "{label}": columns: expected {list(expected.columns)}, '
            f"actual {list(actual.columns)}"
        )
        return mismatches
    for col in expected.columns:
        for i in range(len(expected)):
            a = actual[col][i]
            e = expected[col][i]
            if not _cells_equal(a, e):
                mismatches.append(
                    f'  query "{label}": column "{col}" row {i}: expected {e!r}, actual {a!r}'
                )
    return mismatches


def _run_one_case(
    name: str,
    folder: Path,
    query_mod,
    depends_on: list[str],
    case: dict,
    case_label: str,
) -> tuple[str, list[str]]:
    if not isinstance(case, dict):
        return "failed", [f"  {case_label}: each TESTS entry must be a dict"]

    fixtures = case.get("FIXTURES", {})
    expected = case.get("EXPECTED")

    if not isinstance(fixtures, dict):
        return "failed", [f"  {case_label}: FIXTURES must be a dict of source -> path"]
    if not isinstance(expected, str):
        return "failed", [
            f"  {case_label}: EXPECTED must be a single path string to the "
            f"expected-output CSV"
        ]

    # DEPENDS_ON queries are supplied as canned fixtures, never re-executed —
    # otherwise the test starts depending on the upstream query's sources.
    missing = [d for d in depends_on if d not in fixtures]
    if missing:
        return "failed", [
            f"  {case_label}: DEPENDS_ON {missing} has no matching FIXTURES entry — "
            f"supply a canned upstream-output CSV for each dependency"
        ]

    data = {}
    for source_name, rel_path in fixtures.items():
        data[source_name] = _read_fixture(folder / rel_path)

    result = query_mod.run(data)
    if not isinstance(result, pl.DataFrame):
        return "failed", [
            f"  {case_label}: run(data) must return a single polars DataFrame, got "
            f"{type(result).__name__}"
        ]

    expected_df = _read_fixture(folder / expected)
    mismatches = _compare(result, expected_df, case_label)
    if mismatches:
        return "failed", mismatches
    return "ok", []


def _test_one_query(name: str, folder: Path, log: logging.Logger) -> tuple[str, list[str]]:
    log.info("testing query %s", name)
    try:
        test_mod = _load_module(f"queries.{name}.test", folder / "test.py")
        tests = getattr(test_mod, "TESTS", None)

        if tests is None:
            return "failed", [
                "  test.py must define TESTS = [...], a list of test cases. Each case "
                'is a dict with "name", "FIXTURES", and "EXPECTED" keys.'
            ]
        if not isinstance(tests, list) or not tests:
            return "failed", ["  TESTS must be a non-empty list of test-case dicts"]

        query_mod = _load_module(f"queries.{name}.query", folder / "query.py")
        depends_on = getattr(query_mod, "DEPENDS_ON", [])

        all_mismatches = []
        for i, case in enumerate(tests):
            case_name = case.get("name") if isinstance(case, dict) else None
            case_label = f'{name} / {case_name or f"test {i}"}'
            status, mismatches = _run_one_case(
                name, folder, query_mod, depends_on, case, case_label
            )
            if status != "ok":
                all_mismatches.extend(mismatches)

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
