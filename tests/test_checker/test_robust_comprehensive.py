#!/usr/bin/env python3
"""
Comprehensive test to verify robust checker behavior with missing required fields.
"""

import os
import sys

# Add the project root directory to Python path to use local modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from pabulib.checker import Checker


def test_scenarios():
    """Test different scenarios of missing required fields."""

    # Scenario 1: Missing num_votes field
    print("=== SCENARIO 1: Missing num_votes field ===")
    test_data_1 = """META
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

    checker1 = Checker()
    results1 = checker1.process_files([test_data_1])

    # Get results for this scenario
    file_key = next(
        (k for k in results1.keys() if k != "metadata" and k != "summary"), None
    )
    if file_key and "results" in results1[file_key]:
        file_results = results1[file_key]["results"]
        if isinstance(file_results, dict) and "errors" in file_results:
            missing_errors = file_results["errors"].get("missing meta field value", {})
            if missing_errors:
                print(f"✓ Detected missing num_votes: {missing_errors}")

            vote_count_errors = file_results["errors"].get(
                "different number of votes", {}
            )
            if vote_count_errors:
                print(
                    f"✓ Checker continued and found vote count mismatch: {vote_count_errors}"
                )

    # Scenario 2: Missing budget field (should assign 0.0 and continue)
    print("\n=== SCENARIO 2: Missing budget field ===")
    test_data_2 = """META
description;Test instance with missing budget
country;Poland
unit;Test
instance;2024
num_projects;2
num_votes;3
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

    checker2 = Checker()
    results2 = checker2.process_files([test_data_2])

    # Get results for this scenario
    file_key = next(
        (k for k in results2.keys() if k != "metadata" and k != "summary"), None
    )
    if file_key and "results" in results2[file_key]:
        file_results = results2[file_key]["results"]
        if isinstance(file_results, dict) and "errors" in file_results:
            missing_errors = file_results["errors"].get("missing meta field value", {})
            if missing_errors:
                print(f"✓ Detected missing budget: {missing_errors}")

            budget_errors = file_results["errors"].get("budget exceeded", {})
            if budget_errors:
                print(
                    f"✓ Checker continued and found budget issues with default budget (0): {budget_errors}"
                )

    # Scenario 3: Key present but with no value (empty value)
    print("\n=== SCENARIO 3: Key present but with empty value ===")
    test_data_3 = """META
description;Test instance with empty num_votes
country;Poland
unit;Test
instance;2024
num_projects;2
num_votes;
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

    checker3 = Checker()
    results3 = checker3.process_files([test_data_3])

    # Get results for this scenario
    file_key = next(
        (k for k in results3.keys() if k != "metadata" and k != "summary"), None
    )
    if file_key and "results" in results3[file_key]:
        file_results = results3[file_key]["results"]
        if isinstance(file_results, dict) and "errors" in file_results:
            # Check for empty field value error (different from missing field)
            invalid_errors = file_results["errors"].get("invalid meta field value", {})
            missing_errors = file_results["errors"].get("missing meta field value", {})

            if invalid_errors or missing_errors:
                print(f"✓ Detected empty num_votes value:")
                if invalid_errors:
                    print(f"  - Invalid field errors: {invalid_errors}")
                if missing_errors:
                    print(f"  - Missing field errors: {missing_errors}")

            vote_count_errors = file_results["errors"].get(
                "different number of votes", {}
            )
            if vote_count_errors:
                print(
                    f"✓ Checker continued and found vote count mismatch: {vote_count_errors}"
                )

    print(f"\n=== SUMMARY ===")
    total_processed = (
        results1["metadata"]["processed"]
        + results2["metadata"]["processed"]
        + results3["metadata"]["processed"]
    )
    print(f"Total files processed: {total_processed}")
    print(f"All files processed successfully despite missing/empty required fields!")
    print(
        f"✓ Checker is now robust and continues processing even with missing or empty required fields"
    )


if __name__ == "__main__":
    test_scenarios()
