#!/usr/bin/env python3
"""
Simple script to run the robust checker on files in the examples_internal directory.
This script uses the local pabulib code, not the installed package.
"""

import argparse
import glob
import os
import sys
from pathlib import Path

# Add the project root directory to Python path to use local modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from pabulib.checker import Checker


def run_checker_on_files(verbose=False, summary_only=False):
    """Run the checker on all .pb files in the current directory."""

    # Get the current directory (examples_internal)
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Find all .pb files in the current directory
    pb_files = glob.glob(os.path.join(current_dir, "*.pb"))

    if not pb_files:
        print("No .pb files found in the examples_internal directory.")
        return

    print(f"Found {len(pb_files)} .pb file(s) to check:")
    for file in pb_files:
        print(f"  - {os.path.basename(file)}")
    print()

    # Create checker instance
    checker = Checker()

    # Process all files
    results = checker.process_files(pb_files)

    # Print summary
    print("=" * 60)
    print("CHECKER RESULTS SUMMARY")
    print("=" * 60)
    print(f"Total files processed: {results['metadata']['processed']}")
    print(f"Valid files: {results['metadata']['valid']}")
    print(f"Invalid files: {results['metadata']['invalid']}")
    print()

    # Print detailed results for each file (unless summary only)
    if not summary_only:
        for key, file_result in results.items():
            if key in ["metadata", "summary"]:
                continue

            print(f"File: {key}")
            print("-" * 40)

            if isinstance(file_result.get("results"), str):
                # File is valid
                print(f"✅ {file_result['results']}")
            elif isinstance(file_result.get("results"), dict):
                # File has errors
                file_errors = file_result["results"]

                if "errors" in file_errors:
                    print("❌ ERRORS:")
                    for error_type, error_details in file_errors["errors"].items():
                        error_count = len(error_details)
                        print(f"  • {error_type} ({error_count} instances):")

                        # For large numbers of similar errors, show only first few and summarize (unless verbose)
                        if error_count > 10 and not verbose:
                            # Show first 3 errors
                            shown_count = 0
                            for error_id, error_desc in error_details.items():
                                if shown_count < 3:
                                    print(f"    {error_id}: {error_desc}")
                                    shown_count += 1
                                else:
                                    break
                            print(f"    ... and {error_count - 3} more similar errors")
                            print(
                                f"    💡 Use --verbose to see all {error_count} errors"
                            )
                        else:
                            # Show all errors if count is manageable or verbose mode
                            for error_id, error_desc in error_details.items():
                                print(f"    {error_id}: {error_desc}")
                    print()

                if "warnings" in file_errors:
                    print("⚠️  WARNINGS:")
                    for warning_type, warning_details in file_errors[
                        "warnings"
                    ].items():
                        warning_count = len(warning_details)
                        print(f"  • {warning_type} ({warning_count} instances):")

                        # Show all warnings since they're usually fewer
                        for warning_id, warning_desc in warning_details.items():
                            print(f"    {warning_id}: {warning_desc}")
                    print()

            if "webpage_name" in file_result:
                print(f"📝 Webpage name: {file_result['webpage_name']}")

            print()

    # Print error summary if available
    if "summary" in results and results["summary"]:
        print("ERROR TYPE SUMMARY:")
        print("-" * 20)
        for error_type, count in results["summary"].items():
            print(f"{error_type}: {count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run robust checker on participatory budgeting files"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all errors, even if there are many repetitive ones",
    )
    parser.add_argument(
        "--summary",
        "-s",
        action="store_true",
        help="Show only the summary without detailed error listings",
    )
    args = parser.parse_args()

    print("Running Robust Checker on Internal Examples")
    print("=" * 50)
    print("Using LOCAL pabulib code (not installed package)")
    if args.verbose:
        print("🔍 VERBOSE MODE: Showing all errors")
    elif args.summary:
        print("📊 SUMMARY MODE: Showing only summary statistics")
    print()

    try:
        run_checker_on_files(verbose=args.verbose, summary_only=args.summary)
    except Exception as e:
        print(f"Error running checker: {e}")
        import traceback

        traceback.print_exc()
