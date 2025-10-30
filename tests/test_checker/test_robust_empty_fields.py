#!/usr/bin/env python3
"""
Unit test for handling empty field values (key present but no value).
"""

import os
import sys
import unittest
from copy import deepcopy

# Add the project root directory to Python path to use local modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from pabulib.checker import Checker


class TestRobustEmptyFields(unittest.TestCase):
    """Test cases for handling empty field values."""

    def setUp(self):
        """Set up the Checker instance for unit tests."""
        self.checker = Checker()

    def test_empty_required_field_value(self):
        """
        Test that empty required field values are properly handled.
        When a key is present but has no value (e.g., num_votes;), it should:
        1. Be detected as an invalid/empty value
        2. Allow processing to continue
        3. Report appropriate errors
        """
        # Test data with empty num_votes value
        test_data = """META
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

        # Process the test data
        results = self.checker.process_files([test_data])

        # Verify file was processed
        self.assertEqual(results["metadata"]["processed"], 1)
        self.assertEqual(
            results["metadata"]["invalid"], 1
        )  # Should be invalid due to errors

        # Get the file results
        file_key = next(
            (k for k in results.keys() if k != "metadata" and k != "summary"), None
        )
        self.assertIsNotNone(file_key)

        file_results = results[file_key]["results"]
        self.assertIsInstance(file_results, dict)
        self.assertIn("errors", file_results)

        errors = file_results["errors"]

        # Check that empty field value is detected
        # This could be either 'invalid meta field value' or other appropriate error type
        has_empty_field_error = (
            "invalid meta field value" in errors
            or "missing meta field value" in errors
            or "incorrect meta field datatype" in errors
        )
        self.assertTrue(
            has_empty_field_error, "Empty field value not detected properly"
        )

        # Check that vote count validation still runs (indicating processing continued)
        self.assertIn(
            "missing num_votes field",
            errors,
            "Vote count validation did not run - processing may have stopped",
        )

        # Verify the vote count error shows the expected mismatch
        vote_error = errors["missing num_votes field"][1]
        self.assertIn(
            "but found 3 votes in file", vote_error
        )  # Should show the actual vote count
        self.assertIn("3", vote_error)  # Should show 3 actual votes

    def test_multiple_empty_required_fields(self):
        """
        Test handling of multiple empty required field values.
        """
        test_data = """META
description;
country;Poland
unit;Test
instance;2024
num_projects;
num_votes;
budget;
vote_type;approval
rule;greedy
date_begin;2024
date_end;2024

PROJECTS
project_id;cost;votes;name
p1;500;10;Project 1

VOTES
voter_id;vote
v1;p1
"""

        # Process the test data
        results = self.checker.process_files([test_data])

        # Verify file was processed despite multiple empty fields
        self.assertEqual(results["metadata"]["processed"], 1)

        # Get the file results
        file_key = next(
            (k for k in results.keys() if k != "metadata" and k != "summary"), None
        )
        file_results = results[file_key]["results"]

        # Should have errors but processing should have continued
        self.assertIsInstance(file_results, dict)
        self.assertIn("errors", file_results)

        # Should have multiple field validation errors
        errors = file_results["errors"]
        error_count = sum(len(error_dict) for error_dict in errors.values())
        self.assertGreater(
            error_count, 1, "Should have multiple errors for empty fields"
        )


if __name__ == "__main__":
    unittest.main()
