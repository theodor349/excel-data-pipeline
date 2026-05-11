from decimal import Decimal

import polars as pl
import pytest

from functions.joins import append, merge


def _left():
    return pl.DataFrame({"id": [1, 2, 3], "val": ["a", "b", "c"]})


def _right():
    return pl.DataFrame({"id": [1, 2], "extra": ["x", "y"]})


# ---------------------------------------------------------------------------
# merge — happy paths
# ---------------------------------------------------------------------------


def test_merge_left_join_on_preserves_left_rows():
    result = merge(_left(), _right(), on="id", how="left")
    assert len(result) == 3
    assert set(result.columns) == {"id", "val", "extra"}
    assert result.filter(pl.col("id") == 3)["extra"][0] is None


def test_merge_inner_join_left_on_right_on():
    left = pl.DataFrame({"lid": [1, 2, 3], "val": ["a", "b", "c"]})
    right = pl.DataFrame({"rid": [1, 2], "extra": ["x", "y"]})
    result = merge(left, right, left_on="lid", right_on="rid", how="inner")
    assert len(result) == 2
    assert "lid" in result.columns
    assert "extra" in result.columns


# ---------------------------------------------------------------------------
# merge — validation errors
# ---------------------------------------------------------------------------


def test_merge_raises_when_no_key_given():
    with pytest.raises(ValueError, match="'on'"):
        merge(_left(), _right())


def test_merge_raises_when_only_left_on_given():
    with pytest.raises(ValueError, match="'on'"):
        merge(_left(), _right(), left_on="id")


def test_merge_raises_on_invalid_how():
    with pytest.raises(ValueError, match="left.*inner.*outer.*right"):
        merge(_left(), _right(), on="id", how="banana")


# ---------------------------------------------------------------------------
# merge — Decimal precision regression
# ---------------------------------------------------------------------------


def test_merge_preserves_decimal_column():
    left = pl.DataFrame(
        {"id": [1, 2], "amount": [Decimal("10.50"), Decimal("20.75")]},
        schema={"id": pl.Int64, "amount": pl.Object},
    )
    right = pl.DataFrame({"id": [1, 2], "label": ["A", "B"]})
    result = merge(left, right, on="id", how="left")
    assert all(isinstance(v, Decimal) for v in result["amount"])


# ---------------------------------------------------------------------------
# append — happy paths
# ---------------------------------------------------------------------------


def test_append_concatenates_rows():
    top = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
    bottom = pl.DataFrame({"a": [5], "b": [6]})
    result = append(top, bottom)
    assert len(result) == 3


def test_append_works_with_reordered_columns():
    top = pl.DataFrame({"a": [1], "b": [2], "c": [3]})
    bottom = pl.DataFrame({"b": [20], "c": [30], "a": [10]})
    result = append(top, bottom)
    assert len(result) == 2
    assert set(result.columns) == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# append — validation errors
# ---------------------------------------------------------------------------


def test_append_raises_on_column_mismatch():
    top = pl.DataFrame({"a": [1], "b": [2]})
    bottom = pl.DataFrame({"a": [3], "c": [4]})
    with pytest.raises(ValueError) as exc_info:
        append(top, bottom)
    msg = str(exc_info.value)
    assert "missing in top" in msg
    assert "missing in bottom" in msg
    assert "c" in msg
    assert "b" in msg
