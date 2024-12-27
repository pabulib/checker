import unittest
from copy import deepcopy

from pabulib.checker import Checker


class TestCheckerIntegration(unittest.TestCase):

    def setUp(self):
        """
        Set up a Checker instance with initial values.
        """
        self.checker = Checker()
        self.correct_content = """META
        key;value
        description;desc
        country;Poland
        unit;TestUnit
        instance;TestInstance
        num_projects;2
        num_votes;3
        budget;500
        vote_type;approval
        rule;greedy
        date_begin;01.01.2024
        date_end;31.01.2024
        PROJECTS
        project_id;cost;votes;name;selected
        1;500;2;Project1;1
        2;300;2;Project2;0
        VOTES
        voter_id;vote;sex
        voter1;1,2;M
        voter2;1;F
        voter3;2;F
        """.replace(
            " ", ""
        )

    def test_integration_valid_file(self):
        """
        Test a complete valid file to ensure no errors are logged.
        """
        results = self.checker.process_files([self.correct_content])
        # Validate that the file has no errors
        self.assertEqual(
            results["metadata"]["valid"], 1, "Valid file incorrectly marked as invalid."
        )
        self.assertEqual(
            results["metadata"]["invalid"], 0, "Invalid files count should be zero."
        )

    def test_integration_invalid_field_values(self):
        """
        Test a invalid file to ensure no errors are logged.
        (wrong end date, project with no cost, and sex X)
        """
        incorrect_content = deepcopy(self.correct_content)
        incorrect_content = incorrect_content.replace(
            "date_end;31.01.2024", "date_end;321213"
        )
        incorrect_content = incorrect_content.replace(
            "1;500;2;Project1;1", "1;0;2;Project1;1"
        )
        incorrect_content = incorrect_content.replace("voter3;2;F", "voter3;2;X")

        results = self.checker.process_files([incorrect_content])
        # Validate that the file has errors
        self.assertEqual(
            results["metadata"]["invalid"], 1, "Invalid file not marked as such."
        )
        errors = results[1]["results"]
        self.assertIn(
            "invalid meta field value",
            errors,
            "Invalid datatype error not logged.",
        )
        self.assertIn("project with no cost", errors, "Project cost error not logged.")
        self.assertIn(
            "invalid votes field value", errors, "Votes cost error not logged."
        )


if __name__ == "__main__":
    unittest.main()
