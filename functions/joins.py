import pandas as pd
from pandas import DataFrame

_VALID_HOW = ("left", "inner", "outer", "right")


def merge(
    left: DataFrame,
    right: DataFrame,
    on=None,
    left_on=None,
    right_on=None,
    how: str = "left",
) -> DataFrame:
    if how not in _VALID_HOW:
        raise ValueError(
            f"Invalid how={how!r}. Must be one of: {', '.join(_VALID_HOW)}"
        )
    if on is None and not (left_on is not None and right_on is not None):
        raise ValueError(
            "Provide either 'on' (same column name on both sides) "
            "or both 'left_on' and 'right_on'."
        )
    return pd.merge(left, right, on=on, left_on=left_on, right_on=right_on, how=how)


def append(top: DataFrame, bottom: DataFrame) -> DataFrame:
    top_cols = set(top.columns)
    bottom_cols = set(bottom.columns)
    missing_in_top = bottom_cols - top_cols
    missing_in_bottom = top_cols - bottom_cols
    if missing_in_top or missing_in_bottom:
        raise ValueError(
            f"Column mismatch: missing in top={sorted(missing_in_top)}, "
            f"missing in bottom={sorted(missing_in_bottom)}"
        )
    return pd.concat([top, bottom], ignore_index=True)
