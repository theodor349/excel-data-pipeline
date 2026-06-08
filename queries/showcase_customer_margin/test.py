# Dependencies are supplied as canned fixtures. The two component queries are
# tested separately, and this test checks only the final join/grouping logic.
TESTS = [
    {
        "name": "Happy Path",
        "FIXTURES": {
            "showcase_sales_base": "testData/happy_path/showcase_sales_base.csv",
            "showcase_product_margin": "testData/happy_path/showcase_product_margin.csv",
        },
        "EXPECTED": "testData/happy_path/expected.csv",
    },
]
