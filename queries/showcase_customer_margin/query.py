"""Deliverable query: customer net sales and gross margin.

This showcase query consumes two component queries:

- `showcase_sales_base` provides clean order lines and net sales.
- `showcase_product_margin` provides clean product costs.

The final report joins the two components, calculates line cost and gross
margin, groups by customer, adds a business segment, and presents user-facing
column names.
"""

from engine.validator import expect_columns, expect_non_empty
from functions.columns import add_literal_column, conditional_column, keep_columns
from functions.joins import merge
from functions.reshaping import group
from functions.transforms import divide, multiply, rename, sort, subtract

DEPENDS_ON = ["showcase_sales_base", "showcase_product_margin"]


def load():
    return {}


def run(data):
    sales = data["showcase_sales_base"]
    products = data["showcase_product_margin"]

    expect_non_empty(sales, "showcase_sales_base")
    expect_columns(
        sales,
        [
            "order_id",
            "customer_id",
            "customer_name",
            "region",
            "order_date",
            "fiscal_year",
            "product_id",
            "units",
            "net_sales",
        ],
    )
    expect_non_empty(products, "showcase_product_margin")
    expect_columns(products, ["product_id", "unit_cost", "currency"])

    lines = merge(sales, products, on="product_id")
    lines = multiply(lines, "unit_cost", "units", "line_cost")
    lines = subtract(lines, "net_sales", "line_cost", "gross_margin")

    summary = group(
        lines,
        ["customer_id", "customer_name", "region", "fiscal_year"],
        [
            ("sum", "net_sales", "total_sales"),
            ("sum", "gross_margin", "gross_margin"),
            ("count", None, "orders"),
            ("min", "order_date", "first_order"),
        ],
    )
    summary = divide(summary, "gross_margin", "total_sales", "margin_rate", places=4)
    summary = conditional_column(
        summary,
        "total_sales",
        "at_least",
        700,
        "Priority",
        "Standard",
        "segment",
    )
    summary = add_literal_column(summary, "currency", "USD")

    summary = sort(summary, "total_sales", descending=True)
    summary = rename(summary, "customer_id", "Customer ID")
    summary = rename(summary, "customer_name", "Customer")
    summary = rename(summary, "region", "Region")
    summary = rename(summary, "fiscal_year", "Fiscal Year")
    summary = rename(summary, "orders", "Orders")
    summary = rename(summary, "total_sales", "Net Sales")
    summary = rename(summary, "gross_margin", "Gross Margin")
    summary = rename(summary, "margin_rate", "Margin Rate")
    summary = rename(summary, "segment", "Segment")
    summary = rename(summary, "first_order", "First Order")
    summary = rename(summary, "currency", "Currency")

    return keep_columns(
        summary,
        [
            "Customer ID",
            "Customer",
            "Region",
            "Fiscal Year",
            "Orders",
            "Net Sales",
            "Gross Margin",
            "Margin Rate",
            "Segment",
            "First Order",
            "Currency",
        ],
    )
