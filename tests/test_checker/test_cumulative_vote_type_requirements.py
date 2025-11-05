import os
import sys
import unittest
from copy import deepcopy

# Add the project root directory to Python path to use local modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from pabulib.checker import Checker


class TestCumulativeVoteTypeRequirements(unittest.TestCase):
    def setUp(self):
        self.checker = Checker()
        self.checker.file_results = deepcopy(self.checker.error_levels)

    def test_cumulative_requires_max_sum_points_missing(self):
        """
        If vote_type is 'cumulative', meta must include 'max_sum_points'.
        """
        self.checker.meta = {
            "description": "Test",
            "country": "Poland",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "num_projects": 1,
            "num_votes": 1,
            "budget": 1000.0,
            "vote_type": "cumulative",
            "rule": "greedy",
            "date_begin": "2024",
            "date_end": "2024",
            # Intentionally omit max_sum_points
        }
        self.checker.projects = {}
        self.checker.votes = {}

        self.checker.check_fields()

        errors = self.checker.file_results["errors"]
        self.assertIn("missing meta field value", errors)
        self.assertIn(
            "For vote_type 'cumulative', 'max_sum_points' is required.",
            errors["missing meta field value"][1],
        )

    def test_cumulative_with_max_sum_points_ok(self):
        """
        If vote_type is 'cumulative' and max_sum_points is provided, no missing error should be raised.
        """
        self.checker.meta = {
            "description": "Test",
            "country": "Poland",
            "unit": "TestUnit",
            "instance": "TestInstance",
            "num_projects": 1,
            "num_votes": 1,
            "budget": 1000.0,
            "vote_type": "cumulative",
            "rule": "greedy",
            "date_begin": "2024",
            "date_end": "2024",
            "max_sum_points": 5,
        }
        self.checker.projects = {}
        self.checker.votes = {}

        self.checker.check_fields()

        errors = self.checker.file_results["errors"]
        # Ensure the specific missing error isn't present
        if "missing meta field value" in errors:
            self.assertFalse(
                any(
                    "max_sum_points" in str(msg)
                    for msg in errors["missing meta field value"].values()
                ),
                "max_sum_points should not be flagged when provided",
            )


if __name__ == "__main__":
    unittest.main()
