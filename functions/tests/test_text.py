import polars as pl
import pytest

from functions.text import (
    clean,
    combine_columns,
    left_chars,
    lowercase,
    mid_chars,
    pad_left,
    proper_case,
    replace_values,
    right_chars,
    split_column_by_delimiter,
    trim,
    uppercase,
)


# ---------------------------------------------------------------------------
# lowercase
# ---------------------------------------------------------------------------

def test_lowercase_basic():
    df = pl.DataFrame({"name": ["Alice", "BOB", "carol"]})
    result = lowercase(df, "name")
    assert result["name"].to_list() == ["alice", "bob", "carol"]


def test_lowercase_preserves_nan():
    df = pl.DataFrame({"name": ["Alice", None]})
    result = lowercase(df, "name")
    assert result["name"][0] == "alice"
    assert result["name"][1] is None


def test_lowercase_does_not_mutate():
    df = pl.DataFrame({"name": ["Alice"]})
    lowercase(df, "name")
    assert df["name"][0] == "Alice"


# ---------------------------------------------------------------------------
# text cleanup
# ---------------------------------------------------------------------------

def test_uppercase_basic():
    df = pl.DataFrame({"code": ["ab", "Cd"]})
    result = uppercase(df, "code")
    assert result["code"].to_list() == ["AB", "CD"]


def test_uppercase_preserves_null():
    df = pl.DataFrame({"code": ["ab", None]})
    result = uppercase(df, "code")
    assert result["code"].to_list() == ["AB", None]


def test_uppercase_does_not_mutate():
    df = pl.DataFrame({"code": ["ab"]})
    uppercase(df, "code")
    assert df["code"].to_list() == ["ab"]


def test_proper_case_basic():
    df = pl.DataFrame({"name": ["north region", "SALES"]})
    result = proper_case(df, "name")
    assert result["name"].to_list() == ["North Region", "Sales"]


def test_proper_case_preserves_null():
    df = pl.DataFrame({"name": ["north", None]})
    result = proper_case(df, "name")
    assert result["name"].to_list() == ["North", None]


def test_proper_case_does_not_mutate():
    df = pl.DataFrame({"name": ["north region"]})
    proper_case(df, "name")
    assert df["name"].to_list() == ["north region"]


def test_trim_strips_outer_spaces():
    df = pl.DataFrame({"name": ["  North  ", "\tSales\n", "Already clean"]})
    result = trim(df, "name")
    assert result["name"].to_list() == ["North", "Sales", "Already clean"]


def test_trim_preserves_null():
    df = pl.DataFrame({"name": ["  North  ", None]})
    result = trim(df, "name")
    assert result["name"].to_list() == ["North", None]


def test_trim_does_not_mutate():
    df = pl.DataFrame({"name": ["  North  "]})
    trim(df, "name")
    assert df["name"].to_list() == ["  North  "]


def test_clean_removes_non_printing_characters():
    df = pl.DataFrame({"name": ["A\x00B\x1fC", "Line\nBreak", "Plain"]})
    result = clean(df, "name")
    assert result["name"].to_list() == ["ABC", "LineBreak", "Plain"]


def test_clean_preserves_null():
    df = pl.DataFrame({"name": ["A\x00B", None]})
    result = clean(df, "name")
    assert result["name"].to_list() == ["AB", None]


def test_clean_does_not_mutate():
    df = pl.DataFrame({"name": ["A\x00B"]})
    clean(df, "name")
    assert df["name"].to_list() == ["A\x00B"]


def test_replace_values_basic():
    df = pl.DataFrame({"status": ["N/A", "10", "N/A"]})
    result = replace_values(df, "status", {"N/A": "0"})
    assert result["status"].to_list() == ["0", "10", "0"]


def test_replace_values_category_inline():
    df = pl.DataFrame({"category": ["Old", "Keep", "Old"]})
    result = replace_values(df, "category", {"Old": "New"})
    assert result["category"].to_list() == ["New", "Keep", "New"]


def test_replace_values_new_column_keeps_original():
    df = pl.DataFrame({"status": ["N/A", "10"]})
    result = replace_values(df, "status", {"N/A": "0"}, new_column="fixed_status")
    assert result["status"].to_list() == ["N/A", "10"]
    assert result["fixed_status"].to_list() == ["0", "10"]


def test_replace_values_preserves_null():
    df = pl.DataFrame({"status": ["N/A", None]})
    result = replace_values(df, "status", {"N/A": "0"})
    assert result["status"].to_list() == ["0", None]


def test_replace_values_does_not_mutate():
    df = pl.DataFrame({"status": ["N/A"]})
    replace_values(df, "status", {"N/A": "0"})
    assert df["status"].to_list() == ["N/A"]


def test_split_column_by_delimiter_basic():
    df = pl.DataFrame({"combined": ["North-Sales", "South-Finance"]})
    result = split_column_by_delimiter(
        df, "combined", "-", ["region", "department"]
    )
    assert result["region"].to_list() == ["North", "South"]
    assert result["department"].to_list() == ["Sales", "Finance"]


def test_split_column_by_delimiter_keeps_remainder_in_last_column():
    df = pl.DataFrame({"combined": ["North-Sales-East"]})
    result = split_column_by_delimiter(
        df, "combined", "-", ["region", "department"]
    )
    assert result["region"].to_list() == ["North"]
    assert result["department"].to_list() == ["Sales-East"]


