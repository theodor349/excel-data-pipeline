TESTS = [
    {
        "name": "Happy Path",
        "FIXTURES": {
            "sales": "testData/happy_path/sales.csv",
        },
        "EXPECTED": "testData/happy_path/expected.csv",
    },
    {
        "name": "Mixed casing, three regions",
        "FIXTURES": {
            "sales": "testData/mixed_casing/sales.csv",
        },
        "EXPECTED": "testData/mixed_casing/expected.csv",
    },
]
