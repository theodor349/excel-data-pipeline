"""Component query: normalize product costs for margin reporting.

This is the second component used by `showcase_customer_margin`. It prepares a
single clean product-cost lookup table so downstream queries can join order
lines to exact Decimal unit costs.
"""

from engine.loader import read_csv
from engine.validator import expect_columns, expect_non_empty
from functions.columns import add_literal_column, keep_columns
from functions.filters import remove_duplicates
from functions.text import proper_case, trim, uppercase
from functions.transforms import sort, to_decimal


def load():
    return {"products": read_csv("showcase_products")}


def run(data):
    products = data["products"]

    expect_non_empty(products, "products")
    expect_columns(products, ["product_id", "product_name", "category", "unit_cost"])

    products = uppercase(products, "product_id")
    products = trim(products, "product_name")
    products = proper_case(products, "product_name")
    products = trim(products, "category")
    products = proper_case(products, "category")
    products = to_decimal(products, "unit_cost", places=2)
    products = remove_duplicates(products, ["product_id"])
    products = add_literal_column(products, "currency", "USD")

    products = keep_columns(
        products,
        ["product_id", "product_name", "category", "unit_cost", "currency"],
    )
    return sort(products, "product_id")
