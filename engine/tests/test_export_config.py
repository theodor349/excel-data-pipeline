import json
from pathlib import Path

import pytest

from engine.export_config import (
    ExportConfigError,
    load_export_config,
    referenced_queries,
)


def _write(tmp_path: Path, obj) -> Path:
    p = tmp_path / "exports.json"
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def test_valid_mixed_config(tmp_path):
    path = _write(
        tmp_path,
        {
            "outputs": [
                {
                    "filename": "region_report.xlsx",
                    "format": "xlsx",
                    "sheets": {"Summary": "region_summary", "By Month": "region_monthly"},
                },
                {"filename": "fx.csv", "format": "csv", "query": "fx_rates_clean"},
            ]
        },
    )
    config = load_export_config(path)
    assert len(config.outputs) == 2
    assert referenced_queries(config) == {
        "region_summary",
        "region_monthly",
        "fx_rates_clean",
    }


def test_missing_file(tmp_path):
    with pytest.raises(ExportConfigError, match="not found"):
        load_export_config(tmp_path / "nope.json")


def test_invalid_json(tmp_path):
    p = tmp_path / "exports.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ExportConfigError, match="not valid JSON"):
        load_export_config(p)


def test_missing_outputs_key(tmp_path):
    path = _write(tmp_path, {"foo": []})
    with pytest.raises(ExportConfigError, match="outputs"):
        load_export_config(path)


def test_empty_outputs(tmp_path):
    path = _write(tmp_path, {"outputs": []})
    with pytest.raises(ExportConfigError, match="non-empty"):
        load_export_config(path)


def test_unknown_format(tmp_path):
    path = _write(
        tmp_path,
        {"outputs": [{"filename": "x.txt", "format": "txt", "query": "q"}]},
    )
    with pytest.raises(ExportConfigError, match="unknown format"):
        load_export_config(path)


def test_duplicate_filename(tmp_path):
    path = _write(
        tmp_path,
        {
            "outputs": [
                {"filename": "dup.csv", "format": "csv", "query": "a"},
                {"filename": "dup.csv", "format": "csv", "query": "b"},
            ]
        },
    )
    with pytest.raises(ExportConfigError, match="duplicate"):
        load_export_config(path)


def test_xlsx_requires_sheets(tmp_path):
    path = _write(
        tmp_path,
        {"outputs": [{"filename": "r.xlsx", "format": "xlsx"}]},
    )
    with pytest.raises(ExportConfigError, match="sheets"):
        load_export_config(path)


def test_xlsx_empty_sheets(tmp_path):
    path = _write(
        tmp_path,
        {"outputs": [{"filename": "r.xlsx", "format": "xlsx", "sheets": {}}]},
    )
    with pytest.raises(ExportConfigError, match="sheets"):
        load_export_config(path)


def test_csv_requires_query(tmp_path):
    path = _write(
        tmp_path,
        {"outputs": [{"filename": "r.csv", "format": "csv"}]},
    )
    with pytest.raises(ExportConfigError, match="query"):
        load_export_config(path)


def test_bad_sheet_name_too_long(tmp_path):
    path = _write(
        tmp_path,
        {
            "outputs": [
                {"filename": "r.xlsx", "format": "xlsx", "sheets": {"A" * 32: "q"}}
            ]
        },
    )
    with pytest.raises(ExportConfigError, match="exceeds"):
        load_export_config(path)


def test_bad_sheet_name_invalid_chars(tmp_path):
    path = _write(
        tmp_path,
        {
            "outputs": [
                {"filename": "r.xlsx", "format": "xlsx", "sheets": {"Bad/Name": "q"}}
            ]
        },
    )
    with pytest.raises(ExportConfigError, match="invalid Excel characters"):
        load_export_config(path)


def test_xlsx_with_query_key_rejected(tmp_path):
    path = _write(
        tmp_path,
        {
            "outputs": [
                {
                    "filename": "r.xlsx",
                    "format": "xlsx",
                    "sheets": {"S": "q"},
                    "query": "other",
                }
            ]
        },
    )
    with pytest.raises(ExportConfigError, match="use 'sheets'"):
        load_export_config(path)
