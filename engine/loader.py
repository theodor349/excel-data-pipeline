import json
import os
from pathlib import Path

import polars as pl

_project_root: Path | None = None
_config_cache: dict[str, dict] = {}


def _find_project_root() -> Path:
    global _project_root
    if _project_root is not None:
        return _project_root
    candidate = Path(__file__).resolve().parent
    while candidate != candidate.parent:
        if (candidate / "pyproject.toml").exists():
            _project_root = candidate
            return _project_root
        candidate = candidate.parent
    raise FileNotFoundError("pyproject.toml not found walking up from engine/loader.py")


def _load_config() -> dict:
    env_path = os.environ.get("PIPELINE_CONFIG")
    if env_path:
        config_path = Path(env_path)
    else:
        config_path = _find_project_root() / "config.json"
    key = str(config_path.resolve())
    if key not in _config_cache:
        with config_path.open(encoding="utf-8") as f:
            _config_cache[key] = json.load(f)
    return _config_cache[key]


def _get_source_path(section: str, source_name: str) -> str:
    config = _load_config()
    if source_name not in config.get(section, {}):
        raise KeyError(
            f"'{source_name}' not found in '{section}' in config.json"
        )
    return config[section][source_name]


def _read_csv_path(path: str | Path) -> pl.DataFrame:
    return pl.read_csv(path)


def _read_excel_path(path: str | Path, sheet_name: str) -> pl.DataFrame:
    return pl.read_excel(path, sheet_name=sheet_name, engine="calamine")


def read_excel(source_name: str, sheet_or_table: str) -> pl.DataFrame:
    path = _get_source_path("excel_sources", source_name)
    return _read_excel_path(path, sheet_or_table)


def _read_jsonl_path(path: str | Path) -> pl.DataFrame:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    if not records:
        return pl.DataFrame()
    return pl.DataFrame(records)


def read_jsonl(source_name: str) -> pl.DataFrame:
    path = _get_source_path("jsonl_sources", source_name)
    return _read_jsonl_path(path)


def read_csv(source_name: str) -> pl.DataFrame:
    path = _get_source_path("csv_sources", source_name)
    return _read_csv_path(path)


def read_sql(connection_name: str, query: str) -> pl.DataFrame:
    import pyodbc

    config = _load_config()
    section = "connections"
    if connection_name not in config.get(section, {}):
        raise KeyError(
            f"'{connection_name}' not found in '{section}' in config.json"
        )
    conn_cfg = config[section][connection_name]
    conn_type = conn_cfg.get("type")
    if conn_type == "mssql":
        conn_str = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            f"SERVER={conn_cfg['host']};"
            f"DATABASE={conn_cfg['database']};"
            f"UID={conn_cfg['username']};"
            f"PWD={conn_cfg['password']}"
        )
        conn = pyodbc.connect(conn_str)
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            data = {col: [row[i] for row in rows] for i, col in enumerate(columns)}
            return pl.DataFrame(data)
        finally:
            conn.close()
    else:
        raise ValueError(f"Unsupported connection type: '{conn_type}'")
