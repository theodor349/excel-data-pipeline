import argparse
import sys
from pathlib import Path

from engine.runner import run_all, run_one
from engine.tester import test_all as run_tests_all, test_one as run_tests_one


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the data pipeline.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--all", action="store_true", help="Run every query in queries/")
    target.add_argument("--query", metavar="NAME", help="Run only the named query")
    parser.add_argument("--output", metavar="FOLDER", help="Output folder (required unless --test-only)")
    parser.add_argument("--test-only", action="store_true", help="Run fixture tests, no export, no SQL/Excel I/O")

    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parent
    queries_dir = repo_root / "queries"
    exports_path = repo_root / "exports.json"

    if args.test_only:
        if args.all:
            return run_tests_all(queries_dir)
        return run_tests_one(queries_dir, args.query)

    if not args.output:
        parser.error("--output is required for non-test runs")

    if args.all:
        return run_all(queries_dir, args.output, exports_path)
    return run_one(queries_dir, args.query, args.output, exports_path)


if __name__ == "__main__":
    sys.exit(main())
