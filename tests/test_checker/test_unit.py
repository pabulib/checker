import os
import sys
import unittest
from copy import deepcopy
from io import StringIO

# Add the project root directory to Python path to use local modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from pabulib.checker import Checker


class TestCheckerUnit(unittest.TestCase):
    def setUp(self):
        """
        Set up the Checker instance for unit tests.
        """
        self.checker = Checker()

    def check_if_error_added_correctly(self, type, details):
        error = self.checker.file_results["errors"].get(type)
        if error is None:
            raise AssertionError(f"Error for {type} not caught.")

        # Check if the error content is correct
        expected_error = {1: details}

        self.assertEqual(
            error, expected_error, f"Expected error {expected_error}, but got {error}."
        )

    def test_check_empty_lines(self):
        """
        Test that `check_empty_lines` correctly removes empty lines.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)
        lines = ["line1", "", "line2", "line3", ""]
        original_length = len(lines)

        # Initialize file_results before calling the method
        self.checker.file_results = deepcopy(self.checker.error_levels)

        self.checker.check_empty_lines(lines)

        # Check that empty lines were removed
        self.assertEqual(len(lines), 3)  # Should have 3 lines left
        self.assertNotIn("", lines)  # No empty strings should remain

        # Check that warning was added (new behavior)
        warnings = self.checker.file_results["warnings"].get("empty lines removed")
        self.assertIsNotNone(
            warnings, "Empty line removal should be reported as warning"
        )
        self.assertIn("Removed 2 empty lines from the file.", warnings[1])

    def test_check_no_empty_lines(self):
        # Test case with no empty lines
        lines_without_empty = ["line1", "line2", "line3", ""]
        self.checker.file_results = deepcopy(self.checker.error_levels)
        self.checker.check_empty_lines(lines_without_empty)
        error = self.checker.file_results["errors"].get("empty lines")
        self.assertIsNone(
            error, "Error incorrectly raised for lines without empty entries."
        )

    def test_validate_date_range_valid_year(self):
        """
        Test `validate_date_range` with a valid date range.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)
        meta = {
            "date_begin": "2024",
            "date_end": "2023",
        }
        self.checker.validate_date_range(meta)
        details = "date end (2023-01-01) earlier than start (2024-01-01)!"
        self.check_if_error_added_correctly("date range missmatch", details)

    def test_validate_date_range_valid_full_date(self):
        """
        Test `validate_date_range` with a valid date range.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)
        meta = {
            "date_begin": "02.01.2024",
            "date_end": "01.01.2024",
        }
        self.checker.validate_date_range(meta)
        details = "date end (2024-01-01) earlier than start (2024-01-02)!"
        self.check_if_error_added_correctly("date range missmatch", details)

    def test_add_error(self):
        """
        Test that `add_error` correctly records errors.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)
        self.checker.add_error("test_error", "This is a test error.")
        # Check if the error is recorded in file_results
        self.assertIn("test_error", self.checker.file_results["errors"])
        self.assertEqual(
            self.checker.file_results["errors"]["test_error"][1],
            "This is a test error.",
        )

        # Check if the error is recorded in the summary
        self.assertIn(
            "test_error",
            self.checker.results["summary"],
            "Error not recorded in summary.",
        )
        self.assertEqual(
            self.checker.results["summary"]["test_error"],
            1,
            "Summary count for test_error is incorrect.",
        )

    def test_add_error_two_same_errors(self):
        """
        Test that `add_error` correctly records errors and updates the summary.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Add the first error
        self.checker.add_error("test_error", "This is a test error.")
        # Add a second error of the same type
        self.checker.add_error("test_error", "This is another test error.")

        # Check if the errors are recorded in file_results
        self.assertIn("test_error", self.checker.file_results["errors"])
        self.assertEqual(
            self.checker.file_results["errors"]["test_error"],
            {1: "This is a test error.", 2: "This is another test error."},
            "File results do not match expected multiple errors.",
        )

        # Check if the error count is updated in the summary
        self.assertIn(
            "test_error",
            self.checker.results["summary"],
            "Error not recorded in summary.",
        )
        self.assertEqual(
            self.checker.results["summary"]["test_error"],
            2,
            "Summary count for test_error is incorrect after multiple additions.",
        )

    def test_add_error_two_different_errors(self):
        """
        Test that `add_error` correctly records errors and updates the summary.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Add the first error
        self.checker.add_error("test_error", "This is a test error.")
        # Add a second error of the same type
        self.checker.add_error("different_error", "This is another test error.")

        # Check if the errors are recorded in file_results
        self.assertIn("test_error", self.checker.file_results["errors"])
        self.assertEqual(
            self.checker.file_results["errors"]["test_error"],
            {1: "This is a test error."},
            "File results do not match expected multiple errors.",
        )
        self.assertEqual(
            self.checker.file_results["errors"]["different_error"],
            {1: "This is another test error."},
            "File results do not match expected multiple errors.",
        )

        # Check if the error count is updated in the summary
        self.assertIn(
            "test_error",
            self.checker.results["summary"],
            "Error not recorded in summary.",
        )
        self.assertEqual(
            self.checker.results["summary"]["test_error"],
            1,
            "Summary count for test_error is incorrect after multiple additions.",
        )
        self.assertIn(
            "different_error",
            self.checker.results["summary"],
            "Error not recorded in summary.",
        )
        self.assertEqual(
            self.checker.results["summary"]["different_error"],
            1,
            "Summary count for test_error is incorrect after multiple additions.",
        )

    def test_validate_fields_missing_required(self):
        """
        Test if required fields are correctly validated and errors are logged for missing fields.
        With the new robust checker, missing fields are assigned default values and reported as
        'missing meta field value' errors instead of 'missing meta obligatory field'.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Simulate data that would have missing required fields after parsing
        self.checker.meta = {
            "country": "TestCountry",
            "budget": "1000",
            "date_begin": "2024",
            "date_end": "2024",
            # Simulate missing required fields with default values + markers
            "unit": "",
            "__unit_was_missing__": True,
            "instance": "",
            "__instance_was_missing__": True,
        }

        self.checker.projects = {}
        self.checker.votes = {}

        # Call the method under test
        self.checker.check_fields()

        # Check for the new error type that reports missing fields
        error = self.checker.file_results["errors"].get("missing meta field value")
        self.assertIsNotNone(error, "Error for missing required fields not logged.")
        # Check that both missing fields are reported
        found_unit = any("unit" in str(detail) for detail in error.values())
        found_instance = any("instance" in str(detail) for detail in error.values())
        self.assertTrue(found_unit, "Missing 'unit' not detected.")
        self.assertTrue(found_instance, "Missing 'instance' not detected.")

    def test_validate_fields_wrong_order(self):
        """
        Test if field order validation detects incorrectly ordered fields.
        With the new robust checker, missing fields get default values, so we need to simulate
        them with the marker fields.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Fake data with incorrect field order and simulated missing fields
        self.checker.meta = {
            "instance": "TestInstance",
            "unit": "TestUnit",
            "country": "TestCountry",
            "date_begin": "2024",
            "date_end": "2024",
            # Simulate missing required fields that would be added by the parser
            "description": "",
            "__description_was_missing__": True,
            "num_projects": 0,
            "__num_projects_was_missing__": True,
            "num_votes": 0,
            "__num_votes_was_missing__": True,
            "budget": 0.0,
            "__budget_was_missing__": True,
            "vote_type": "",
            "__vote_type_was_missing__": True,
            "rule": "",
            "__rule_was_missing__": True,
        }

        self.checker.projects = {}
        self.checker.votes = {}

        # Call method to validate fields
        self.checker.check_fields()

        # Check for field order error (now includes all fields, not just the present ones)
        warnings = self.checker.file_results["warnings"].get("wrong meta fields order")
        self.assertEqual(
            warnings[1],
            "correct order should be: ['description', 'country', 'unit', 'instance', 'num_projects', 'num_votes', 'budget', 'vote_type', 'rule', 'date_begin', 'date_end']",
        )

        # Check for missing field value errors (the new error type)
        errors = self.checker.file_results["errors"].get("missing meta field value")
        self.assertIsNotNone(errors, "Missing field value errors not logged.")

        # Verify that some of the expected missing fields are reported
        missing_fields_found = []
        for error_detail in errors.values():
            if "description" in str(error_detail):
                missing_fields_found.append("description")
            if "num_projects" in str(error_detail):
                missing_fields_found.append("num_projects")
            if "num_votes" in str(error_detail):
                missing_fields_found.append("num_votes")
            if "budget" in str(error_detail):
                missing_fields_found.append("budget")
            if "vote_type" in str(error_detail):
                missing_fields_found.append("vote_type")
            if "rule" in str(error_detail):
                missing_fields_found.append("rule")

        # We should find all the missing required fields
        expected_missing = [
            "description",
            "num_projects",
            "num_votes",
            "budget",
            "vote_type",
            "rule",
        ]
        for field in expected_missing:
            self.assertIn(
                field, missing_fields_found, f"Missing field '{field}' not detected."
            )

    def test_validate_fields_unknown_field(self):
        """
        Test if unknown fields are correctly detected and logged.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Fake data with unknown field
        self.checker.meta = {
            "country": "TestCountry",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "unknown_field": "unexpected",
            "date_begin": "2024",
            "date_end": "2024",
        }

        self.checker.projects = {}
        self.checker.votes = {}

        # Call method to validate fields
        self.checker.check_fields()

        # Check for unknown field error
        error = self.checker.file_results["errors"].get("not known meta fields")
        self.assertIsNotNone(error, "Error for unknown fields not logged.")

    def test_validate_fields_invalid_value(self):
        """
        Test if invalid field values are correctly validated and errors are logged.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Fake data with invalid value for 'budget'
        self.checker.meta = {
            "country": "TestCountry",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "budget": "not_a_number",
            "date_begin": "2024",
            "date_end": "2024",
        }

        # Mock field order
        self.checker.fields_order = {
            "country": {"obligatory": True, "datatype": str},
            "unit": {"obligatory": True, "datatype": str},
            "instance": {"obligatory": True, "datatype": str},
            "budget": {"obligatory": False, "datatype": int},
        }

        self.checker.projects = {}
        self.checker.votes = {}

        # Call method to validate fields
        self.checker.check_fields()

        # Check for invalid value error
        error = self.checker.file_results["errors"].get("incorrect meta field datatype")
        self.assertIsNotNone(error, "Error for invalid field values not logged.")

    def test_validate_budget_lower_no_ff_flag(self):
        """
        Test if fully funded are correctly detected and logged.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Fake data with unknown field
        self.checker.meta = {
            "country": "TestCountry",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "date_begin": "2024",
            "date_end": "2024",
            "budget": "500",
        }

        self.checker.projects = {
            1: {"project_id": 1, "cost": 200},
            2: {"project_id": 2, "cost": 200},
        }
        self.checker.votes = {}

        # Call method to validate fields
        self.checker.check_budgets()

        error = self.checker.file_results["errors"]
        self.assertIsNotNone(
            error.get("all projects funded"),
            "Error for all projects funded not logged.",
        )
        self.assertEqual(
            error.get("all projects funded")[1],
            "budget: 500, cost of all projects: 400",
        )

    def test_validate_budget_lower_no_ff_flag(self):
        """
        Test if fully funded (budget ) are correctly detected and logged.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Fake data with unknown field
        self.checker.meta = {
            "country": "TestCountry",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "date_begin": "2024",
            "date_end": "2024",
            "budget": "500",
        }

        self.checker.projects = {
            1: {"project_id": 1, "cost": 300},
            2: {"project_id": 2, "cost": 200},
        }
        self.checker.votes = {}

        # Call method to validate fields
        self.checker.check_budgets()

        error = self.checker.file_results["errors"]
        self.assertIsNotNone(
            error.get("all projects funded"),
            "Error for all projects funded not logged.",
        )
        self.assertEqual(
            error.get("all projects funded")[1],
            "budget: 500, cost of all projects: 500",
        )

    def test_validate_budget_lower_ff_flag(self):
        """
        Test if fully funded (budget ) are correctly detected and logged.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Fake data with unknown field
        self.checker.meta = {
            "country": "TestCountry",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "date_begin": "2024",
            "date_end": "2024",
            "budget": "500",
            "fully_funded": "1",
        }

        self.checker.projects = {
            1: {"project_id": 1, "cost": 300},
            2: {"project_id": 2, "cost": 200},
        }
        self.checker.votes = {}

        # Call method to validate fields
        self.checker.check_budgets()

        error = self.checker.file_results["errors"]
        self.assertIsNone(
            error.get("all projects funded"),
            "Error for all projects funded logged.",
        )

    def test_validate_budget_lower_no_ff_flag(self):
        """
        Test if fully funded are correctly detected and logged.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Fake data with unknown field
        self.checker.meta = {
            "country": "TestCountry",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "date_begin": "2024",
            "date_end": "2024",
            "budget": "500",
            "fully_funded": "1",
        }

        self.checker.projects = {
            1: {"project_id": 1, "cost": 200},
            2: {"project_id": 2, "cost": 200},
        }
        self.checker.votes = {}

        # Call method to validate fields
        self.checker.check_budgets()

        error = self.checker.file_results["errors"]
        self.assertIsNone(
            error.get("all projects funded"),
            "Error for all projects funded logged.",
        )

    def test_validate_wrong_ff_flag(self):
        """
        Test if fully funded are correctly detected and logged.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Fake data with unknown field
        self.checker.meta = {
            "country": "TestCountry",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "date_begin": "2024",
            "date_end": "2024",
            "budget": "500",
            "fully_funded": "1",
        }

        self.checker.projects = {
            1: {"project_id": 1, "cost": 200},
            2: {"project_id": 2, "cost": 400},
        }
        self.checker.votes = {}

        # Call method to validate fields
        self.checker.check_budgets()

        error = self.checker.file_results["errors"]
        self.assertIsNotNone(
            error.get("wrong fully_funded flag"),
            "Wrong fully funded flag not catched.",
        )
        self.assertEqual(
            error.get("wrong fully_funded flag")[1],
            "budget: 500, lower than cost of all projects: 600",
        )

    def test_validate_ff_flag_str(self):
        """
        Test if fully funded are correctly detected and logged.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Fake data with unknown field
        self.checker.meta = {
            "country": "TestCountry",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "date_begin": "2024",
            "date_end": "2024",
            "budget": "500",
            "fully_funded": "something else",
        }

        self.checker.projects = {}
        self.checker.votes = {}

        # Call method to validate fields
        self.checker.check_fields()

        error = self.checker.file_results["errors"]
        self.assertIsNotNone(
            error.get("incorrect meta field datatype"),
            "Invalid full_funded flag not catched.",
        )
        self.assertEqual(
            error.get("incorrect meta field datatype")[1],
            "meta field 'fully_funded' has incorrect datatype. Expected int, found str.",
        )

    def test_validate_ff_flag_zero(self):
        """
        Test if fully funded are correctly detected and logged.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Fake data with unknown field
        self.checker.meta = {
            "country": "Poland",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "date_begin": "2024",
            "date_end": "2024",
            "budget": "500",
            "fully_funded": 0,
        }

        self.checker.projects = {}
        self.checker.votes = {}

        # Call method to validate fields
        self.checker.check_fields()

        error = self.checker.file_results["errors"]
        self.assertIsNotNone(
            error.get("invalid meta field value"),
            "Invalid full_funded flag not catched.",
        )
        self.assertEqual(
            error.get("invalid meta field value")[1],
            "meta field 'fully_funded' cannot be None or empty.",
        )

    def test_validate_ff_flag_other_int(self):
        """
        Test if fully funded are correctly detected and logged.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Fake data with unknown field
        self.checker.meta = {
            "country": "Poland",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "date_begin": "2024",
            "date_end": "2024",
            "budget": "500",
            "fully_funded": 2,
        }

        self.checker.projects = {}
        self.checker.votes = {}

        # Call method to validate fields
        self.checker.check_fields()

        error = self.checker.file_results["errors"]
        self.assertIsNotNone(
            error.get("invalid meta field value"),
            "Invalid full_funded flag not catched.",
        )
        self.assertEqual(
            error.get("invalid meta field value")[1],
            "meta field 'fully_funded' failed validation with value: 2.",
        )

    def test_create_webpage_name_with_polish_chars(self):
        """
        Test that `create_webpage_name` handles Polish characters correctly.
        """
        self.checker.meta = {
            "country": "Polska",
            "unit": "Wydział Śródmieście",
            "instance": "Białołęka",
        }

        name = self.checker.create_webpage_name()
        expected = "Polska_Wydział Śródmieście_Białołęka"

        self.assertEqual(name, expected)
        print("Generated webpage name:", name)

    def test_no_max_length_used_warning(self):
        """
        Should raise a warning when no vote uses the full max_length.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        self.checker.meta = {
            "country": "Polska",
            "unit": "Warszawa",
            "instance": "2020",
            "max_length": "3",  # Must be string if stored that way
        }

        self.checker.votes = {
            1: {"voter_id": 1, "vote": "1"},
            2: {"voter_id": 2, "vote": "1,2"},
        }

        self.checker.check_vote_length()

        warning = self.checker.file_results["warnings"].get("no_max_length_used")
        self.assertIsNotNone(warning, "Expected warning not triggered.")
        self.assertIn("No voter used the full max vote length of `3`", warning[1])

    def test_max_length_used_no_warning(self):
        """
        Should NOT raise a warning when at least one vote uses the full max_length.
        """
        self.checker.file_results = deepcopy(self.checker.error_levels)

        self.checker.meta = {
            "country": "Polska",
            "unit": "Warszawa",
            "instance": "2020",
            "max_length": "3",
        }

        self.checker.votes = {
            1: {"voter_id": 1, "vote": "1"},
            2: {"voter_id": 2, "vote": "1,2"},
            3: {"voter_id": 3, "vote": "1,2,3"},  # matches max_length
        }

        self.checker.check_vote_length()

        warning = self.checker.file_results["warnings"].get("no_max_length_used")
        self.assertIsNone(
            warning, "Unexpected warning triggered when max length was used."
        )


if __name__ == "__main__":
    unittest.main()
