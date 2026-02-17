#!/usr/bin/env python3
"""
Unit tests for new functionality added to the checker.
Tests cover recent improvements including:
- Comment field validation rules
- Unused budget greedy simulation logic
- Empty line handling with warnings
- Enhanced field validation
"""

import os
import sys
import unittest
from copy import deepcopy

# Add the project root directory to Python path to use local modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from pabulib.checker import Checker


class TestNewFunctionality(unittest.TestCase):
    """Test cases for new functionality added to the checker."""

    def setUp(self):
        """Set up the Checker instance for unit tests."""
        self.checker = Checker()

    def test_comment_field_validation_valid_format(self):
        """
        Test that comment field with correct format ('#1: comment text') passes validation.
        """
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
            "comment": "#1: This is a valid comment format",
        }

        self.checker.projects = {}
        self.checker.votes = {}

        # Call the method that validates fields
        self.checker.check_fields()

        # Should not have any comment validation errors
        errors = self.checker.file_results["errors"]
        self.assertNotIn("invalid meta field value", errors)

    def test_comment_field_validation_invalid_format(self):
        """
        Test that comment field with incorrect format fails validation.
        """
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
            "comment": "This is an invalid comment format",  # Missing '#1: ' prefix
        }

        self.checker.projects = {}
        self.checker.votes = {}

        # Call the method that validates fields
        self.checker.check_fields()

        # Should have comment validation error
        errors = self.checker.file_results["errors"]
        self.assertIn("invalid meta field value", errors)

        # Check that the error mentions comment format
        comment_error_found = False
        for error_detail in errors["invalid meta field value"].values():
            if "comment should follow the '#1: ' format" in str(error_detail):
                comment_error_found = True
                break

        self.assertTrue(
            comment_error_found, "Comment format validation error not found"
        )

    def test_unused_budget_greedy_simulation_simple(self):
        """
        Test unused budget detection with greedy simulation.
        Should only report projects that can actually be funded with remaining budget.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Set up scenario: budget 1000, project 1 selected (cost 600),
        # project 2 not selected (cost 300, can be funded),
        # project 3 not selected (cost 500, cannot be funded)
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
                "cost": 600,
                "selected": "1",
                "votes": 10,
                "name": "Selected Project",
            },
            2: {
                "project_id": 2,
                "cost": 300,
                "selected": "0",
                "votes": 8,
                "name": "Can Be Funded",
            },  # Can be funded
            3: {
                "project_id": 3,
                "cost": 500,
                "selected": "0",
                "votes": 6,
                "name": "Cannot Be Funded",
            },  # Cannot be funded
        }

        self.checker.votes = {}
        self.checker.results_field = "votes"
        self.checker.threshold = 0

        # Call budget validation
        self.checker.check_budgets()

        # Should only report project 2 as unused budget (can be funded)
        warnings = self.checker.file_results["warnings"]
        self.assertIn("unused budget", warnings)

        # Should only mention project 2, not project 3
        unused_errors = warnings["unused budget"]
        error_message = str(list(unused_errors.values())[0])

        self.assertIn(
            "2", error_message, "Project 2 should be reported as unused budget"
        )
        self.assertNotIn(
            "3", error_message, "Project 3 should NOT be reported (cannot be funded)"
        )

    def test_unused_budget_greedy_simulation_with_threshold(self):
        """
        Test unused budget detection respects minimum score threshold.
        Only projects above threshold should be considered for funding.
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

        self.checker.projects = {
            1: {
                "project_id": 1,
                "cost": 400,
                "selected": "1",
                "votes": 15,
                "name": "Selected Project",
            },
            2: {
                "project_id": 2,
                "cost": 300,
                "selected": "0",
                "votes": 10,
                "name": "Above Threshold",
            },  # Above threshold, can be funded
            3: {
                "project_id": 3,
                "cost": 200,
                "selected": "0",
                "votes": 5,
                "name": "Below Threshold",
            },  # Below threshold, should be ignored
        }

        self.checker.votes = {}
        self.checker.results_field = "votes"
        self.checker.threshold = 8  # Minimum 8 votes required

        # Call budget validation
        self.checker.check_budgets()

        # Should only report project 2 (above threshold and can be funded)
        warnings = self.checker.file_results["warnings"]
        if "unused budget" in warnings:
            unused_errors = warnings["unused budget"]
            error_message = str(list(unused_errors.values())[0])

            self.assertIn(
                "2", error_message, "Project 2 should be reported (above threshold)"
            )
            self.assertNotIn(
                "3", error_message, "Project 3 should NOT be reported (below threshold)"
            )

    def test_unused_budget_greedy_simulation_priority_order(self):
        """
        Test that unused budget detection follows greedy priority (highest votes first).
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

        # Selected project costs 300, remaining budget 700
        # Two unselected projects: high votes (cost 400) and low votes (cost 600)
        # Only high votes project should be reported (greedy order)
        self.checker.projects = {
            1: {
                "project_id": 1,
                "cost": 300,
                "selected": "1",
                "votes": 20,
                "name": "Selected Project",
            },
            2: {
                "project_id": 2,
                "cost": 400,
                "selected": "0",
                "votes": 15,
                "name": "High Priority",
            },  # Higher priority, can be funded
            3: {
                "project_id": 3,
                "cost": 600,
                "selected": "0",
                "votes": 8,
                "name": "Low Priority",
            },  # Lower priority, would exceed budget after project 2
        }

        self.checker.votes = {}
        self.checker.results_field = "votes"
        self.checker.threshold = 0

        # Call budget validation
        self.checker.check_budgets()

        # Should only report project 2 (higher priority and fits)
        warnings = self.checker.file_results["warnings"]
        self.assertIn("unused budget", warnings)

        unused_errors = warnings["unused budget"]
        error_message = str(list(unused_errors.values())[0])

        self.assertIn(
            "2", error_message, "Project 2 should be reported (higher priority)"
        )
        self.assertNotIn(
            "3",
            error_message,
            "Project 3 should NOT be reported (would exceed budget after project 2)",
        )

    def test_empty_lines_warning_system(self):
        """
        Test that empty lines are reported as warnings, not errors,
        and that the count is accurate.
        """
        # Test with lines containing empty strings
        lines = ["META", "", "description;test", "country;Poland", "", "PROJECTS", ""]

        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Call empty line check
        self.checker.check_empty_lines(lines)

        # Should be reported as warning, not error
        warnings = self.checker.file_results["warnings"]
        errors = self.checker.file_results["errors"]

        self.assertIn("empty lines removed", warnings)
        self.assertNotIn("empty lines", errors)

        # Check warning message contains correct count
        warning_message = warnings["empty lines removed"][1]
        self.assertIn("Removed 2 empty lines", warning_message)

        # Check that empty lines were actually removed from the list
        self.assertNotIn("", lines)
        self.assertEqual(
            len(lines), 4
        )  # Original 7 - 2 empty (excluding trailing) - 1 trailing = 4

    def test_empty_lines_no_warning_when_none(self):
        """
        Test that no warning is generated when there are no empty lines.
        """
        lines = ["META", "description;test", "country;Poland", "PROJECTS"]

        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Call empty line check
        self.checker.check_empty_lines(lines)

        # Should not have any warnings about empty lines
        warnings = self.checker.file_results["warnings"]
        errors = self.checker.file_results["errors"]

        self.assertNotIn("empty lines removed", warnings)
        self.assertNotIn("empty lines", errors)

    def test_skipped_key_field_validation(self):
        """
        Test that 'key' field is properly skipped during validation
        (it's auto-generated and should not cause unknown field errors).
        """
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
            "key": "auto_generated_key_should_be_skipped",  # Should be ignored
        }

        self.checker.projects = {}
        self.checker.votes = {}

        # Call field validation
        self.checker.check_fields()

        # Should not report 'key' as unknown field
        errors = self.checker.file_results["errors"]
        if "not known meta fields" in errors:
            unknown_field_errors = errors["not known meta fields"]
            key_field_reported = any(
                "key" in str(detail) for detail in unknown_field_errors.values()
            )
            self.assertFalse(
                key_field_reported,
                "'key' field should be skipped, not reported as unknown",
            )

    def test_voting_method_validation_invalid(self):
        """
        Test that invalid voting methods are properly detected and reported.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        self.checker.meta = {
            "description": "Test",
            "country": "Poland",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "num_projects": 1,
            "num_votes": 1,
            "budget": 1000.0,
            "vote_type": "invalid_voting_method",  # Invalid vote type
            "rule": "greedy",
            "date_begin": "2024",
            "date_end": "2024",
        }

        self.checker.projects = {}
        self.checker.votes = {}

        # Call field validation
        self.checker.check_fields()

        # Should report invalid vote_type
        errors = self.checker.file_results["errors"]
        self.assertIn("invalid meta field value", errors)

        # Check that error mentions vote_type
        vote_type_error_found = False
        for error_detail in errors["invalid meta field value"].values():
            if "vote_type" in str(error_detail):
                vote_type_error_found = True
                break

        self.assertTrue(vote_type_error_found, "Invalid vote_type should be reported")

    def test_voting_method_validation_valid(self):
        """
        Test that valid voting methods pass validation.
        """
        valid_vote_types = ["ordinal", "approval", "cumulative", "choose-1"]

        for vote_type in valid_vote_types:
            with self.subTest(vote_type=vote_type):
                self.checker.file_results = deepcopy(self.checker.error_levels)

                self.checker.meta = {
                    "description": "Test",
                    "country": "Poland",
                    "unit": "TestUnit",
                    "instance": "TestInstance",
                    "num_projects": 1,
                    "num_votes": 1,
                    "budget": 1000.0,
                    "vote_type": vote_type,
                    "rule": "greedy",
                    "date_begin": "2024",
                    "date_end": "2024",
                }

                self.checker.projects = {}
                self.checker.votes = {}

                # Call field validation
                self.checker.check_fields()

                # Should not have vote_type validation errors
                errors = self.checker.file_results["errors"]
                if "invalid meta field value" in errors:
                    vote_type_error_found = any(
                        "vote_type" in str(detail)
                        for detail in errors["invalid meta field value"].values()
                    )
                    self.assertFalse(
                        vote_type_error_found,
                        f"Valid vote_type '{vote_type}' should not be reported as invalid",
                    )

    def test_num_votes_field_missing_error_message(self):
        """
        Test that missing num_votes field generates clear error message
        with actual vote count from file.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Simulate missing num_votes (empty or None)
        self.checker.meta = {"num_votes": ""}
        self.checker.votes = {
            1: {"voter_id": 1, "vote": "1"},
            2: {"voter_id": 2, "vote": "1,2"},
            3: {"voter_id": 3, "vote": "2"},
        }

        # Call the method that checks vote numbers
        self.checker.check_number_of_votes()

        # Should report missing num_votes with actual count
        errors = self.checker.file_results["errors"]
        self.assertIn("missing num_votes field", errors)

        error_message = errors["missing num_votes field"][1]
        self.assertIn("but found 3 votes in file", error_message)
        self.assertIn("missing or empty", error_message)

    def test_integration_unused_budget_improvement(self):
        """
        Integration test showing improved unused budget detection.
        Only reports projects that can actually be funded in greedy order.
        """
        test_data = """META
description;Test for unused budget improvement
country;Poland
unit;TestUnit
instance;TestInstance
num_projects;4
num_votes;3
budget;1000
vote_type;approval
rule;greedy
date_begin;2024
date_end;2024

PROJECTS
project_id;cost;votes;name;selected
1;400;20;Selected Project;1
2;300;15;Can Be Funded;0
3;500;10;Too Expensive After Project 2;0
4;100;5;Can Also Be Funded;0

VOTES
voter_id;vote
v1;1,2
v2;1,3
v3;2,4
"""

        # Process the test data
        results = self.checker.process_files([test_data])

        # File may contain other validation errors; unused budget should be an error for greedy rule.
        self.assertEqual(results["metadata"]["processed"], 1)

        # Get the file results
        file_key = next(
            (k for k in results.keys() if k != "metadata" and k != "summary"), None
        )
        file_results = results[file_key]["results"]
        errors = file_results["errors"]

        # Should have unused budget error (for greedy rule)
        self.assertIn("unused budget", errors)

        # Check which projects are reported
        unused_errors = errors["unused budget"]
        error_message = str(list(unused_errors.values())[0])

        # Should report projects 2 and 4 (can be funded in greedy order)
        # Should NOT report project 3 (would exceed budget after funding projects 2 and 4)
        self.assertIn(
            "2", error_message, "Project 2 should be reported (can be funded)"
        )
        self.assertIn(
            "4",
            error_message,
            "Project 4 should be reported (can be funded after project 2)",
        )
        self.assertNotIn(
            "3", error_message, "Project 3 should NOT be reported (would exceed budget)"
        )


if __name__ == "__main__":
    unittest.main()
