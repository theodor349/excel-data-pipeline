import pandas as pd

from engine.loader import read_jsonl
from engine.validator import expect_columns, expect_non_empty
from functions.aggregations import min, sum
from functions.joins import merge
from functions.transforms import keep_columns, rename


def load():
    return {
        "activities": read_jsonl("activities"),
        "entries": read_jsonl("entries"),
        "entry_activities": read_jsonl("entry_activities"),
    }


def run(data):
    activities = data["activities"]
    entries = data["entries"]
    entry_activities = data["entry_activities"]

    expect_non_empty(activities, "activities")
    expect_columns(activities, ["_id", "displayName"])
    expect_non_empty(entries, "entries")
    expect_columns(entries, ["_id", "startTime", "duration"])
    expect_non_empty(entry_activities, "entry_activities")
    expect_columns(entry_activities, ["activityId", "entryId"])

    entries = entries.copy()
    entries["startTime"] = pd.to_datetime(entries["startTime"], unit="ms")
    entries["hours"] = entries["duration"] / 3_600_000.0

    joined = merge(entry_activities, entries, left_on="entryId", right_on="_id")
    joined = merge(joined, activities, left_on="activityId", right_on="_id")
    joined = keep_columns(joined, ["displayName", "hours", "startTime"])

    total_hours = sum(joined, "displayName", "hours")
    first_entry = min(joined, "displayName", "startTime")
    first_entry["startTime"] = first_entry["startTime"].dt.date

    result = merge(total_hours, first_entry, on="displayName")
    result = rename(result, "startTime", "first_entry")
    result = result.sort_values("hours", ascending=False)

    return {"ActivityHours": result}
