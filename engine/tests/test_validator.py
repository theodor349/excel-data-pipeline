import pandas
import pytest

from engine.validator import expect_columns, expect_non_empty


def make_df(*columns, rows=1):
    data = {col: ["x"] * rows for col in columns}
    return pandas.DataFrame(data)


def test_expect_columns_passes_when_all_present():
    df = make_df("a", "b", "c")
    expect_columns(df, ["a", "b", "c"])


def test_expect_columns_passes_with_extra_columns():
    df = make_df("a", "b", "c", "extra")
    expect_columns(df, ["a", "b"])


def test_expect_columns_raises_on_missing_columns():
    df = make_df("a", "b")
    with pytest.raises(ValueError) as exc_info:
        expect_columns(df, ["a", "b", "c", "d"], source_name="sales")
    message = str(exc_info.value)
    assert "sales" in message
    assert "c" in message
    assert "d" in message


def test_expect_columns_message_lists_only_missing_columns():
    df = make_df("present_col", "b")
    with pytest.raises(ValueError) as exc_info:
        expect_columns(df, ["present_col", "missing_col"], source_name="inventory")
    message = str(exc_info.value)
    assert "missing_col" in message
    assert "present_col" not in message


def test_expect_non_empty_passes_on_non_empty_df():
    df = make_df("a", rows=3)
    expect_non_empty(df, "sales")


def test_expect_non_empty_raises_on_zero_rows():
    df = make_df("a", rows=0)
    with pytest.raises(ValueError) as exc_info:
        expect_non_empty(df, "sales")
    assert "sales" in str(exc_info.value)


def test_expect_columns_passes_on_df_with_columns_but_zero_rows():
    df = make_df("a", "b", rows=0)
    expect_columns(df, ["a", "b"])
