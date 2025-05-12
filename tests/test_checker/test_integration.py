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
        errors = results[1]["results"]["errors"]
        self.assertIn(
            "invalid meta field value",
            errors,
            "Invalid datatype error not logged.",
        )
        self.assertIn("project with no cost", errors, "Project cost error not logged.")
        self.assertIn(
            "invalid votes field value", errors, "Votes cost error not logged."
        )

    def test_greedy_with_threshold(self):
        """
        Greedy rule with threshold:
        - First: correct (project 1 selected, votes = 3, above threshold).
        - Second: incorrect (project 1 selected, but votes = 2 → below threshold).
        """
        content = """META
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
        min_project_score_threshold;3
        PROJECTS
        project_id;cost;votes;name;selected
        1;500;3;Project1;1
        2;300;1;Project2;0
        VOTES
        voter_id;vote;sex
        voter1;1;M
        voter2;1;F
        voter3;1,2;F
        """.replace(
            " ", ""
        )
        results = self.checker.process_files([content])
        self.assertEqual(results["metadata"]["invalid"], 0)

        # Now test incorrect: Project 1 has only 2 voters → votes should be 2
        incorrect = content.replace("1;500;3;Project1;1", "1;500;2;Project1;1")
        incorrect = incorrect.replace("voter1;1;M", "voter1;;M")  # Remove one vote
        results = self.checker.process_files([incorrect])
        self.assertEqual(results["metadata"]["invalid"], 1)
        self.assertIn("threshold violation", results[1]["results"]["errors"])

    def test_greedy_without_threshold(self):
        """
        Greedy rule without threshold:
        - First: correct selection (Project 1 has highest votes and fits budget).
        - Second: incorrect selection (Project 2 selected instead of Project 1).
        """
        content = """META
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
        1;500;3;Project1;1
        2;300;1;Project2;0
        VOTES
        voter_id;vote;sex
        voter1;1;M
        voter2;1;F
        voter3;1,2;F
        """.replace(
            " ", ""
        )
        results = self.checker.process_files([content])
        self.assertEqual(results["metadata"]["invalid"], 0)

        # Now simulate incorrect selection (Project 1 should have been picked, but Project 2 is marked selected)
        incorrect = content.replace("1;500;3;Project1;1", "1;500;3;Project1;0")
        incorrect = incorrect.replace("2;300;1;Project2;0", "2;300;1;Project2;1")
        results = self.checker.process_files([incorrect])
        self.assertEqual(results["metadata"]["invalid"], 1)
        self.assertIn("greedy rule not followed", results[1]["results"]["errors"])

    def test_greedy_threshold_vs_no_threshold(self):
        """
        Greedy rule behavior with and without threshold:
        - With threshold (3): only project 1 (votes=3) should be selected.
        - Without threshold: both projects should be selected (budget allows).
        """
        base_content = """META
        key;value
        description;desc
        country;Poland
        unit;TestUnit
        instance;TestInstance
        num_projects;3
        num_votes;3
        budget;800
        vote_type;approval
        rule;greedy
        date_begin;01.01.2024
        date_end;31.01.2024
        {threshold_line}
        PROJECTS
        project_id;cost;votes;name;selected
        1;500;3;Project1;1
        2;300;2;Project2;{selected_2}
        3;200;1;Project3;0
        VOTES
        voter_id;vote;sex
        voter1;1;M
        voter2;1,2;F
        voter3;1,2,3;F
        """.replace(
            " ", ""
        )

        # ---- CASE 1: With threshold → only project 1 selected ----
        with_threshold = base_content.format(
            threshold_line="min_project_score_threshold;3", selected_2="0"
        )
        results = self.checker.process_files([with_threshold])
        self.assertEqual(results["metadata"]["invalid"], 0)

        # ---- CASE 2: Without threshold → both projects selected ----
        without_threshold = base_content.format(
            threshold_line="min_project_score_threshold;0", selected_2="1"
        )
        results = self.checker.process_files([without_threshold])
        self.assertEqual(results["metadata"]["invalid"], 0)

        # ---- CASE 3: ERROR — With threshold, but project 2 selected anyway ----
        incorrect_with_threshold = base_content.format(
            threshold_line="min_project_score_threshold;3", selected_2="1"
        )
        results = self.checker.process_files([incorrect_with_threshold])
        self.assertEqual(results["metadata"]["invalid"], 1)
        self.assertIn("threshold violation", results[1]["results"]["errors"])


if __name__ == "__main__":
    unittest.main()
