"""Text cleanup vocabulary for query authors.

Every function returns a new DataFrame and never mutates its input.
"""

import polars as pl


def _text(column: str) -> pl.Expr:
    return pl.col(column).cast(pl.String)


def lowercase(df: pl.DataFrame, column: str) -> pl.DataFrame:
    return df.with_columns(_text(column).str.to_lowercase())


def uppercase(df: pl.DataFrame, column: str) -> pl.DataFrame:
    return df.with_columns(_text(column).str.to_uppercase())


def proper_case(df: pl.DataFrame, column: str) -> pl.DataFrame:
    return df.with_columns(_text(column).str.to_titlecase())


def trim(df: pl.DataFrame, column: str) -> pl.DataFrame:
    return df.with_columns(_text(column).str.strip_chars())


def clean(df: pl.DataFrame, column: str) -> pl.DataFrame:
    return df.with_columns(
        _text(column)
        .str.replace_all(r"[\x00-\x1F\x7F-\x9F]", "")
        .alias(column)
    )


def replace_values(
    df: pl.DataFrame,
    column: str,
    replacements: dict,
    new_column: str | None = None,
) -> pl.DataFrame:
    target = new_column if new_column is not None else column
    return df.with_columns(pl.col(column).replace(replacements).alias(target))


def split_column_by_delimiter(
    df: pl.DataFrame,
    column: str,
    delimiter: str,
    new_columns: list[str],
) -> pl.DataFrame:
    if len(new_columns) < 2:
        raise ValueError("split_column_by_delimiter requires at least two new columns.")
    parts = (
        _text(column)
        .str.splitn(delimiter, len(new_columns))
        .struct.rename_fields(new_columns)
        .alias("__split_parts")
    )
    return df.with_columns(parts).unnest("__split_parts")


def combine_columns(
    df: pl.DataFrame,
    columns: list[str],
    new_column: str,
    separator: str = "",
    ignore_nulls: bool = False,
) -> pl.DataFrame:
    return df.with_columns(
        pl.concat_str(columns, separator=separator, ignore_nulls=ignore_nulls).alias(
            new_column
        )
    )


def pad_left(
    df: pl.DataFrame,
    column: str,
    length: int,
    character: str = "0",
    new_column: str | None = None,
) -> pl.DataFrame:
    if len(character) != 1:
        raise ValueError("pad_left character must be exactly one character.")
    target = new_column if new_column is not None else column
    return df.with_columns(
        _text(column).str.pad_start(length, character).alias(target)
    )


def left_chars(
    df: pl.DataFrame,
    column: str,
    length: int,
    new_column: str | None = None,
) -> pl.DataFrame:
    target = new_column if new_column is not None else column
    return df.with_columns(_text(column).str.slice(0, length).alias(target))


def right_chars(
    df: pl.DataFrame,
    column: str,
    length: int,
    new_column: str | None = None,
) -> pl.DataFrame:
    target = new_column if new_column is not None else column
    return df.with_columns(_text(column).str.slice(-length, length).alias(target))


def mid_chars(
    df: pl.DataFrame,
    column: str,
    start: int,
    length: int,
    new_column: str | None = None,
) -> pl.DataFrame:
    target = new_column if new_column is not None else column
    return df.with_columns(_text(column).str.slice(start, length).alias(target))
