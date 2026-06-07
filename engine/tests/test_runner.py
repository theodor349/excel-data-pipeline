import json
from pathlib import Path

import pytest

from engine.runner import run_all, run_one


def _make_query(queries_dir: Path, name: str, query_src: str) -> Path:
    folder = queries_dir / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "query.py").write_text(query_src, encoding="utf-8")
    return folder


def _write_exports(repo_dir: Path, outputs: list[dict]) -> Path:
    path = repo_dir / "exports.json"
    path.write_text(json.dumps({"outputs": outputs}), encoding="utf-8")
    return path


def _read_summary(output_folder: Path) -> dict:
    return json.loads((output_folder / "summary.json").read_text(encoding="utf-8"))


PASSING = """\
import polars as pl
def load(): return {}
def run(data): return pl.DataFrame({"x": [1, 2, 3]})
"""

FAILING = """\
def load(): return {}
def run(data): raise RuntimeError("something broke")
"""

MISSING_RUN = """\
def load(): return {}
"""

UPSTREAM = """\
import polars as pl
def load(): return {}
def run(data): return pl.DataFrame({"x": [1, 2, 3]})
"""

DOWNSTREAM = """\
import polars as pl
DEPENDS_ON = ["upstream"]
def load(): return {}
def run(data):
    up = data["upstream"]
    return up.with_columns((pl.col("x") * 10).alias("y"))
"""

COLLISION = """\
import polars as pl
DEPENDS_ON = ["dep"]
def load(): return {"dep": pl.DataFrame({"x": [1]})}
def run(data): return data["dep"]
"""

CYCLE_A = """\
import polars as pl
DEPENDS_ON = ["b"]
def load(): return {}
def run(data): return pl.DataFrame({"x": [1]})
"""

CYCLE_B = """\
import polars as pl
DEPENDS_ON = ["a"]
def load(): return {}
def run(data): return pl.DataFrame({"x": [1]})
"""


class TestBasicRun:
    def test_passing_query_writes_output_and_returns_zero(self, tmp_path):
        qd = tmp_path / "queries"
        out = tmp_path / "output"
        _make_query(qd, "alpha", PASSING)
        exports = _write_exports(tmp_path, [
            {"filename": "alpha.xlsx", "format": "xlsx", "sheets": {"Sheet1": "alpha"}}
        ])

        rc = run_all(qd, out, exports)

        assert rc == 0
        assert (out / "alpha.xlsx").exists()
        summary = _read_summary(out)
        assert summary["queries"]["alpha"]["status"] == "ok"
        assert summary["outputs"]["alpha.xlsx"]["status"] == "written"

    def test_failing_query_fails_run_and_blocks_its_output(self, tmp_path):
        qd = tmp_path / "queries"
        out = tmp_path / "output"
        _make_query(qd, "bad", FAILING)
        exports = _write_exports(tmp_path, [
            {"filename": "bad.csv", "format": "csv", "query": "bad"}
        ])

        rc = run_all(qd, out, exports)

        assert rc == 1
        assert not (out / "bad.csv").exists()
        summary = _read_summary(out)
        assert summary["queries"]["bad"]["status"] == "failed"
        assert "reason" in summary["queries"]["bad"]
        assert summary["outputs"]["bad.csv"]["status"] == "failed"

    def test_failing_query_traceback_logged(self, tmp_path):
        qd = tmp_path / "queries"
        out = tmp_path / "output"
        _make_query(qd, "bad", FAILING)
        exports = _write_exports(tmp_path, [
            {"filename": "bad.csv", "format": "csv", "query": "bad"}
        ])

        run_all(qd, out, exports)

        log = next((out / "logs").glob("pipeline-*.log")).read_text(encoding="utf-8")
        assert "Traceback" in log
        assert "something broke" in log

    def test_missing_run_function_is_failure(self, tmp_path):
        qd = tmp_path / "queries"
        out = tmp_path / "output"
        _make_query(qd, "no_run", MISSING_RUN)
        exports = _write_exports(tmp_path, [
            {"filename": "x.csv", "format": "csv", "query": "no_run"}
        ])

        rc = run_all(qd, out, exports)

        assert rc == 1
        summary = _read_summary(out)
        assert summary["queries"]["no_run"]["status"] == "failed"
        assert "run" in summary["queries"]["no_run"]["reason"].lower()


