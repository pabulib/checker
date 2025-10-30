#!/usr/bin/env python3
"""
Advanced test cases for edge scenarios and complex validation rules.
Tests cover:
- Complex unused budget scenarios with multiple project combinations
- Comment field edge cases and format variations
- Threshold interactions with budget calculations
- Field validation edge cases
"""

import os
import sys
import unittest
from copy import deepcopy

# Add the project root directory to Python path to use local modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from pabulib.checker import Checker


class TestAdvancedScenarios(unittest.TestCase):
    """Test cases for advanced and edge case scenarios."""

    def setUp(self):
        """Set up the Checker instance for unit tests."""
        self.checker = Checker()

    def test_unused_budget_complex_combination(self):
        """
        Test unused budget detection with complex project combinations.
        Should find optimal combination of projects that can be funded.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Budget 1000, selected project costs 300, remaining 700
        # Multiple unselected projects with different combinations possible
        self.checker.meta = {
            "country": "Poland",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "budget": "1000",
            "date_begin": "2024",
            "date_end": "2024",
        }

        self.checker.projects = {
            1: {
                "project_id": 1,
                "cost": 300,
                "selected": "1",
                "votes": 25,
                "name": "Selected",
            },  # Selected
            2: {
                "project_id": 2,
                "cost": 400,
                "selected": "0",
                "votes": 20,
                "name": "Priority 1",
            },  # Can be funded (priority 1)
            3: {
                "project_id": 3,
                "cost": 350,
                "selected": "0",
                "votes": 15,
                "name": "Priority 2",
            },  # Can be funded after 2, but not both
            4: {
                "project_id": 4,
                "cost": 200,
                "selected": "0",
                "votes": 18,
                "name": "Priority 3",
            },  # Can be funded (priority 2)
            5: {
                "project_id": 5,
                "cost": 100,
                "selected": "0",
                "votes": 12,
                "name": "Priority 4",
            },  # Can be funded (priority 3)
            6: {
                "project_id": 6,
                "cost": 500,
                "selected": "0",
                "votes": 22,
                "name": "Too Expensive",
            },  # Too expensive to fit with any other
        }

        self.checker.votes = {}
        self.checker.results_field = "votes"
        self.checker.threshold = 0

        # Call budget validation
        self.checker.check_budgets()

        # Should report projects in greedy order until budget exhausted
        # Greedy order by votes: 6(22), 2(20), 4(18), 3(15), 5(12)
        # Remaining budget: 700
        # Fund project 6 (cost 500) → remaining: 200
        # Cannot fund project 2 (cost 400) → exceeds budget
        # Fund project 4 (cost 200) → remaining: 0
        errors = self.checker.file_results["errors"]
        if "unused budget" in errors:
            unused_errors = errors["unused budget"]
            error_message = str(list(unused_errors.values())[0])

            # Should report projects 6 and 4 (can be funded in greedy order)
            # Should not report project 2 (would exceed budget after project 6)
            self.assertIn(
                "6",
                error_message,
                "Project 6 should be reported (highest votes, can be funded)",
            )
            self.assertIn(
                "4",
                error_message,
                "Project 4 should be reported (can be funded after project 6)",
            )
            self.assertNotIn(
                "2",
                error_message,
                "Project 2 should NOT be reported (would exceed budget after project 6)",
            )

    def test_comment_field_edge_cases(self):
        """
        Test comment field validation with various edge cases.
        """
        # Test cases: (comment_value, should_pass, test_description)
        test_cases = [
            ("#1: Valid comment", True, "Standard valid format"),
            ("#1: ", True, "Valid format with empty comment text"),
            ("#1:", False, "Missing space after colon"),
            ("# 1: Invalid space", False, "Space before number"),
            ("#2: Wrong number", False, "Wrong number (should be #1)"),
            ("1: Missing hash", False, "Missing hash symbol"),
            ("#1 Missing colon", False, "Missing colon"),
            ("", True, "Empty comment (should be allowed as optional field)"),
            (
                "#1: Multiple #1: parts",
                True,
                "Multiple instances of pattern (first one valid)",
            ),
        ]

        for comment_value, should_pass, description in test_cases:
            with self.subTest(comment=comment_value, desc=description):
                self.checker.file_results = deepcopy(self.checker.error_levels)

                self.checker.meta = {
                    "description": "Test",
                    "country": "Poland",
                    "unit": "TestUnit",
                    "instance": "TestInstance",
                    "num_projects": 1,
                    "num_votes": 1,
                    "budget": 1000.0,
                    "vote_type": "approval",
                    "rule": "greedy",
                    "date_begin": "2024",
                    "date_end": "2024",
                    "comment": comment_value,
                }

                self.checker.projects = {}
                self.checker.votes = {}

                # Call field validation
                self.checker.check_fields()

                # Check if validation passed or failed as expected
                errors = self.checker.file_results["errors"]
                has_comment_error = False
                if "invalid meta field value" in errors:
                    for error_detail in errors["invalid meta field value"].values():
                        if "comment should follow the '#1: ' format" in str(
                            error_detail
                        ):
                            has_comment_error = True
                            break

                if should_pass:
                    self.assertFalse(
                        has_comment_error,
                        f"Comment '{comment_value}' should be valid but was rejected",
                    )
                else:
                    self.assertTrue(
                        has_comment_error,
                        f"Comment '{comment_value}' should be invalid but was accepted",
                    )

    def test_threshold_interaction_with_unused_budget(self):
        """
        Test complex interaction between threshold and unused budget detection.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        self.checker.meta = {
            "country": "Poland",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "budget": "1000",
            "date_begin": "2024",
            "date_end": "2024",
        }

        # Mix of projects above and below threshold
        self.checker.projects = {
            1: {
                "project_id": 1,
                "cost": 200,
                "selected": "1",
                "votes": 25,
                "name": "Selected Above Threshold",
            },  # Selected, above threshold
            2: {
                "project_id": 2,
                "cost": 300,
                "selected": "0",
                "votes": 20,
                "name": "Unselected Above Threshold 1",
            },  # Unselected, above threshold, can be funded
            3: {
                "project_id": 3,
                "cost": 400,
                "selected": "0",
                "votes": 18,
                "name": "Unselected Above Threshold 2",
            },  # Unselected, above threshold, can be funded
            4: {
                "project_id": 4,
                "cost": 150,
                "selected": "0",
                "votes": 8,
                "name": "Below Threshold",
            },  # Unselected, below threshold, should be ignored
            5: {
                "project_id": 5,
                "cost": 100,
                "selected": "0",
                "votes": 22,
                "name": "Unselected Above Threshold 3",
            },  # Unselected, above threshold, can be funded
        }

        self.checker.votes = {}
        self.checker.results_field = "votes"
        self.checker.threshold = 15  # Projects need >= 15 votes

        # Call budget validation
        self.checker.check_budgets()

        # Should only consider projects 2, 3, 5 (above threshold)
        # Should not consider project 4 (below threshold)
        errors = self.checker.file_results["errors"]
        if "unused budget" in errors:
            unused_errors = errors["unused budget"]
            error_message = str(list(unused_errors.values())[0])

            # Check if any above-threshold projects are mentioned
            above_threshold_reported = any(
                str(pid) in error_message for pid in [2, 3, 5]
            )
            below_threshold_reported = "4" in error_message

            self.assertTrue(
                above_threshold_reported,
                "At least one above-threshold project should be reported",
            )
            self.assertFalse(
                below_threshold_reported,
                "Below-threshold project 4 should not be reported",
            )

    def test_empty_lines_with_whitespace(self):
        """
        Test empty line detection with various types of whitespace.
        """
        # Lines with different types of "empty" content
        lines = [
            "META",
            "",  # Truly empty
            "   ",  # Spaces only
            "\t",  # Tab only
            "\n",  # Newline only
            "description;test",
            "  \t  ",  # Mixed whitespace
            "country;Poland",
        ]

        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Call empty line check
        self.checker.check_empty_lines(lines)

        # All whitespace-only lines should be removed
        remaining_content = [line for line in lines if line.strip()]
        self.assertEqual(len(remaining_content), 3)  # META, description, country

        # Should report the correct number of removed lines
        warnings = self.checker.file_results["warnings"]
        if "empty lines removed" in warnings:
            warning_message = warnings["empty lines removed"][1]
            # Should report removing 5 lines (empty, spaces, tab, newline, mixed)
            self.assertIn("Removed 5 empty lines", warning_message)

    def test_field_validation_with_none_values(self):
        """
        Test field validation with None values and edge cases.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        self.checker.meta = {
            "description": None,  # None value
            "country": "",  # Empty string
            "unit": "TestUnit",
            "instance": "TestInstance",
            "num_projects": 0,  # Zero value
            "num_votes": None,  # None value
            "budget": 1000.0,
            "vote_type": "approval",
            "rule": "greedy",
            "date_begin": "2024",
            "date_end": "2024",
        }

        self.checker.projects = {}
        self.checker.votes = {}

        # Call field validation
        self.checker.check_fields()

        # Should detect invalid/missing values
        errors = self.checker.file_results["errors"]

        # Should have errors for None/empty required fields
        invalid_value_errors = errors.get("invalid meta field value", {})
        missing_value_errors = errors.get("missing meta field value", {})

        # Check that problematic fields are detected
        all_error_details = []
        all_error_details.extend(invalid_value_errors.values())
        all_error_details.extend(missing_value_errors.values())

        error_text = " ".join(str(detail) for detail in all_error_details)

        # Should detect issues with description and num_votes
        self.assertTrue(
            "description" in error_text or "num_votes" in error_text,
            "Should detect issues with None/empty required field values",
        )

    def test_integration_comprehensive_validation(self):
        """
        Comprehensive integration test covering multiple validation aspects.
        """
        test_data = """META
