import unittest

from pabulib.checker import Checker


class TestCheckerUnit(unittest.TestCase):
    def setUp(self):
        """
        Set up the Checker instance for unit tests.
        """
        self.checker = Checker()

    def check_if_error_added_correctly(self, type, details):
        error = self.checker.file_results.get(type)
        if error is None:
            raise AssertionError(f"Error for {type} not caught.")

        # Check if the error content is correct
        expected_error = {1: details}
        self.assertEqual(
            error, expected_error, f"Expected error {expected_error}, but got {error}."
        )

    def test_check_empty_lines(self):
        """
        Test that `check_empty_lines` correctly identifies and removes empty lines.
        """
        self.checker.file_results = {}
        lines = ["line1", "", "line2", "line3", ""]
        self.checker.check_empty_lines(lines)
        self.check_if_error_added_correctly(
            "empty lines", "contains empty lines at: [2]"
        )

    def test_check_no_empty_lines(self):
        # Test case with no empty lines
        lines_without_empty = ["line1", "line2", "line3", ""]
        self.checker.file_results = {}
        self.checker.check_empty_lines(lines_without_empty)
        error = self.checker.file_results.get("empty lines")
        self.assertIsNone(
            error, "Error incorrectly raised for lines without empty entries."
        )

    def test_validate_date_range_valid_year(self):
        """
        Test `validate_date_range` with a valid date range.
        """
        self.checker.file_results = {}
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
        self.checker.file_results = {}
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
        self.checker.file_results = {}
        self.checker.add_error("test_error", "This is a test error.")
        # Check if the error is recorded in file_results
        self.assertIn("test_error", self.checker.file_results)
        self.assertEqual(
            self.checker.file_results["test_error"][1], "This is a test error."
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
        self.checker.file_results = {}

        # Add the first error
        self.checker.add_error("test_error", "This is a test error.")
        # Add a second error of the same type
        self.checker.add_error("test_error", "This is another test error.")

        # Check if the errors are recorded in file_results
        self.assertIn("test_error", self.checker.file_results)
        self.assertEqual(
            self.checker.file_results["test_error"],
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
        self.checker.file_results = {}

        # Add the first error
        self.checker.add_error("test_error", "This is a test error.")
        # Add a second error of the same type
        self.checker.add_error("different_error", "This is another test error.")

        # Check if the errors are recorded in file_results
        self.assertIn("test_error", self.checker.file_results)
        self.assertEqual(
            self.checker.file_results["test_error"],
            {1: "This is a test error."},
            "File results do not match expected multiple errors.",
        )
        self.assertEqual(
            self.checker.file_results["different_error"],
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
        """
        self.checker.file_results = {}

        # Fake data
        self.checker.meta = {
            "country": "TestCountry",  # Missing 'unit' and 'instance'
            "budget": "1000",
            "date_begin": "2024",
            "date_end": "2024",
        }

        # Mock fields order for validation
        self.checker.fields_order = {
            "country": {"obligatory": True},
            "unit": {"obligatory": True},
            "instance": {"obligatory": True},
            "budget": {"obligatory": False},
        }
        self.checker.projects = {}
        self.checker.votes = {}

        # Call the method under test
        self.checker.check_fields()

        # Check for errors in file_results
        error = self.checker.file_results.get("missing meta obligatory field")
        self.assertIsNotNone(error, "Error for missing required fields not logged.")
        self.assertIn("unit", error[1], "Missing 'unit' not detected.")
        self.assertIn("instance", error[1], "Missing 'instance' not detected.")

    def test_validate_fields_wrong_order(self):
        """
        Test if field order validation detects incorrectly ordered fields.
        """
        self.checker.file_results = {}

        # Fake data with incorrect field order
        self.checker.meta = {
            "instance": "TestInstance",
            "unit": "TestUnit",
            "country": "TestCountry",
            "date_begin": "2024",
            "date_end": "2024",
        }

        # Mock field order
        self.checker.fields_order = {
            "country": {"obligatory": True},
            "unit": {"obligatory": True},
            "instance": {"obligatory": True},
        }
        self.checker.projects = {}
        self.checker.votes = {}

        # Call method to validate fields
        self.checker.check_fields()

        # Check for field order error
        error = self.checker.file_results.get("wrong meta fields order")
        self.assertIsNotNone(error, "Error for incorrect field order not logged.")

    def test_validate_fields_unknown_field(self):
        """
        Test if unknown fields are correctly detected and logged.
        """
        self.checker.file_results = {}

        # Fake data with unknown field
        self.checker.meta = {
            "country": "TestCountry",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "unknown_field": "unexpected",
            "date_begin": "2024",
            "date_end": "2024",
        }

        # Mock field order
        self.checker.fields_order = {
            "country": {"obligatory": True},
            "unit": {"obligatory": True},
            "instance": {"obligatory": True},
        }

        self.checker.projects = {}
        self.checker.votes = {}

        # Call method to validate fields
        self.checker.check_fields()

        # Check for unknown field error
        error = self.checker.file_results.get("not known meta fields")
        self.assertIsNotNone(error, "Error for unknown fields not logged.")

    def test_validate_fields_invalid_value(self):
        """
        Test if invalid field values are correctly validated and errors are logged.
        """
        self.checker.file_results = {}

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
        error = self.checker.file_results.get("incorrect meta field datatype")
        self.assertIsNotNone(error, "Error for invalid field values not logged.")


if __name__ == "__main__":
    unittest.main()
