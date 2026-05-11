import textwrap
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from engine.tester import test_all as run_tests_all, test_one as run_tests_one


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def _make_query(
    queries_dir: Path,
    name: str,
    query_py: str,
    test_py: str,
    fixtures: dict[str, str],
    expected_files: dict[str, str],
) -> Path:
    folder = queries_dir / name
    _write(folder / "query.py", query_py)
    _write(folder / "test.py", test_py)
    for fname, body in fixtures.items():
        _write(folder / "testData" / fname, body)
    for fname, body in expected_files.items():
        _write(folder / "testData" / fname, body)
    return folder


def test_passing_query(tmp_path, capsys):
    _make_query(
        tmp_path,
        "trivial",
        query_py="""
            import polars as pl
            def load():
                raise RuntimeError("should not be called")

            def run(data):
                return {"Out": data["src"].with_columns((pl.col("x") * 2).alias("y"))}
        """,
        test_py="""
            FIXTURES = {"src": "testData/src.csv"}
            EXPECTED = {"Out": "testData/expected.csv"}
        """,
        fixtures={"src.csv": "x\n1\n2\n3\n"},
        expected_files={"expected.csv": "x,y\n1,2\n2,4\n3,6\n"},
    )
    rc = run_tests_one(tmp_path, "trivial")
    out = capsys.readouterr().out
    assert rc == 0
    assert "[OK] trivial" in out


def test_failing_query_shows_cell_mismatch(tmp_path, capsys):
    _make_query(
        tmp_path,
        "broken",
        query_py="""
            import polars as pl
            def load(): raise RuntimeError
            def run(data):
                return {"Out": data["src"].with_columns((pl.col("x") * 2).alias("y"))}
        """,
        test_py="""
            FIXTURES = {"src": "testData/src.csv"}
            EXPECTED = {"Out": "testData/expected.csv"}
        """,
        fixtures={"src.csv": "x\n1\n2\n"},
        expected_files={"expected.csv": "x,y\n1,2\n2,99\n"},
    )
    rc = run_tests_one(tmp_path, "broken")
    out = capsys.readouterr().out
    assert rc == 1
    assert "[FAILED] broken" in out
    assert 'column "y" row 1' in out


def test_multiple_sheets_one_passes_one_fails(tmp_path, capsys):
    _make_query(
        tmp_path,
        "multi",
        query_py="""
            import polars as pl
            def load(): raise RuntimeError
            def run(data):
                return {
                    "A": pl.DataFrame({"v": [1, 2]}),
                    "B": pl.DataFrame({"v": [3, 4]}),
                }
        """,
        test_py="""
            FIXTURES = {}
            EXPECTED = {
                "A": "testData/expected_a.csv",
                "B": "testData/expected_b.csv",
            }
        """,
        fixtures={},
        expected_files={
            "expected_a.csv": "v\n1\n2\n",
            "expected_b.csv": "v\n3\n5\n",
        },
    )
    rc = run_tests_one(tmp_path, "multi")
    out = capsys.readouterr().out
    assert rc == 1
    assert 'sheet "B"' in out
    assert 'column "v" row 1' in out


def test_decimal_money_round_trip(tmp_path, capsys):
    _make_query(
        tmp_path,
        "money",
        query_py="""
            from functions.transforms import to_decimal
            def load(): raise RuntimeError
            def run(data):
                df = to_decimal(data["src"], "amount", places=2)
                return {"Out": df}
        """,
        test_py="""
            FIXTURES = {"src": "testData/src.csv"}
            EXPECTED = {"Out": "testData/expected.csv"}
        """,
        fixtures={"src.csv": "amount\n100.50\n200.25\n"},
        expected_files={"expected.csv": "amount\n100.50\n200.25\n"},
    )
    rc = run_tests_one(tmp_path, "money")
    out = capsys.readouterr().out
    assert rc == 0, out


def test_test_all_returns_one_if_any_fail(tmp_path, capsys):
    _make_query(
        tmp_path,
        "good",
        query_py="""
            import polars as pl
            def load(): raise RuntimeError
            def run(data): return {"Out": pl.DataFrame({"v": [1]})}
        """,
        test_py="""
            FIXTURES = {}
            EXPECTED = {"Out": "testData/exp.csv"}
        """,
        fixtures={},
        expected_files={"exp.csv": "v\n1\n"},
    )
    _make_query(
        tmp_path,
        "bad",
        query_py="""
            import polars as pl
            def load(): raise RuntimeError
            def run(data): return {"Out": pl.DataFrame({"v": [1]})}
        """,
        test_py="""
            FIXTURES = {}
            EXPECTED = {"Out": "testData/exp.csv"}
        """,
        fixtures={},
        expected_files={"exp.csv": "v\n2\n"},
    )
    rc = run_tests_all(tmp_path)
    out = capsys.readouterr().out
    assert rc == 1
    assert "[OK] good" in out
    assert "[FAILED] bad" in out


def test_test_all_returns_zero_when_all_pass(tmp_path, capsys):
    _make_query(
        tmp_path,
        "ok1",
        query_py="""
            import polars as pl
            def load(): raise RuntimeError
            def run(data): return {"Out": pl.DataFrame({"v": [1]})}
        """,
        test_py="""
            FIXTURES = {}
            EXPECTED = {"Out": "testData/exp.csv"}
        """,
        fixtures={},
        expected_files={"exp.csv": "v\n1\n"},
    )
    rc = run_tests_all(tmp_path)
    assert rc == 0


def test_test_one_unknown_query(tmp_path, capsys):
    rc = run_tests_one(tmp_path, "does_not_exist")
    out = capsys.readouterr().out
    assert rc == 1
    assert "does_not_exist" in out


def test_load_is_never_called(tmp_path, capsys):
    _make_query(
        tmp_path,
        "no_load",
        query_py="""
            import polars as pl
            def load():
                raise RuntimeError("load() must not be called during tests")
            def run(data):
                return {"Out": pl.DataFrame({"v": [1]})}
        """,
        test_py="""
            FIXTURES = {}
            EXPECTED = {"Out": "testData/exp.csv"}
        """,
        fixtures={},
        expected_files={"exp.csv": "v\n1\n"},
    )
    rc = run_tests_one(tmp_path, "no_load")
    out = capsys.readouterr().out
    assert rc == 0, out
