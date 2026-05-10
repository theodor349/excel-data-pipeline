import decimal
import os
import uuid
from pathlib import Path

import openpyxl
import pandas as pd

_INVALID_SHEET_CHARS = frozenset(r"/\?*[]:")
_MAX_SHEET_NAME_LEN = 31


def _validate_sheet_name(name: str) -> None:
    if len(name) > _MAX_SHEET_NAME_LEN:
        raise ValueError(
            f"Sheet name '{name}' exceeds {_MAX_SHEET_NAME_LEN} characters"
        )
    bad = _INVALID_SHEET_CHARS & set(name)
    if bad:
        raise ValueError(
            f"Sheet name '{name}' contains invalid Excel characters: {bad}"
        )


def _decimal_places_for_column(series: pd.Series) -> int:
    non_null = series.dropna()
    sample = [v for v in non_null if isinstance(v, decimal.Decimal)][:10]
    if not sample:
        return 2
    max_places = 0
    for value in sample:
        sign, digits, exponent = value.as_tuple()
        if exponent < 0:
            max_places = max(max_places, -exponent)
    return max_places if max_places > 0 else 2


def _is_decimal_column(series: pd.Series) -> bool:
    if series.dtype != object:
        return False
    for value in series:
        if value is not None and not (isinstance(value, float) and pd.isna(value)):
            return isinstance(value, decimal.Decimal)
    return False


def export(sheets: dict[str, pd.DataFrame], output_folder: str | Path, filename: str) -> None:
    for name in sheets:
        _validate_sheet_name(name)

    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    if not filename.endswith(".xlsx"):
        filename = filename + ".xlsx"

    target = output_folder / filename
    tmp_path = output_folder / f"{filename}.tmp-{uuid.uuid4()}.xlsx"

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    for sheet_name, df in sheets.items():
        ws = wb.create_sheet(title=sheet_name)

        decimal_columns: dict[int, str] = {}
        for col_idx, col_name in enumerate(df.columns):
            series = df[col_name]
            if _is_decimal_column(series):
                places = _decimal_places_for_column(series)
                fmt = "#,##0." + "0" * places
                decimal_columns[col_idx] = fmt

        ws.append(list(df.columns))

        for row_tuple in df.itertuples(index=False, name=None):
            row_data = []
            for col_idx, value in enumerate(row_tuple):
                if col_idx in decimal_columns and isinstance(value, decimal.Decimal):
                    row_data.append(float(value))
                else:
                    row_data.append(value)
            ws.append(row_data)

        if decimal_columns:
            for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
                for col_idx, fmt in decimal_columns.items():
                    cell = row[col_idx]
                    cell.number_format = fmt

    wb.save(tmp_path)

    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(target_path)
