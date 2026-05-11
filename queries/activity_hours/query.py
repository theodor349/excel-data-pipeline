import polars as pl

from engine.loader import read_jsonl
from engine.validator import expect_columns, expect_non_empty
from functions.aggregations import min, sum
from functions.joins import merge
from functions.transforms import keep_columns, rename


def load():
    return {
        "activities": read_jsonl("activities"),
        "categories": read_jsonl("categories"),
        "entries": read_jsonl("entries"),
        "entry_activities": read_jsonl("entry_activities"),
    }


def run(data):
    activities = data["activities"]
    categories = data["categories"]
    entries = data["entries"]
    entry_activities = data["entry_activities"]

    expect_non_empty(activities, "activities")
    expect_columns(activities, ["_id", "displayName", "categoryId"])
    expect_non_empty(categories, "categories")
    expect_columns(categories, ["_id", "displayName"])
    expect_non_empty(entries, "entries")
    expect_columns(entries, ["_id", "startTime", "duration"])
    expect_non_empty(entry_activities, "entry_activities")
    expect_columns(entry_activities, ["activityId", "entryId"])

    entries = entries.with_columns([
        pl.col("startTime").cast(pl.Datetime(time_unit="ms")),
        (pl.col("duration") / 3_600_000.0).alias("hours"),
    ])

    # Polars join with left_on/right_on drops the right key; conflicting non-key
    # columns get a "_right" suffix.
    activities = merge(activities, categories, left_on="categoryId", right_on="_id")
    activities = rename(activities, "displayName_right", "category")
    activities = keep_columns(activities, ["_id", "displayName", "category"])

    joined = merge(entry_activities, entries, left_on="entryId", right_on="_id")
    joined = merge(joined, activities, left_on="activityId", right_on="_id")
    joined = keep_columns(joined, ["displayName", "category", "hours", "startTime"])

    group_cols = ["displayName", "category"]
    total_hours = sum(joined, group_cols, "hours")
    first_entry = min(joined, group_cols, "startTime")
    first_entry = first_entry.with_columns(pl.col("startTime").dt.date())

    result = merge(total_hours, first_entry, on=group_cols)
    result = rename(result, "startTime", "first_entry")
    result = rename(result, "displayName", "Activity")
    result = rename(result, "category", "Category")
    result = rename(result, "hours", "Hours")
    result = rename(result, "first_entry", "First Entry")
    result = result.sort("Hours", descending=True)
    result = keep_columns(result, ["Category", "Activity", "Hours", "First Entry"])

    return {"ActivityHours": result}