class TestDependencies:
    def test_downstream_receives_upstream_table_in_topo_order(self, tmp_path):
        qd = tmp_path / "queries"
        out = tmp_path / "output"
        _make_query(qd, "upstream", UPSTREAM)
        _make_query(qd, "downstream", DOWNSTREAM)
        exports = _write_exports(tmp_path, [
            {"filename": "down.csv", "format": "csv", "query": "downstream"}
        ])

        rc = run_all(qd, out, exports)

        assert rc == 0
        content = (out / "down.csv").read_text(encoding="utf-8")
        assert content == "x,y\n1,10\n2,20\n3,30\n"

    def test_unreferenced_component_still_runs_if_depended_on(self, tmp_path):
        # upstream is not exported directly; it runs only because downstream needs it.
        qd = tmp_path / "queries"
        out = tmp_path / "output"
        _make_query(qd, "upstream", UPSTREAM)
        _make_query(qd, "downstream", DOWNSTREAM)
        exports = _write_exports(tmp_path, [
            {"filename": "down.csv", "format": "csv", "query": "downstream"}
        ])

        run_all(qd, out, exports)

        summary = _read_summary(out)
        assert summary["queries"]["upstream"]["status"] == "ok"
        assert summary["queries"]["downstream"]["status"] == "ok"

    def test_dependency_failure_skips_dependent(self, tmp_path):
        qd = tmp_path / "queries"
        out = tmp_path / "output"
        # rename upstream's run to fail
        _make_query(qd, "upstream", "def load(): return {}\ndef run(data): raise ValueError('boom')\n")
        _make_query(qd, "downstream", DOWNSTREAM)
        exports = _write_exports(tmp_path, [
            {"filename": "down.csv", "format": "csv", "query": "downstream"}
        ])

        rc = run_all(qd, out, exports)

        assert rc == 1
        summary = _read_summary(out)
        assert summary["queries"]["upstream"]["status"] == "failed"
        assert summary["queries"]["downstream"]["status"] == "skipped"
        assert "upstream" in summary["queries"]["downstream"]["reason"]
        assert summary["outputs"]["down.csv"]["status"] == "failed"


class TestReachabilityPruning:
    def test_unreferenced_query_never_runs(self, tmp_path):
        qd = tmp_path / "queries"
        out = tmp_path / "output"
        _make_query(qd, "wanted", PASSING)
        # If 'unwanted' executed it would FAIL; pruning means it is only skipped.
        _make_query(qd, "unwanted", FAILING)
        exports = _write_exports(tmp_path, [
            {"filename": "w.csv", "format": "csv", "query": "wanted"}
        ])

        rc = run_all(qd, out, exports)

        assert rc == 0
        summary = _read_summary(out)
        assert summary["queries"]["wanted"]["status"] == "ok"
        assert summary["queries"]["unwanted"]["status"] == "skipped"
        assert "not referenced" in summary["queries"]["unwanted"]["reason"]


class TestCycleDetection:
    def test_cycle_is_hard_error_nothing_runs(self, tmp_path):
        qd = tmp_path / "queries"
        out = tmp_path / "output"
        _make_query(qd, "a", CYCLE_A)
        _make_query(qd, "b", CYCLE_B)
        exports = _write_exports(tmp_path, [
            {"filename": "a.csv", "format": "csv", "query": "a"}
        ])

        rc = run_all(qd, out, exports)

        assert rc == 1
        # nothing executed: summary has empty queries section
        summary = _read_summary(out)
        assert summary["queries"] == {}
        log = next((out / "logs").glob("pipeline-*.log")).read_text(encoding="utf-8")
        assert "cycle" in log.lower()


