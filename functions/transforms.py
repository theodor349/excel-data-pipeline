from decimal import Decimal, ROUND_HALF_UP

import pandas as pd
from pandas import DataFrame


def lowercase(df: DataFrame, column: str) -> DataFrame:
    df = df.copy()
    df[column] = df[column].where(df[column].isna(), df[column].str.lower())
    return df


def to_int(df: DataFrame, column: str) -> DataFrame:
    df = df.copy()
    df[column] = df[column].astype("Int64")
    return df


def to_decimal(df: DataFrame, column: str, places: int = 2) -> DataFrame:
    df = df.copy()
    quantizer = Decimal(10) ** -places

    def _convert(value):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP)

    df[column] = df[column].apply(_convert)
    return df


def to_float(df: DataFrame, column: str) -> DataFrame:
    df = df.copy()
    df[column] = df[column].astype(float)
    return df


def to_date(df: DataFrame, column: str, format: str | None = None) -> DataFrame:
    df = df.copy()
    if format is not None:
        df[column] = pd.to_datetime(df[column], format=format)
    else:
        df[column] = pd.to_datetime(df[column])
    return df


def fiscal_year(
    df: DataFrame,
    date_column: str,
    fy_start_month: int = 1,
    new_column: str = "fiscal_year",
) -> DataFrame:
    df = df.copy()
    # FY = the calendar year in which the fiscal year ends.
    # e.g. fy_start_month=7: Jul 2025 – Jun 2026 is FY 2026.
    dates = df[date_column]
    cal_year = dates.dt.year
    cal_month = dates.dt.month
    if fy_start_month == 1:
        df[new_column] = cal_year
    else:
        df[new_column] = cal_year + (cal_month >= fy_start_month).astype(int)
    return df


def period_end(
    df: DataFrame,
    date_column: str,
    granularity: str,
    new_column: str = "period_end",
) -> DataFrame:
    df = df.copy()
    freq_map = {"month": "M", "quarter": "Q", "year": "Y"}
    freq = freq_map[granularity]
    df[new_column] = (
        df[date_column].dt.to_period(freq).dt.end_time.dt.normalize()
    )
    return df


def rename(df: DataFrame, old_name: str, new_name: str) -> DataFrame:
    df = df.copy()
    df = df.rename(columns={old_name: new_name})
    return df


def keep_columns(df: DataFrame, columns: list) -> DataFrame:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise KeyError(f"Columns not found in DataFrame: {missing}")
    return df[columns].copy()


def filter_rows(df: DataFrame, column: str, value) -> DataFrame:
    df = df.copy()
    return df[df[column] == value].copy()


def drop_nulls(df: DataFrame, column: str) -> DataFrame:
    df = df.copy()
    return df[df[column].notna()].copy()
