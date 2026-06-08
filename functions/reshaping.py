import polars as pl

from functions import aggregations


def unpivot(
    df: pl.DataFrame,
    columns: str | list[str],
    index: str | list[str],
    variable_name: str = "variable",
    value_name: str = "value",
) -> pl.DataFrame:
    return df.unpivot(
        on=columns,
        index=index,
        variable_name=variable_name,
        value_name=value_name,
    )


def pivot(
    df: pl.DataFrame,
    index: str | list[str],
    columns: str,
    values: str,
    aggregate_function: str | None = None,
    sort_columns: bool = False,
) -> pl.DataFrame:
    return df.pivot(
        on=columns,
        index=index,
        values=values,
        aggregate_function=aggregate_function,
        sort_columns=sort_columns,
    )


def fill_down(df: pl.DataFrame, columns: str | list[str]) -> pl.DataFrame:
    return df.with_columns(pl.col(columns).fill_null(strategy="forward"))


def fill_up(df: pl.DataFrame, columns: str | list[str]) -> pl.DataFrame:
    return df.with_columns(pl.col(columns).fill_null(strategy="backward"))


def group(
    df: pl.DataFrame,
    group_by: str | list[str],
    aggregation_specs: list[tuple] | list[dict],
) -> pl.DataFrame:
    group_by = _normalize_columns(group_by)
    if not aggregation_specs:
        raise ValueError("aggregation_specs must not be empty")

    result = None
    for spec in aggregation_specs:
        function_name, column, alias = _parse_aggregation_spec(spec)
        partial = _aggregate(df, group_by, function_name, column)
        value_column = "count" if function_name == "count" else column
        if alias != value_column:
            partial = partial.rename({value_column: alias})
        result = partial if result is None else result.join(partial, on=group_by)

    return result


def _normalize_columns(columns: str | list[str]) -> list[str]:
    return [columns] if isinstance(columns, str) else columns


def _parse_aggregation_spec(spec: tuple | dict) -> tuple[str, str | None, str]:
    if isinstance(spec, dict):
        function_name = spec.get("function") or spec.get("op")
        column = spec.get("column")
        alias = spec.get("alias") or spec.get("as")
    else:
        if len(spec) not in (2, 3):
            raise ValueError("aggregation tuple must be (function, column[, alias])")
        function_name = spec[0]
        column = spec[1]
        alias = spec[2] if len(spec) == 3 else None

    if function_name not in {"sum", "count", "avg", "min", "max"}:
        raise ValueError(f"unsupported aggregation function: {function_name}")
    if function_name != "count" and column is None:
        raise ValueError(f"{function_name} aggregation requires a column")

    default_alias = "count" if function_name == "count" else column
    return function_name, column, alias or default_alias


def _aggregate(
    df: pl.DataFrame,
    group_by: list[str],
    function_name: str,
    column: str | None,
) -> pl.DataFrame:
    if function_name == "count":
        return aggregations.count(df, group_by)

    aggregate = getattr(aggregations, function_name)
    return aggregate(df, group_by, column)