class TestCollision:
    def test_source_and_dependency_name_collision_is_failure(self, tmp_path):
        qd = tmp_path / "queries"
        out = tmp_path / "output"
        _make_query(qd, "dep", UPSTREAM)
        _make_query(qd, "collide", COLLISION)
        exports = _write_exports(tmp_path, [
            {"filename": "c.csv", "format": "csv", "query": "collide"}
        ])

        rc = run_all(qd, out, exports)

        assert rc == 1
        summary = _read_summary(out)
        assert summary["queries"]["collide"]["status"] == "failed"
        assert "collision" in summary["queries"]["collide"]["reason"].lower()


class TestUnknownReferences:
    def test_export_references_unknown_query(self, tmp_path):
        qd = tmp_path / "queries"
        qd.mkdir(parents=True, exist_ok=True)
        out = tmp_path / "output"
        exports = _write_exports(tmp_path, [
            {"filename": "x.csv", "format": "csv", "query": "ghost"}
        ])

        rc = run_all(qd, out, exports)

        assert rc == 1
        log = next((out / "logs").glob("pipeline-*.log")).read_text(encoding="utf-8")
        assert "ghost" in log

    def test_missing_exports_file(self, tmp_path):
        qd = tmp_path / "queries"
        _make_query(qd, "a", PASSING)
        out = tmp_path / "output"

        rc = run_all(qd, out, tmp_path / "nonexistent.json")

        assert rc == 1


class TestRunOne:
    def test_runs_query_and_its_closure(self, tmp_path):
        qd = tmp_path / "queries"
        out = tmp_path / "output"
        _make_query(qd, "upstream", UPSTREAM)
        _make_query(qd, "downstream", DOWNSTREAM)
        _make_query(qd, "other", PASSING)
        exports = _write_exports(tmp_path, [
            {"filename": "down.csv", "format": "csv", "query": "downstream"},
            {"filename": "other.csv", "format": "csv", "query": "other"},
        ])

        rc = run_one(qd, "downstream", out, exports)

        assert rc == 0
        # downstream's output is written; 'other' is outside the closure, not written.
        assert (out / "down.csv").exists()
        assert not (out / "other.csv").exists()
        summary = _read_summary(out)
        assert summary["queries"]["upstream"]["status"] == "ok"
        assert summary["queries"]["downstream"]["status"] == "ok"
        assert "other" not in summary["queries"]

    def test_unknown_query_returns_one(self, tmp_path):
        qd = tmp_path / "queries"
        qd.mkdir(parents=True, exist_ok=True)
        out = tmp_path / "output"
        exports = _write_exports(tmp_path, [
            {"filename": "x.csv", "format": "csv", "query": "a"}
        ])

        rc = run_one(qd, "nonexistent", out, exports)

        assert rc == 1
        summary = _read_summary(out)
        assert summary["queries"]["nonexistent"]["status"] == "failed"


class TestDiscoverySkipsSpecialDirs:
    def test_pycache_and_dot_and_underscore_skipped(self, tmp_path):
        qd = tmp_path / "queries"
        out = tmp_path / "output"
        _make_query(qd, "__pycache__", PASSING)
        _make_query(qd, ".hidden", PASSING)
        _make_query(qd, "_private", PASSING)
        _make_query(qd, "real", PASSING)
        exports = _write_exports(tmp_path, [
            {"filename": "real.csv", "format": "csv", "query": "real"}
        ])

        run_all(qd, out, exports)

        summary = _read_summary(out)
        assert "real" in summary["queries"]
        assert "__pycache__" not in summary["queries"]
        assert ".hidden" not in summary["queries"]
        assert "_private" not in summary["queries"]