def test_split_column_by_delimiter_missing_part_is_null():
    df = pl.DataFrame({"combined": ["North"]})
    result = split_column_by_delimiter(
        df, "combined", "-", ["region", "department"]
    )
    assert result["region"].to_list() == ["North"]
    assert result["department"].to_list() == [None]


def test_split_column_by_delimiter_preserves_null():
    df = pl.DataFrame({"combined": [None]})
    result = split_column_by_delimiter(
        df, "combined", "-", ["region", "department"]
    )
    assert result["region"].to_list() == [None]
    assert result["department"].to_list() == [None]


def test_split_column_by_delimiter_requires_two_columns():
    df = pl.DataFrame({"combined": ["North-Sales"]})
    with pytest.raises(ValueError, match="at least two"):
        split_column_by_delimiter(df, "combined", "-", ["region"])


def test_split_column_by_delimiter_does_not_mutate():
    df = pl.DataFrame({"combined": ["North-Sales"]})
    split_column_by_delimiter(df, "combined", "-", ["region", "department"])
    assert df.columns == ["combined"]


def test_combine_columns_basic():
    df = pl.DataFrame({"region": ["North"], "year": [2026]})
    result = combine_columns(df, ["region", "year"], "key", separator="-")
    assert result["key"].to_list() == ["North-2026"]


def test_combine_columns_without_separator():
    df = pl.DataFrame({"a": ["A"], "b": ["B"]})
    result = combine_columns(df, ["a", "b"], "key")
    assert result["key"].to_list() == ["AB"]


def test_combine_columns_null_default_returns_null():
    df = pl.DataFrame({"region": [None], "year": [2026]})
    result = combine_columns(df, ["region", "year"], "key", separator="-")
    assert result["key"].to_list() == [None]


def test_combine_columns_can_ignore_nulls():
    df = pl.DataFrame({"region": [None], "year": [2026]})
    result = combine_columns(
        df, ["region", "year"], "key", separator="-", ignore_nulls=True
    )
    assert result["key"].to_list() == ["2026"]


def test_combine_columns_does_not_mutate():
    df = pl.DataFrame({"region": ["North"], "year": [2026]})
    combine_columns(df, ["region", "year"], "key", separator="-")
    assert "key" not in df.columns


def test_pad_left_adds_leading_zeros():
    df = pl.DataFrame({"account": ["420", "00042", None]})
    result = pad_left(df, "account", 5)
    assert result["account"].to_list() == ["00420", "00042", None]


def test_pad_left_casts_numbers_to_text():
    df = pl.DataFrame({"account": [420]})
    result = pad_left(df, "account", 5)
    assert result["account"].to_list() == ["00420"]


def test_pad_left_custom_character_and_new_column():
    df = pl.DataFrame({"account": ["42"]})
    result = pad_left(df, "account", 4, character="X", new_column="padded")
    assert result["account"].to_list() == ["42"]
    assert result["padded"].to_list() == ["XX42"]


def test_pad_left_rejects_multi_character_pad():
    df = pl.DataFrame({"account": ["42"]})
    with pytest.raises(ValueError, match="exactly one"):
        pad_left(df, "account", 4, character="00")


def test_pad_left_does_not_mutate():
    df = pl.DataFrame({"account": ["420"]})
    pad_left(df, "account", 5)
    assert df["account"].to_list() == ["420"]


def test_left_chars_basic():
    df = pl.DataFrame({"code": ["ABCDE", None]})
    result = left_chars(df, "code", 2)
    assert result["code"].to_list() == ["AB", None]


def test_left_chars_new_column_keeps_original():
    df = pl.DataFrame({"code": ["ABCDE"]})
    result = left_chars(df, "code", 2, new_column="prefix")
    assert result["code"].to_list() == ["ABCDE"]
    assert result["prefix"].to_list() == ["AB"]


def test_left_chars_does_not_mutate():
    df = pl.DataFrame({"code": ["ABCDE"]})
    left_chars(df, "code", 2)
    assert df["code"].to_list() == ["ABCDE"]


def test_right_chars_basic():
    df = pl.DataFrame({"code": ["ABCDE", None]})
    result = right_chars(df, "code", 2)
    assert result["code"].to_list() == ["DE", None]


def test_right_chars_new_column_keeps_original():
    df = pl.DataFrame({"code": ["ABCDE"]})
    result = right_chars(df, "code", 2, new_column="suffix")
    assert result["code"].to_list() == ["ABCDE"]
    assert result["suffix"].to_list() == ["DE"]


def test_right_chars_does_not_mutate():
    df = pl.DataFrame({"code": ["ABCDE"]})
    right_chars(df, "code", 2)
    assert df["code"].to_list() == ["ABCDE"]


def test_mid_chars_zero_based_start():
    df = pl.DataFrame({"code": ["ABCDE", None]})
    result = mid_chars(df, "code", start=1, length=3)
    assert result["code"].to_list() == ["BCD", None]


def test_mid_chars_new_column_keeps_original():
    df = pl.DataFrame({"code": ["ABCDE"]})
    result = mid_chars(df, "code", start=1, length=3, new_column="middle")
    assert result["code"].to_list() == ["ABCDE"]
    assert result["middle"].to_list() == ["BCD"]


def test_mid_chars_does_not_mutate():
    df = pl.DataFrame({"code": ["ABCDE"]})
    mid_chars(df, "code", start=1, length=3)
    assert df["code"].to_list() == ["ABCDE"]
