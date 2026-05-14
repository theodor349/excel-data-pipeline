import polars as pl


def avg(df: pl.DataFrame, group_by: str | list, column: str) -> pl.DataFrame:
    if isinstance(group_by, str):
        group_by = [group_by]

    dtype = df[column].dtype
    if isinstance(dtype, pl.Decimal):
        scale = dtype.scale
        return df.group_by(group_by).agg(
            pl.col(column).mean().cast(pl.Decimal(scale=scale))
        )

    return df.group_by(group_by).agg(pl.col(column).mean())


def sum(df: pl.DataFrame, group_by: str | list, column: str) -> pl.DataFrame:
    if isinstance(group_by, str):
        group_by = [group_by]

    return df.group_by(group_by).agg(pl.col(column).sum())


def count(df: pl.DataFrame, group_by: str | list) -> pl.DataFrame:
    if isinstance(group_by, str):
        group_by = [group_by]

    return df.group_by(group_by).agg(pl.len().alias("count"))


def min(df: pl.DataFrame, group_by: str | list, column: str) -> pl.DataFrame:
    if isinstance(group_by, str):
        group_by = [group_by]

    return df.group_by(group_by).agg(pl.col(column).min())


def max(df: pl.DataFrame, group_by: str | list, column: str) -> pl.DataFrame:
    if isinstance(group_by, str):
        group_by = [group_by]

    return df.group_by(group_by).agg(pl.col(column).max())
