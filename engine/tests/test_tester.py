import textwrap
from pathlib import Path

from engine.tester import test_all as run_tests_all, test_one as run_tests_one


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def _make_query(
    queries_dir: Path,
    name: str,
    query_py: str,
    test_py: str,
    data_files: dict[str, str],
) -> Path:
    folder = queries_dir / name
    _write(folder / "query.py", query_py)
    _write(folder / "test.py", test_py)
    for fname, body in data_files.items():
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
                return data["src"].with_columns((pl.col("x") * 2).alias("y"))
        """,
        test_py="""
            FIXTURES = {"src": "testData/src.csv"}
            EXPECTED = "testData/expected.csv"
        """,
        data_files={
            "src.csv": "x\n1\n2\n3\n",
            "expected.csv": "x,y\n1,2\n2,4\n3,6\n",
        },
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
                return data["src"].with_columns((pl.col("x") * 2).alias("y"))
        """,
        test_py="""
            FIXTURES = {"src": "testData/src.csv"}
            EXPECTED = "testData/expected.csv"
        """,
        data_files={
            "src.csv": "x\n1\n2\n",
            "expected.csv": "x,y\n1,2\n2,99\n",
        },
    )
    rc = run_tests_one(tmp_path, "broken")
    out = capsys.readouterr().out
    assert rc == 1
    assert "[FAILED] broken" in out
    assert 'column "y" row 1' in out


def test_dependency_supplied_as_fixture(tmp_path, capsys):
    # A DEPENDS_ON query is read from a canned fixture, never re-executed.
    _make_query(
        tmp_path,
        "consumer",
        query_py="""
            import polars as pl
            DEPENDS_ON = ["base"]
            def load(): raise RuntimeError
            def run(data):
                return data["base"].with_columns((pl.col("v") + 1).alias("w"))
        """,
        test_py="""
            FIXTURES = {"base": "testData/base.csv"}
            EXPECTED = "testData/expected.csv"
        """,
        data_files={
            "base.csv": "v\n10\n20\n",
            "expected.csv": "v,w\n10,11\n20,21\n",
        },
    )
    rc = run_tests_one(tmp_path, "consumer")
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "[OK] consumer" in out


def test_dependency_without_fixture_is_hard_error(tmp_path, capsys):
    _make_query(
        tmp_path,
        "consumer",
        query_py="""
            import polars as pl
            DEPENDS_ON = ["base"]
            def load(): raise RuntimeError
            def run(data): return data["base"]
        """,
        test_py="""
            FIXTURES = {}
            EXPECTED = "testData/expected.csv"
        """,
        data_files={"expected.csv": "v\n1\n"},
    )
    rc = run_tests_one(tmp_path, "consumer")
    out = capsys.readouterr().out
    assert rc == 1
    assert "DEPENDS_ON" in out
    assert "base" in out


def test_expected_must_be_single_path(tmp_path, capsys):
    _make_query(
        tmp_path,
        "olddict",
        query_py="""
            import polars as pl
            def load(): raise RuntimeError
            def run(data): return pl.DataFrame({"v": [1]})
        """,
        test_py="""
            FIXTURES = {}
            EXPECTED = {"Out": "testData/exp.csv"}
        """,
        data_files={"exp.csv": "v\n1\n"},
    )
    rc = run_tests_one(tmp_path, "olddict")
    out = capsys.readouterr().out
    assert rc == 1
    assert "EXPECTED" in out


def test_decimal_money_round_trip(tmp_path, capsys):
    _make_query(
        tmp_path,
        "money",
        query_py="""
            from functions.transforms import to_decimal
            def load(): raise RuntimeError
            def run(data):
                return to_decimal(data["src"], "amount", places=2)
        """,
        test_py="""
            FIXTURES = {"src": "testData/src.csv"}
            EXPECTED = "testData/expected.csv"
        """,
        data_files={
            "src.csv": "amount\n100.50\n200.25\n",
            "expected.csv": "amount\n100.50\n200.25\n",
        },
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
            def run(data): return pl.DataFrame({"v": [1]})
        """,
        test_py="""
            FIXTURES = {}
            EXPECTED = "testData/exp.csv"
        """,
        data_files={"exp.csv": "v\n1\n"},
    )
    _make_query(
        tmp_path,
        "bad",
        query_py="""
            import polars as pl
            def load(): raise RuntimeError
            def run(data): return pl.DataFrame({"v": [1]})
        """,
        test_py="""
            FIXTURES = {}
            EXPECTED = "testData/exp.csv"
        """,
        data_files={"exp.csv": "v\n2\n"},
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
            def run(data): return pl.DataFrame({"v": [1]})
        """,
        test_py="""
            FIXTURES = {}
            EXPECTED = "testData/exp.csv"
        """,
        data_files={"exp.csv": "v\n1\n"},
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
                return pl.DataFrame({"v": [1]})
        """,
        test_py="""
            FIXTURES = {}
            EXPECTED = "testData/exp.csv"
        """,
        data_files={"exp.csv": "v\n1\n"},
    )
    rc = run_tests_one(tmp_path, "no_load")
    out = capsys.readouterr().out
    assert rc == 0, out
