import importlib.util
import json
import logging
from pathlib import Path

import engine.exporter as exporter
import engine.logger as logger_mod


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


def _run_query(name: str, query_file: Path, output_folder: Path, log: logging.Logger) -> tuple[str, str | None]:
    log.info("starting query %s", name)
    try:
        module = _load_query_module(name, query_file)

        if not hasattr(module, "load"):
            reason = f"query.py is missing required function 'load'"
            log.error("query %s failed: %s", name, reason)
            return "failed", reason

        if not hasattr(module, "run"):
            reason = f"query.py is missing required function 'run'"
            log.error("query %s failed: %s", name, reason)
            return "failed", reason

        data = module.load()
        sheets = module.run(data)
        exporter.export(sheets, output_folder, filename=name)
        log.info("query %s ok", name)
        return "ok", None

    except Exception as e:
        reason = f"{type(e).__name__}: {e}"
        log.exception("query %s failed: %s", name, reason)
        return "failed", reason


def _write_summary(output_folder: Path, results: dict[str, tuple[str, str | None]]) -> None:
    queries_summary = {}
    for name, (status, reason) in results.items():
        entry: dict = {"status": status}
        if status == "failed" and reason is not None:
            entry["reason"] = reason
        queries_summary[name] = entry

    summary_path = output_folder / "summary.json"
    summary_path.write_text(
        json.dumps({"queries": queries_summary}, indent=2), encoding="utf-8"
    )


def run_all(queries_dir: str | Path, output_folder: str | Path) -> int:
    queries_dir = Path(queries_dir)
    output_folder = Path(output_folder)

    logger_mod.setup_logger(output_folder)
    log = logging.getLogger("pipeline")
    log.info("run started: all queries in %s", queries_dir)

    discovered = _discover_queries(queries_dir)
    results: dict[str, tuple[str, str | None]] = {}

    for name, query_file in discovered:
        status, reason = _run_query(name, query_file, output_folder, log)
        results[name] = (status, reason)

        if status == "ok":
            print(f"[OK] {name}")
        else:
            log_filename = _log_file_name(output_folder)
            print(f"[FAILED] {name} — see logs/{log_filename}")

    _write_summary(output_folder, results)

    return 0 if all(status == "ok" for status, _ in results.values()) else 1


def run_one(queries_dir: str | Path, query_name: str, output_folder: str | Path) -> int:
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
        _write_summary(output_folder, {query_name: ("failed", reason)})
        return 1

    status, reason = _run_query(query_name, query_file, output_folder, log)
    _write_summary(output_folder, {query_name: (status, reason)})

    if status == "ok":
        print(f"[OK] {query_name}")
        return 0
    else:
        log_filename = _log_file_name(output_folder)
        print(f"[FAILED] {query_name} — see logs/{log_filename}")
        return 1
