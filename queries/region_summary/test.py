# The dependency is supplied as a CANNED fixture — region_base is never
# re-executed during this test. The fixture key must match the DEPENDS_ON name.
FIXTURES = {
    "region_base": "testData/region_base.csv",
}
EXPECTED = "testData/expected_region_summary.csv"
