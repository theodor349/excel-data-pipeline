"""Component query: a reusable, normalized sales-by-region base table.

This query is never exported directly (it is absent from exports.json). It runs
only because `region_summary` lists it in DEPENDS_ON. Any number of other
queries could consume `region_base` the same way — that is the whole point of a
component query: write the normalization once, reuse it everywhere.
"""

from engine.loader import read_excel
from engine.validator import expect_columns, expect_non_empty
from functions.aggregations import sum
from functions.transforms import lowercase, sort, to_decimal


def load():
    return {"sales": read_excel("sales", "Sheet1")}


def run(data):
    sales = data["sales"]

    expect_non_empty(sales, "sales")
    expect_columns(sales, ["region", "amount"])

    sales = lowercase(sales, "region")          # "North"/"north" -> one region
    sales = to_decimal(sales, "amount", places=2)  # money stays Decimal

    base = sum(sales, "region", "amount")
    return sort(base, "region")
