"""Query execution engine.

Queries form a DAG via `DEPENDS_ON`. Only queries reachable from `exports.json`
(plus their dependency closure) run; everything else is pruned and reported as
skipped. Execution is a single sequential topological walk in one process: each
query runs exactly once, its output table is cached in memory, and that table is
injected into the `data` dict of every dependent. Keeping everything in-process
means polars `Decimal` columns are never pickled across a boundary, so precision
is preserved by construction. Outputs are then written per `exports.json`.
"""

import importlib.util
import json
import logging
import traceback
from dataclasses import dataclass
from pathlib import Path

import polars as pl

import engine.exporter as exporter
import engine.logger as logger_mod
from engine.export_config import (
    ExportConfig,
    ExportConfigError,
    load_export_config,
    referenced_queries,
)


@dataclass
class QueryOutcome:
    status: str  # "ok" | "failed" | "skipped"
    reason: str | None = None
    table: pl.DataFrame | None = None
    traceback: str | None = None


def _discover_queries(queries_dir: Path) -> list[tuple[str, Path]]:
    results = []
    for entry in sorted(queries_dir.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        if name == "__pycache__" or name.startswith(".") or name.startswith("_"):
            continue
        query_file = entry / "query.py"
        if query_file.is_file():
            results.append((name, query_file))
    return results


def _load_query_module(name: str, query_file: Path):
    spec = importlib.util.spec_from_file_location(f"queries.{name}.query", query_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _log_file_name(output_folder: Path) -> str:
    logs_dir = output_folder / "logs"
    files = sorted(logs_dir.glob("pipeline-*.log"))
    if files:
        return files[-1].name
    return "pipeline-<unknown>.log"


def _reachable(seeds: set[str], deps: dict[str, list[str]]) -> set[str]:
    """All nodes reachable from `seeds` following `DEPENDS_ON` edges."""
    seen: set[str] = set()
    stack = list(seeds)
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(deps.get(node, []))
    return seen


def _find_cycle(nodes: set[str], deps: dict[str, list[str]]) -> list[str] | None:
    """Return one dependency cycle as an ordered list, or None if acyclic."""
    WHITE, GREY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}
    path: list[str] = []

    def visit(n: str) -> list[str] | None:
        color[n] = GREY
        path.append(n)
        for dep in deps.get(n, []):
            if dep not in color:
                continue
            if color[dep] == GREY:
                idx = path.index(dep)
                return path[idx:] + [dep]
            if color[dep] == WHITE:
                found = visit(dep)
                if found:
                    return found
        path.pop()
        color[n] = BLACK
        return None

    for node in sorted(nodes):
        if color[node] == WHITE:
            found = visit(node)
            if found:
                return found
    return None


def _topo_order(nodes: set[str], deps: dict[str, list[str]]) -> list[str]:
    """Dependencies before dependents. Assumes `nodes` is acyclic."""
    order: list[str] = []
    visited: set[str] = set()

    def visit(n: str) -> None:
        if n in visited:
            return
        visited.add(n)
        for dep in deps.get(n, []):
            if dep in nodes:
                visit(dep)
        order.append(n)

    for node in sorted(nodes):
        visit(node)
    return order


def _load_modules(
    discovered: list[tuple[str, Path]],
) -> tuple[dict, dict[str, list[str]], dict[str, str]]:
    """Import each query module to read its `DEPENDS_ON`.

    Returns (modules, deps, load_errors). A module that fails to import gets an
    empty dependency list and an entry in load_errors; it executes as a failure.
    """
    modules: dict = {}
    deps: dict[str, list[str]] = {}
    load_errors: dict[str, str] = {}
    for name, query_file in discovered:
        try:
            module = _load_query_module(name, query_file)
        except Exception as e:
            deps[name] = []
            load_errors[name] = f"{type(e).__name__}: {e}"
            continue
        modules[name] = module
        declared = getattr(module, "DEPENDS_ON", [])
        if not isinstance(declared, (list, tuple)) or not all(
            isinstance(d, str) for d in declared
        ):
            load_errors[name] = "DEPENDS_ON must be a list of query-name strings"
            deps[name] = []
        else:
            deps[name] = list(declared)
    return modules, deps, load_errors


def _execute_query(
    module,
    dep_names: list[str],
    outcomes: dict[str, QueryOutcome],
) -> QueryOutcome:
    """Run one query whose dependencies have already been resolved."""
    if not hasattr(module, "load"):
        return QueryOutcome("failed", "query.py is missing required function 'load'")
    if not hasattr(module, "run"):
        return QueryOutcome("failed", "query.py is missing required function 'run'")

    try:
        data = module.load()
        if not isinstance(data, dict):
            return QueryOutcome("failed", "load() must return a dict of named tables")

        # A DEPENDS_ON name colliding with a load() source key would silently
        # clobber one or the other — a finance-grade wrong-number bug. Hard error.
        collisions = sorted(set(data) & set(dep_names))
        if collisions:
            return QueryOutcome(
                "failed",
                f"name collision: {collisions} is both a load() source and a "
                f"DEPENDS_ON query. Rename the source or the query.",
            )

        for dep in dep_names:
            data[dep] = outcomes[dep].table

        table = module.run(data)
        if not isinstance(table, pl.DataFrame):
            return QueryOutcome(
                "failed",
                f"run(data) must return a single polars DataFrame, got "
                f"{type(table).__name__}",
            )
        return QueryOutcome("ok", table=table)
    except Exception as e:
        return QueryOutcome("failed", f"{type(e).__name__}: {e}", traceback=traceback.format_exc())


def _write_summary(
    output_folder: Path,
    outcomes: dict[str, QueryOutcome],
    output_results: dict[str, "exporter.OutputResult"],
) -> None:
    queries_summary: dict[str, dict] = {}
    for name, outcome in outcomes.items():
        entry: dict = {"status": outcome.status}
        if outcome.reason is not None:
            entry["reason"] = outcome.reason
        queries_summary[name] = entry

    outputs_summary: dict[str, dict] = {}
    for filename, result in output_results.items():
        entry = {"status": result.status}
        if result.reason is not None:
            entry["reason"] = result.reason
        outputs_summary[filename] = entry

    summary_path = output_folder / "summary.json"
    summary_path.write_text(
        json.dumps({"queries": queries_summary, "outputs": outputs_summary}, indent=2),
        encoding="utf-8",
    )


def _report_query(name: str, outcome: QueryOutcome, output_folder: Path, log: logging.Logger) -> None:
    if outcome.status == "ok":
        log.info("query %s ok", name)
        print(f"[OK] {name}")
    elif outcome.status == "skipped":
        log.info("query %s skipped: %s", name, outcome.reason)
        print(f"[SKIPPED] {name} — {outcome.reason}")
    else:
        if outcome.traceback:
            log.error("query %s failed: %s\n%s", name, outcome.reason, outcome.traceback)
        else:
            log.error("query %s failed: %s", name, outcome.reason)
        print(f"[FAILED] {name} — see logs/{_log_file_name(output_folder)}")


def _run(
    queries_dir: Path,
    output_folder: Path,
    config: ExportConfig,
    seeds: set[str],
    report_unreachable: bool,
) -> int:
    log = logging.getLogger("pipeline")

    discovered = _discover_queries(queries_dir)
    discovered_names = {name for name, _ in discovered}
    modules, deps, load_errors = _load_modules(discovered)

    # Pre-execution structural checks: missing references and cycles are hard
    # errors that fail before anything runs (the user hits these while composing).
    unknown_refs = sorted(seeds - discovered_names)
    if unknown_refs:
        msg = f"exports.json references unknown quer{'y' if len(unknown_refs)==1 else 'ies'}: {unknown_refs}"
        log.error(msg)
        print(f"[ERROR] {msg}")
        _write_summary(output_folder, {}, {})
        return 1

    missing_deps = sorted(
        f"{name} -> {dep}"
        for name, dep_list in deps.items()
        for dep in dep_list
        if dep not in discovered_names
    )
    if missing_deps:
        msg = f"DEPENDS_ON references unknown queries: {missing_deps}"
        log.error(msg)
        print(f"[ERROR] {msg}")
        _write_summary(output_folder, {}, {})
        return 1

    cycle = _find_cycle(discovered_names, deps)
    if cycle:
        msg = f"DEPENDS_ON cycle detected: {' -> '.join(cycle)}"
        log.error(msg)
        print(f"[ERROR] {msg}")
        _write_summary(output_folder, {}, {})
        return 1

    reachable = _reachable(seeds, deps)
    order = _topo_order(reachable, deps)

    outcomes: dict[str, QueryOutcome] = {}
    if report_unreachable:
        for name in sorted(discovered_names - reachable):
            outcomes[name] = QueryOutcome("skipped", "not referenced by exports.json")
            _report_query(name, outcomes[name], output_folder, log)

    for name in order:
        log.info("starting query %s", name)
        if name in load_errors:
            outcomes[name] = QueryOutcome("failed", load_errors[name])
            _report_query(name, outcomes[name], output_folder, log)
            continue

        failed_dep = next(
            (d for d in deps[name] if outcomes[d].status != "ok"), None
        )
        if failed_dep is not None:
            outcomes[name] = QueryOutcome(
                "skipped", f"dependency '{failed_dep}' did not succeed"
            )
            _report_query(name, outcomes[name], output_folder, log)
            continue

        outcomes[name] = _execute_query(modules[name], deps[name], outcomes)
        _report_query(name, outcomes[name], output_folder, log)

    results = {
        name: o.table for name, o in outcomes.items() if o.status == "ok"
    }
    # Only attempt outputs whose every query is in the executed set (so --query
    # writes just the files its closure can satisfy). For --all this is all of them.
    attempt = ExportConfig(
        outputs=[o for o in config.outputs if o.query_names() <= reachable]
    )
    output_results = exporter.export_outputs(results, attempt, output_folder)
    for filename, result in output_results.items():
        if result.status == "written":
            log.info("output %s written", filename)
            print(f"[WROTE] {filename}")
        else:
            log.error("output %s failed: %s", filename, result.reason)
            print(f"[FAILED] {filename} — {result.reason}")

    _write_summary(output_folder, outcomes, output_results)

    any_query_failed = any(o.status == "failed" for o in outcomes.values())
    any_output_failed = any(r.status == "failed" for r in output_results.values())
    return 1 if (any_query_failed or any_output_failed) else 0


def run_all(
    queries_dir: str | Path,
    output_folder: str | Path,
    exports_path: str | Path,
) -> int:
    queries_dir = Path(queries_dir)
    output_folder = Path(output_folder)

    logger_mod.setup_logger(output_folder)
    log = logging.getLogger("pipeline")
    log.info("run started: all exports.json outputs in %s", queries_dir)

    try:
        config = load_export_config(exports_path)
    except ExportConfigError as e:
        log.error("invalid exports.json: %s", e)
        print(f"[ERROR] {e}")
        _write_summary(output_folder, {}, {})
        return 1

    return _run(
        queries_dir,
        output_folder,
        config,
        seeds=referenced_queries(config),
        report_unreachable=True,
    )


def run_one(
    queries_dir: str | Path,
    query_name: str,
    output_folder: str | Path,
    exports_path: str | Path,
) -> int:
    queries_dir = Path(queries_dir)
    output_folder = Path(output_folder)

    logger_mod.setup_logger(output_folder)
    log = logging.getLogger("pipeline")
    log.info("run started: single query '%s' in %s", query_name, queries_dir)

    query_file = queries_dir / query_name / "query.py"
    if not query_file.is_file():
        reason = f"query '{query_name}' not found in {queries_dir}"
        log.error(reason)
        print(f"[FAILED] {query_name} — query not found")
        _write_summary(output_folder, {query_name: QueryOutcome("failed", reason)}, {})
        return 1

    try:
        config = load_export_config(exports_path)
    except ExportConfigError as e:
        log.error("invalid exports.json: %s", e)
        print(f"[ERROR] {e}")
        _write_summary(output_folder, {}, {})
        return 1

    return _run(
        queries_dir,
        output_folder,
        config,
        seeds={query_name},
        report_unreachable=False,
    )
