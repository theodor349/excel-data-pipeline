# The dependency is supplied as a CANNED fixture — region_base is never
# re-executed during this test. The fixture key must match the DEPENDS_ON name.
TESTS = [
    {
        "name": "Happy Path",
        "FIXTURES": {
            "region_base": "testData/happy_path/region_base.csv",
        },
        "EXPECTED": "testData/happy_path/expected.csv",
    },
    {
        "name": "Three regions, descending",
        "FIXTURES": {
            "region_base": "testData/three_regions/region_base.csv",
        },
        "EXPECTED": "testData/three_regions/expected.csv",
    },
]
