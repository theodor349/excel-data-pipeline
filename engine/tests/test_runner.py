import json
from pathlib import Path

import pandas as pd
import pytest

from engine.runner import run_all, run_one


def _make_query(queries_dir: Path, name: str, query_src: str) -> Path:
    query_folder = queries_dir / name
    query_folder.mkdir(parents=True, exist_ok=True)
    (query_folder / "query.py").write_text(query_src, encoding="utf-8")
    return query_folder


PASSING_QUERY_SRC = """\
import pandas as pd

def load():
    return {}

def run(data):
    return {"Out": pd.DataFrame({"x": [1, 2, 3]})}
"""

FAILING_QUERY_SRC = """\
import pandas as pd

def load():
    return {}

def run(data):
    raise RuntimeError("something broke")
"""

MISSING_RUN_QUERY_SRC = """\
import pandas as pd

def load():
    return {}
"""

KEYERROR_QUERY_SRC = """\
import pandas as pd

def load():
    return {"sales": pd.DataFrame({"amount": [10, 20]})}

def run(data):
    df = data["sales"]
    _ = df["nonexistent_column"]
    return {"Out": df}
"""


def _read_summary(output_folder: Path) -> dict:
    return json.loads((output_folder / "summary.json").read_text(encoding="utf-8"))


