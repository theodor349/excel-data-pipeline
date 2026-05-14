import uuid
from pathlib import Path

import openpyxl
import polars as pl

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


def _decimal_places_for_column(col: pl.Series) -> int:
    dtype = col.dtype
    if isinstance(dtype, pl.Decimal):
        scale = dtype.scale
        return scale if scale is not None else 2
    return 2


def _is_decimal_column(col: pl.Series) -> bool:
    return isinstance(col.dtype, pl.Decimal)


def export(sheets: dict[str, pl.DataFrame], output_folder: str | Path, filename: str) -> None:
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
            col = df[col_name]
            if _is_decimal_column(col):
                places = _decimal_places_for_column(col)
                fmt = "#,##0." + "0" * places
                decimal_columns[col_idx] = fmt

        ws.append(list(df.columns))

        # Cast Decimal columns to Float64 for openpyxl (which needs numeric scalars)
        df_export = df
        for col_idx, col_name in enumerate(df.columns):
            if col_idx in decimal_columns:
                df_export = df_export.with_columns(
                    pl.col(col_name).cast(pl.Float64)
                )

        for row_tuple in df_export.iter_rows():
            ws.append(list(row_tuple))

        if decimal_columns:
            for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
                for col_idx, fmt in decimal_columns.items():
                    cell = row[col_idx]
                    cell.number_format = fmt

    wb.save(tmp_path)

    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(target_path)
