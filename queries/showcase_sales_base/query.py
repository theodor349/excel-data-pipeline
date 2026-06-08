"""Component query: clean order lines and calculate net sales.

This is the first component used by `showcase_customer_margin`. It turns a raw
order file into a clean, reusable sales table: customer and region names are
standardized, cancelled rows are removed, dates are converted, money is kept as
Decimal, and each order line gets a net-sales amount.
"""

from engine.loader import read_csv
from engine.validator import expect_columns, expect_non_empty
from functions.columns import conditional_column, keep_columns
from functions.filters import filter_not_equal
from functions.text import clean, lowercase, proper_case, replace_values, trim, uppercase
from functions.transforms import (
    fiscal_year,
    multiply,
    sort,
    subtract,
    to_date,
    to_decimal,
    to_int,
)


def load():
    return {"orders": read_csv("showcase_orders")}


def run(data):
    orders = data["orders"]

    expect_non_empty(orders, "orders")
    expect_columns(
        orders,
        [
            "order_id",
            "customer_id",
            "customer_name",
            "region",
            "order_date",
            "product_id",
            "units",
            "unit_price",
            "discount",
            "status",
        ],
    )

    orders = clean(orders, "customer_name")
    orders = trim(orders, "customer_name")
    orders = proper_case(orders, "customer_name")
    orders = lowercase(orders, "region")
    orders = replace_values(orders, "region", {"n": "north", "s": "south", "e": "east", "w": "west"})
    orders = lowercase(orders, "status")
    orders = filter_not_equal(orders, "status", "cancelled")

    orders = uppercase(orders, "product_id")
    orders = to_date(orders, "order_date")
    orders = fiscal_year(orders, "order_date", fy_start_month=7, new_column="fiscal_year")
    orders = to_int(orders, "units")
    orders = to_decimal(orders, "unit_price", places=2)
    orders = to_decimal(orders, "discount", places=2)

    orders = multiply(orders, "unit_price", "units", "line_sales")
    orders = subtract(orders, "line_sales", "discount", "net_sales")
    orders = conditional_column(
        orders,
        "net_sales",
        "at_least",
        500,
        "Large",
        "Standard",
        "order_size",
    )

    orders = keep_columns(
        orders,
        [
            "order_id",
            "customer_id",
            "customer_name",
            "region",
            "order_date",
            "fiscal_year",
            "product_id",
            "units",
            "unit_price",
            "discount",
            "net_sales",
            "order_size",
        ],
    )
    return sort(orders, "order_id")