class TestRunAllTwoPassingQueries:
    def test_returns_zero(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        _make_query(queries_dir, "alpha", PASSING_QUERY_SRC)
        _make_query(queries_dir, "beta", PASSING_QUERY_SRC)

        result = run_all(queries_dir, output_folder)

        assert result == 0

    def test_both_xlsx_files_exist(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        _make_query(queries_dir, "alpha", PASSING_QUERY_SRC)
        _make_query(queries_dir, "beta", PASSING_QUERY_SRC)

        run_all(queries_dir, output_folder)

        assert (output_folder / "alpha.xlsx").exists()
        assert (output_folder / "beta.xlsx").exists()

    def test_summary_marks_both_ok(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        _make_query(queries_dir, "alpha", PASSING_QUERY_SRC)
        _make_query(queries_dir, "beta", PASSING_QUERY_SRC)

        run_all(queries_dir, output_folder)

        summary = _read_summary(output_folder)
        assert summary["queries"]["alpha"]["status"] == "ok"
        assert summary["queries"]["beta"]["status"] == "ok"

    def test_log_file_exists_in_logs_dir(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        _make_query(queries_dir, "alpha", PASSING_QUERY_SRC)
        _make_query(queries_dir, "beta", PASSING_QUERY_SRC)

        run_all(queries_dir, output_folder)

        logs_dir = output_folder / "logs"
        assert logs_dir.is_dir()
        assert len(list(logs_dir.glob("pipeline-*.log"))) == 1


class TestRunAllOnePassingOneFailing:
    def test_returns_one(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        _make_query(queries_dir, "good_query", PASSING_QUERY_SRC)
        _make_query(queries_dir, "bad_query", FAILING_QUERY_SRC)

        result = run_all(queries_dir, output_folder)

        assert result == 1

    def test_passing_xlsx_exists(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        _make_query(queries_dir, "good_query", PASSING_QUERY_SRC)
        _make_query(queries_dir, "bad_query", FAILING_QUERY_SRC)

        run_all(queries_dir, output_folder)

        assert (output_folder / "good_query.xlsx").exists()

    def test_summary_marks_each_correctly(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        _make_query(queries_dir, "good_query", PASSING_QUERY_SRC)
        _make_query(queries_dir, "bad_query", FAILING_QUERY_SRC)

        run_all(queries_dir, output_folder)

        summary = _read_summary(output_folder)
        assert summary["queries"]["good_query"]["status"] == "ok"
        assert summary["queries"]["bad_query"]["status"] == "failed"
        assert "reason" in summary["queries"]["bad_query"]

    def test_failing_query_traceback_in_log(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        _make_query(queries_dir, "good_query", PASSING_QUERY_SRC)
        _make_query(queries_dir, "bad_query", FAILING_QUERY_SRC)

        run_all(queries_dir, output_folder)

        log_file = next((output_folder / "logs").glob("pipeline-*.log"))
        content = log_file.read_text(encoding="utf-8")
        assert "Traceback" in content
        assert "RuntimeError" in content
        assert "something broke" in content


class TestRunAllMissingRunFunction:
    def test_missing_run_is_failure(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        _make_query(queries_dir, "no_run", MISSING_RUN_QUERY_SRC)

        result = run_all(queries_dir, output_folder)

        assert result == 1

    def test_missing_run_reason_in_summary(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        _make_query(queries_dir, "no_run", MISSING_RUN_QUERY_SRC)

        run_all(queries_dir, output_folder)

        summary = _read_summary(output_folder)
        assert summary["queries"]["no_run"]["status"] == "failed"
        reason = summary["queries"]["no_run"]["reason"]
        assert "run" in reason.lower()


class TestRunOne:
    def test_known_query_returns_zero(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        _make_query(queries_dir, "target", PASSING_QUERY_SRC)
        _make_query(queries_dir, "other", PASSING_QUERY_SRC)

        result = run_one(queries_dir, "target", output_folder)

        assert result == 0

    def test_known_query_only_runs_that_query(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        _make_query(queries_dir, "target", PASSING_QUERY_SRC)
        _make_query(queries_dir, "other", PASSING_QUERY_SRC)

        run_one(queries_dir, "target", output_folder)

        assert (output_folder / "target.xlsx").exists()
        assert not (output_folder / "other.xlsx").exists()

    def test_unknown_query_returns_one(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        queries_dir.mkdir(parents=True, exist_ok=True)

        result = run_one(queries_dir, "nonexistent", output_folder)

        assert result == 1

    def test_unknown_query_writes_summary_failed(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        queries_dir.mkdir(parents=True, exist_ok=True)

        run_one(queries_dir, "nonexistent", output_folder)

        summary = _read_summary(output_folder)
        assert summary["queries"]["nonexistent"]["status"] == "failed"
        assert "reason" in summary["queries"]["nonexistent"]


class TestRunAllKeyErrorInRun:
    def test_keyerror_is_caught_and_reported(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        _make_query(queries_dir, "bad_key", KEYERROR_QUERY_SRC)

        result = run_all(queries_dir, output_folder)

        assert result == 1

    def test_keyerror_reason_in_summary(self, tmp_path):
        queries_dir = tmp_path / "queries"
        output_folder = tmp_path / "output"
        _make_query(queries_dir, "bad_key", KEYERROR_QUERY_SRC)

        run_all(queries_dir, output_folder)

        summary = _read_summary(output_folder)
        assert summary["queries"]["bad_key"]["status"] == "failed"
        reason = summary["queries"]["bad_key"]["reason"]
        assert "KeyError" in reason


class TestDiscoverySkipsSpecialDirs:
    def test_pycache_is_skipped(self, tmp_path):
        queries_dir = tmp_path / "queries"
        _make_query(queries_dir, "__pycache__", PASSING_QUERY_SRC)
        _make_query(queries_dir, "real_query", PASSING_QUERY_SRC)
        output_folder = tmp_path / "output"

        run_all(queries_dir, output_folder)

        summary = _read_summary(output_folder)
        assert "__pycache__" not in summary["queries"]
        assert "real_query" in summary["queries"]

    def test_dot_prefix_dirs_are_skipped(self, tmp_path):
        queries_dir = tmp_path / "queries"
        _make_query(queries_dir, ".hidden", PASSING_QUERY_SRC)
        _make_query(queries_dir, "visible", PASSING_QUERY_SRC)
        output_folder = tmp_path / "output"

        run_all(queries_dir, output_folder)

        summary = _read_summary(output_folder)
        assert ".hidden" not in summary["queries"]

    def test_underscore_prefix_dirs_are_skipped(self, tmp_path):
        queries_dir = tmp_path / "queries"
        _make_query(queries_dir, "_private", PASSING_QUERY_SRC)
        _make_query(queries_dir, "public", PASSING_QUERY_SRC)
        output_folder = tmp_path / "output"

        run_all(queries_dir, output_folder)

        summary = _read_summary(output_folder)
        assert "_private" not in summary["queries"]
