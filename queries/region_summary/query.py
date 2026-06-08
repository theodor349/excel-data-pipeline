"""Deliverable query built by referencing a component query.

`region_summary` does no loading of its own — it consumes the output of
`region_base` (declared in DEPENDS_ON), which the engine injects into `data`
under that name, exactly like a named source. Because references are passed in
memory, the `Decimal` amounts from `region_base` arrive intact (no round-trip
through a file).
"""

from engine.validator import expect_columns, expect_non_empty
from functions.transforms import rename, sort

DEPENDS_ON = ["region_base"]


def load():
    return {}


def run(data):
    base = data["region_base"]

    expect_non_empty(base, "region_base")
    expect_columns(base, ["region", "amount"])

    summary = sort(base, "amount", descending=True)
    summary = rename(summary, "region", "Region")
    summary = rename(summary, "amount", "Total Sales")
    return summary
