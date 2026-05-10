from engine.loader import read_csv, read_excel
from engine.validator import expect_columns, expect_non_empty
from functions.aggregations import sum
from functions.joins import merge
from functions.transforms import fiscal_year, to_date, to_decimal


def load():
    return {
        "sales": read_excel("sales", "Sheet1"),
        "params": read_csv("params"),
    }


def run(data):
    sales = data["sales"]
    params = data["params"]

    expect_non_empty(sales, "sales")
    expect_columns(sales, ["date", "region", "amount"])
    expect_non_empty(params, "params")
    expect_columns(params, ["fiscal_year"])

    sales = to_date(sales, "date")
    sales = to_decimal(sales, "amount", places=2)
    sales = fiscal_year(sales, "date", fy_start_month=7)

    in_scope = merge(sales, params, on="fiscal_year", how="inner")

    summary = sum(in_scope, "region", "amount")

    return {"Summary": summary}
