#!/usr/bin/env python3
"""
Test script to verify that the checker can handle missing required fields
by assigning default values and continuing with validation.
"""

import os
import sys

# Add the project root directory to Python path to use local modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from pabulib.checker import Checker

# Test data with missing required num_votes field
test_data_missing_num_votes = """META
description;Test instance with missing num_votes
country;Poland
unit;Test
instance;2024
num_projects;2
budget;1000
vote_type;approval
rule;greedy
date_begin;2024
date_end;2024

PROJECTS
project_id;cost;votes;name
p1;500;10;Project 1
p2;600;5;Project 2

VOTES
voter_id;vote
v1;p1
v2;p1,p2
v3;p2
"""


def test_missing_required_field():
    """Test that missing required fields are handled gracefully."""
    print("Testing missing required field handling...")

    # Create checker instance
    checker = Checker()

    # Process the test data
    results = checker.process_files([test_data_missing_num_votes])

    # Print results
    print(f"Processed files: {results['metadata']['processed']}")
    print(f"Valid files: {results['metadata']['valid']}")
    print(f"Invalid files: {results['metadata']['invalid']}")

    # Check if we have errors but processing continued
    if results["metadata"]["processed"] > 0:
        print("✓ File was processed successfully")

        # Get the first (and only) file result
        file_key = next(
            (k for k in results.keys() if k != "metadata" and k != "summary"), None
        )
        if file_key and "results" in results[file_key]:
            file_results = results[file_key]["results"]

            if isinstance(file_results, dict) and "errors" in file_results:
                print("\n=== ERRORS FOUND ===")
                for error_type, error_details in file_results["errors"].items():
                    print(f"{error_type}: {error_details}")

                # Check specifically for missing field error
                if "missing meta field value" in file_results["errors"]:
                    print("✓ Missing required field was detected and reported")
                else:
                    print("⚠ Missing required field was not detected")

                # Check if other validations ran (indicating processing continued)
                if len(file_results["errors"]) > 1:
                    print("✓ Other validations ran, indicating processing continued")
                else:
                    print("⚠ Only one error found, other validations may not have run")
            else:
                print("✓ No errors found (unexpected for this test)")
        else:
            print("✗ Could not find file results")
    else:
        print("✗ File was not processed")


if __name__ == "__main__":
    test_missing_required_field()
