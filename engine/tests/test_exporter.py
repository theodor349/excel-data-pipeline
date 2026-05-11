import decimal
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import openpyxl
import polars as pl
import pytest

from engine.exporter import export


def test_single_sheet_creates_file(tmp_path):
    df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
    export({"Sheet1": df}, tmp_path, "output.xlsx")
    assert (tmp_path / "output.xlsx").exists()


def test_xlsx_extension_appended_when_missing(tmp_path):
    df = pl.DataFrame({"x": [1]})
    export({"S": df}, tmp_path, "report")
    assert (tmp_path / "report.xlsx").exists()


def test_multi_sheet_all_sheets_present(tmp_path):
    df1 = pl.DataFrame({"col": [1, 2]})
    df2 = pl.DataFrame({"col": [3, 4]})
    df3 = pl.DataFrame({"col": [5, 6]})
    export({"Alpha": df1, "Beta": df2, "Gamma": df3}, tmp_path, "multi.xlsx")

    wb = openpyxl.load_workbook(tmp_path / "multi.xlsx")
    assert wb.sheetnames == ["Alpha", "Beta", "Gamma"]


def test_output_folder_created_if_missing(tmp_path):
    deep = tmp_path / "a" / "b" / "c"
    assert not deep.exists()
    df = pl.DataFrame({"v": [1]})
    export({"Sheet1": df}, deep, "out.xlsx")
    assert (deep / "out.xlsx").exists()


def test_no_tmp_files_remain_after_export(tmp_path):
    df = pl.DataFrame({"n": [1, 2, 3]})
    export({"Data": df}, tmp_path, "clean.xlsx")
    tmp_files = list(tmp_path.glob("*.tmp-*.xlsx"))
    assert tmp_files == []


def test_decimal_round_trip_precision(tmp_path):
    col = [Decimal("0.10")] * 1000
    df = pl.DataFrame({"amount": col}, schema={"amount": pl.Object})
    export({"Sheet1": df}, tmp_path, "decimal_test.xlsx")

    wb = openpyxl.load_workbook(tmp_path / "decimal_test.xlsx", data_only=True)
    ws = wb.active

    read_sum = Decimal("0")
    sample_cell = None
    for row_idx, row in enumerate(ws.iter_rows(min_row=2)):
        cell = row[0]
        if sample_cell is None:
            sample_cell = cell
        read_sum += Decimal(str(cell.value))

    assert Decimal(str(read_sum)) == Decimal("100.00")
    assert sample_cell.number_format == "#,##0.00"
    assert sample_cell.data_type == "n"


def test_decimal_three_places_gets_correct_format(tmp_path):
    df = pl.DataFrame(
        {"price": [Decimal("1.234"), Decimal("5.678")]},
        schema={"price": pl.Object},
    )
    export({"Prices": df}, tmp_path, "three_dp.xlsx")

    wb = openpyxl.load_workbook(tmp_path / "three_dp.xlsx", data_only=True)
    ws = wb.active

    data_cell = list(ws.iter_rows(min_row=2))[0][0]
    assert data_cell.number_format == "#,##0.000"


def test_invalid_sheet_name_too_long_raises():
    df = pl.DataFrame({"x": [1]})
    with pytest.raises(ValueError, match="exceeds"):
        export({"A" * 32: df}, "/tmp", "out.xlsx")


def test_invalid_sheet_name_bad_chars_raises():
    df = pl.DataFrame({"x": [1]})
    with pytest.raises(ValueError, match="invalid Excel characters"):
        export({"Bad/Name": df}, "/tmp", "out.xlsx")


def test_permission_error_during_rename_propagates(tmp_path):
    df = pl.DataFrame({"v": [1]})
    with patch("pathlib.Path.replace", side_effect=PermissionError("file in use")):
        with pytest.raises(PermissionError):
            export({"Sheet1": df}, tmp_path, "locked.xlsx")