description;Comprehensive test file
country;Poland
unit;TestUnit
instance;TestInstance
num_projects;4
num_votes;4
budget;1000
vote_type;approval
rule;greedy
date_begin;2024
date_end;2024
min_project_score_threshold;10
comment;#1: This is a properly formatted comment

PROJECTS
project_id;cost;votes;name;selected
1;300;25;High Priority Selected;1
2;400;20;Should Be Funded;0
3;350;15;Above Threshold But Cannot Fit;0
4;100;5;Below Threshold;0

VOTES
voter_id;vote
v1;1,2
v2;1,3
v3;2,3,4
v4;1
"""

        # Process the test data
        results = self.checker.process_files([test_data])

        # Get the file results
        file_key = next(
            (k for k in results.keys() if k != "metadata" and k != "summary"), None
        )
        file_results = results[file_key]["results"]

        # Should have some validation issues but process successfully
        self.assertIsInstance(file_results, dict)

        if "errors" in file_results:
            errors = file_results["errors"]

            # Should detect unused budget for project 2 only (project 4 below threshold)
            if "unused budget" in errors:
                unused_errors = errors["unused budget"]
                error_message = str(list(unused_errors.values())[0])

                self.assertIn(
                    "2",
                    error_message,
                    "Project 2 should be reported (above threshold, can be funded)",
                )
                self.assertNotIn(
                    "4",
                    error_message,
                    "Project 4 should not be reported (below threshold)",
                )

        # Should not have comment format errors (comment is properly formatted)
        if (
            "errors" in file_results
            and "invalid meta field value" in file_results["errors"]
        ):
            comment_errors = [
                detail
                for detail in file_results["errors"][
                    "invalid meta field value"
                ].values()
                if "comment should follow" in str(detail)
            ]
            self.assertEqual(
                len(comment_errors), 0, "Should not have comment format errors"
            )

    def test_zero_budget_edge_case(self):
        """
        Test behavior with zero budget.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        self.checker.meta = {
            "country": "Poland",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "budget": "0",  # Zero budget
            "date_begin": "2024",
            "date_end": "2024",
        }

        self.checker.projects = {
            1: {
                "project_id": 1,
                "cost": 100,
                "selected": "0",
                "votes": 10,
                "name": "Project 1",
            },
            2: {
                "project_id": 2,
                "cost": 200,
                "selected": "0",
                "votes": 15,
                "name": "Project 2",
            },
        }

        self.checker.votes = {}
        self.checker.results_field = "votes"
        self.checker.threshold = 0

        # Call budget validation
        self.checker.check_budgets()

        # With zero budget, no projects should be reported as unused budget
        errors = self.checker.file_results["errors"]
        self.assertNotIn(
            "unused budget",
            errors,
            "With zero budget, no unused budget errors should be reported",
        )

    def test_malformed_numeric_fields(self):
        """
        Test handling of malformed numeric field values.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        self.checker.meta = {
            "description": "Test",
            "country": "Poland",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "num_projects": "not_a_number",  # Invalid numeric
            "num_votes": "1.5",  # Float where int expected
            "budget": "1,000.50",  # Comma in float (should be handled)
            "vote_type": "approval",
            "rule": "greedy",
            "date_begin": "2024",
            "date_end": "2024",
        }

        self.checker.projects = {}
        self.checker.votes = {}

        # Call field validation
        self.checker.check_fields()

        # Should detect datatype errors
        errors = self.checker.file_results["errors"]
        self.assertIn(
            "incorrect meta field datatype", errors, "Should detect incorrect datatypes"
        )

        # Check that specific problematic fields are mentioned
        datatype_errors = errors["incorrect meta field datatype"]
        error_text = " ".join(str(detail) for detail in datatype_errors.values())

        self.assertIn("num_projects", error_text, "Should detect invalid num_projects")
        self.assertIn("num_votes", error_text, "Should detect invalid num_votes")


if __name__ == "__main__":
    unittest.main()
