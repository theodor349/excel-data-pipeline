import polars as pl


def expect_columns(df: pl.DataFrame, expected: list[str], source_name: str = "") -> None:
    missing = [col for col in expected if col not in df.columns]
    if missing:
        source = f" '{source_name}'" if source_name else ""
        raise ValueError(
            f"Source{source} is missing columns: {missing}"
        )


def expect_non_empty(df: pl.DataFrame, source_name: str = "") -> None:
    if len(df) == 0:
        source = f" '{source_name}'" if source_name else ""
        raise ValueError(f"Source{source} is empty (0 rows)")
