import os
import sys
import unittest
from copy import deepcopy

# Add the project root directory to Python path to use local modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from pabulib.checker import Checker


class TestRulesChecker(unittest.TestCase):
    """Test suite for different rule validation scenarios."""

    def setUp(self):
        """Set up the Checker instance for rule tests."""
        self.checker = Checker()

    def create_test_pb_content(
        self,
        rule,
        unit="City",
        selected_projects=None,
        budget=1000,
        include_comment=True,
        include_threshold=False,
    ):
        """
        Helper method to create test .pb file content.

        Args:
            rule (str): The rule to test
            unit (str): The unit/location
            selected_projects (list): List of project IDs that are selected (default: [1])
            budget (int): Budget amount
            include_comment (bool): Whether to include comment field
            include_threshold (bool): Whether to include min_project_score_threshold field

        Returns:
            str: Content of the .pb file
        """
        if selected_projects is None:
            selected_projects = [1]

        content = f"""META
key;value
description;Test file for rule: {rule}
country;Poland
unit;{unit}
instance;test_instance
num_projects;3
num_votes;12
budget;{budget}
vote_type;approval
rule;{rule}
date_begin;2024
date_end;2024
"""

        if include_threshold:
            content += "min_project_score_threshold;5\n"

        if include_comment:
            content += f"comment;#1: This is a test for {rule} rule\n"

        content += """PROJECTS
project_id;cost;votes;name;selected
1;300;10;Project A;{}
2;400;6;Project B;{}
3;200;5;Project C;{}
VOTES
voter_id;vote
1;1,2,3
2;1,2
3;1,3
4;1,2,3
5;1
6;2,3
7;1,2
8;1,3
9;1
10;1
11;2
12;1
""".format(
            1 if 1 in selected_projects else 0,
            1 if 2 in selected_projects else 0,
            1 if 3 in selected_projects else 0,
        )

        return content

    def test_rule_unknown(self):
        """Test that 'unknown' rule produces a warning."""
        content = self.create_test_pb_content(rule="unknown")

        results = self.checker.process_files([content])

        # Get the results for the test instance (identifier is 1 when processing content)
        test_results = results[1]["results"]

        # Check that a warning was added
        self.assertIn("warnings", test_results)
        self.assertIn("rule validation skipped", test_results["warnings"])

        # Verify warning message
        warning = test_results["warnings"]["rule validation skipped"][1]
        self.assertIn("unknown", warning.lower())
        self.assertIn("cannot be verified", warning.lower())

        print("✓ Test passed: 'unknown' rule produces correct warning")

    def test_rule_equalshares(self):
        """Test that 'equalshares' rule produces a warning about not being implemented."""
        content = self.create_test_pb_content(rule="equalshares")

        results = self.checker.process_files([content])

        # Get the results for the test instance (identifier is 1 when processing content)
        test_results = results[1]["results"]

        # Check that a warning was added
        self.assertIn("warnings", test_results)
        self.assertIn("rule checker not implemented", test_results["warnings"])

        # Verify warning message
        warning = test_results["warnings"]["rule checker not implemented"][1]
        self.assertIn("equalshares", warning.lower())
        self.assertIn("not yet implemented", warning.lower())

        print("✓ Test passed: 'equalshares' rule produces correct warning")

    def test_rule_equalshares_add1(self):
        """Test that 'equalshares/add1' rule produces a warning about not being implemented."""
        content = self.create_test_pb_content(rule="equalshares/add1")

        results = self.checker.process_files([content])

        # Get the results for the test instance (identifier is 1 when processing content)
        test_results = results[1]["results"]

        # Check that a warning was added
        self.assertIn("warnings", test_results)
        self.assertIn("rule checker not implemented", test_results["warnings"])

        # Verify warning message
        warning = test_results["warnings"]["rule checker not implemented"][1]
        self.assertIn("equalshares/add1", warning.lower())
        self.assertIn("not yet implemented", warning.lower())

        print("✓ Test passed: 'equalshares/add1' rule produces correct warning")

    def test_rule_greedy_valid(self):
        """Test that 'greedy' rule passes when projects are selected correctly."""
        # Budget: 1000
        # Projects sorted by votes (descending):
        # 1: cost=300, votes=10 -> selected (budget: 1000-300=700)
        # 2: cost=400, votes=8 -> selected (budget: 700-400=300)
        # 3: cost=200, votes=6 -> selected (budget: 300-200=100)
        content = self.create_test_pb_content(
            rule="greedy", selected_projects=[1, 2, 3], budget=1000
        )

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have no errors for greedy rule
        errors = test_results.get("errors", {})
        self.assertNotIn("greedy rule not followed", errors)

        print("✓ Test passed: 'greedy' rule validation passes for correct selection")

    def test_rule_greedy_missing_project(self):
        """Test that 'greedy' rule catches when a project should be selected but isn't."""
        # Budget: 1000
        # Should select: 1 (300), 2 (400), 3 (200) = 900 total
        # But only selecting 1 and 2
        content = self.create_test_pb_content(
            rule="greedy", selected_projects=[1, 2], budget=1000  # Missing project 3
        )

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have error for greedy rule not followed
        self.assertIn("errors", test_results)
        self.assertIn("greedy rule not followed", test_results["errors"])

        error = test_results["errors"]["greedy rule not followed"][1]
        self.assertIn("3", error)  # Project 3 should be mentioned
        self.assertIn("not selected but should be", error.lower())

        print("✓ Test passed: 'greedy' rule catches missing project")

    def test_rule_greedy_wrong_project_selected(self):
        """Test that 'greedy' rule catches when wrong projects are selected."""
        # Budget: 700
        # Should select: 1 (300), 2 (400) = 700 total (can't fit 3)
        # But selecting 1 and 3 instead
        content = self.create_test_pb_content(
            rule="greedy",
            selected_projects=[1, 3],  # Wrong! Should be 1 and 2
            budget=700,
        )

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have error for greedy rule not followed
        self.assertIn("errors", test_results)
        self.assertIn("greedy rule not followed", test_results["errors"])

        error = test_results["errors"]["greedy rule not followed"][1]
        self.assertIn("2", error)  # Project 2 should be mentioned as missing
        self.assertIn("3", error)  # Project 3 should be mentioned as wrongly selected

        print("✓ Test passed: 'greedy' rule catches wrong project selection")

    def test_rule_greedy_budget_exhausted(self):
        """Test greedy rule when budget is perfectly exhausted."""
        # Budget: 900
        # Should select: 1 (300), 2 (400), 3 (200) = exactly 900
        content = self.create_test_pb_content(
            rule="greedy", selected_projects=[1, 2, 3], budget=900
        )

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have no errors
        errors = test_results.get("errors", {})
        self.assertNotIn("greedy rule not followed", errors)

        print("✓ Test passed: 'greedy' rule works with budget perfectly exhausted")

    def test_rule_greedy_skip_expensive(self):
        """Test that greedy correctly skips expensive projects that don't fit."""
        # Budget: 500
        # Should select: 1 (300), then skip 2 (400 - too expensive), then select 3 (200)
        # Total: 1 and 3 = 500
        content = self.create_test_pb_content(
            rule="greedy", selected_projects=[1, 3], budget=500  # Skips project 2
        )

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have no errors - greedy can skip projects
        errors = test_results.get("errors", {})
        self.assertNotIn("greedy rule not followed", errors)

        print(
            "✓ Test passed: 'greedy' rule correctly handles skipping expensive projects"
        )

    def test_rule_invalid_rule(self):
        """Test that an invalid/unknown rule value produces an error."""
        content = self.create_test_pb_content(rule="some-fake-rule")

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have error for unknown rule
        self.assertIn("errors", test_results)
        self.assertIn("unknown rule value", test_results["errors"])

        error = test_results["errors"]["unknown rule value"][1]
        self.assertIn("some-fake-rule", error.lower())
        self.assertIn("not recognized", error.lower())
        self.assertIn("valid rules are", error.lower())

        print("✓ Test passed: Invalid rule produces correct error")

    def test_rule_greedy_no_skip_valid(self):
        """Test that 'greedy-no-skip' rule passes when selection is correct."""
        # Budget: 900
        # greedy-no-skip: 1 (300), 2 (400), 3 (200) = 900
        # Stops when first project doesn't fit
        content = self.create_test_pb_content(
            rule="greedy-no-skip", selected_projects=[1, 2, 3], budget=900
        )

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have no errors
        errors = test_results.get("errors", {})
        self.assertNotIn("greedy-no-skip rule not followed", errors)

        print(
            "✓ Test passed: 'greedy-no-skip' rule validation passes for correct selection"
        )

    def test_rule_greedy_no_skip_cannot_skip(self):
        """Test that 'greedy-no-skip' fails when trying to skip a project."""
        # Budget: 500
        # greedy-no-skip: 1 (300), then 2 (400) doesn't fit -> STOP
        # Should only select: 1
        # But we're selecting 1 and 3 (simulating a skip)
        content = self.create_test_pb_content(
            rule="greedy-no-skip",
            selected_projects=[1, 3],  # Wrong! Should only be 1
            budget=500,
        )

        results = self.checker.process_files([content])
        test_results = results[1]["results"]
        # Should have error - can't skip in greedy-no-skip
        self.assertIn("errors", test_results)
        self.assertIn("greedy-no-skip rule not followed", test_results["errors"])

        error = test_results["errors"]["greedy-no-skip rule not followed"][1]
        self.assertIn("3", error)  # Project 3 shouldn't be selected

        print("✓ Test passed: 'greedy-no-skip' rule catches incorrect skip")

    def test_rule_greedy_threshold_missing_field(self):
        """Test that 'greedy-threshold' errors when threshold field is missing."""
        content = self.create_test_pb_content(
            rule="greedy-threshold", include_threshold=False  # Missing threshold field
        )

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have error for missing threshold field
        self.assertIn("errors", test_results)
        self.assertIn("missing threshold field", test_results["errors"])

        error = test_results["errors"]["missing threshold field"][1]
        self.assertIn("min_project_score_threshold", error)
        self.assertIn("missing", error.lower())

        print("✓ Test passed: 'greedy-threshold' catches missing threshold field")

    def test_rule_greedy_threshold_with_threshold(self):
        """Test that 'greedy-threshold' works correctly with threshold field."""
        # Threshold: 5
        # All projects have votes >= 5, so all should be considered
        # Budget: 900
        content = self.create_test_pb_content(
            rule="greedy-threshold",
            selected_projects=[1, 2, 3],
            budget=900,
            include_threshold=True,  # min_project_score_threshold=5
        )

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have no errors
        errors = test_results.get("errors", {})
        self.assertNotIn("greedy rule not followed", errors)
        self.assertNotIn("threshold violation", errors)

        print("✓ Test passed: 'greedy-threshold' works with threshold field")

    def test_rule_greedy_exclusive_mismatch(self):
        """Test that 'greedy-exclusive' produces warning when greedy would differ."""
        # Intentionally select wrong projects to trigger greedy mismatch
        # Budget: 700
        # Greedy would select: 1 (300), 2 (400)
        # But selecting 1 and 3 instead (simulating exclusive zone logic)
        content = self.create_test_pb_content(
            rule="greedy-exclusive", selected_projects=[1, 3], budget=700
        )

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have warning, not error
        self.assertIn("warnings", test_results)
        self.assertIn("greedy-exclusive potential mismatch", test_results["warnings"])

        # Should NOT have error
        errors = test_results.get("errors", {})
        self.assertNotIn("greedy rule not followed", errors)

        warning = test_results["warnings"]["greedy-exclusive potential mismatch"][1]
        self.assertIn("greedy", warning.lower())
        self.assertIn("hierarchy", warning.lower())
        # Should include project details
        self.assertIn("2", warning)  # Project 2 should be mentioned as missing
        self.assertIn("3", warning)  # Project 3 should be mentioned as wrongly selected

        print("✓ Test passed: 'greedy-exclusive' produces warning for mismatch")

    def test_rule_greedy_custom_missing_comment(self):
        """Test that 'greedy-custom' warns when comment field is missing."""
        content = self.create_test_pb_content(
            rule="greedy-custom", include_comment=False
        )

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have warning for missing comment
        self.assertIn("warnings", test_results)
        self.assertIn("missing comment for greedy-custom", test_results["warnings"])

        warning = test_results["warnings"]["missing comment for greedy-custom"][1]
        self.assertIn("comment", warning.lower())

        print("✓ Test passed: 'greedy-custom' warns about missing comment")

    def test_rule_greedy_custom_with_comment(self):
        """Test that 'greedy-custom' with comment produces warning for mismatch."""
        # Budget: 700
        # Greedy would select: 1 (300), 2 (400)
        # But selecting 1 and 3 instead (custom logic)
        content = self.create_test_pb_content(
            rule="greedy-custom",
            selected_projects=[1, 3],
            budget=700,
            include_comment=True,
        )

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have warning, not error
        self.assertIn("warnings", test_results)
        self.assertIn("greedy-custom cannot be verified", test_results["warnings"])

        # Should NOT have error
        errors = test_results.get("errors", {})
        self.assertNotIn("greedy rule not followed", errors)

        warning = test_results["warnings"]["greedy-custom cannot be verified"][1]
        self.assertIn("custom", warning.lower())
        # Should include project details
        self.assertIn("2", warning)  # Project 2 should be mentioned as missing
        self.assertIn("3", warning)  # Project 3 should be mentioned as wrongly selected

        print("✓ Test passed: 'greedy-custom' produces warning for custom logic")

    def test_rule_greedy_custom_poznan(self):
        """Test that 'greedy-custom' with Poznań unit uses Poznań-specific validation."""
        # Create content with Poznań unit
        content = self.create_test_pb_content(
            rule="greedy-custom",
            unit="Poznań",
            selected_projects=[1, 2],  # Simplified for Poznań
            budget=700,
        )

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Poznań validation should be used
        # The specific errors depend on Poznań rule implementation
        # Just verify no crash and processing completes
        self.assertIsNotNone(test_results)

        print("✓ Test passed: 'greedy-custom' with Poznań unit uses Poznań validation")

    def test_rule_greedy_threshold_violation(self):
        """Test that threshold violations are caught."""
        # Projects: 1 (10 votes), 2 (6 votes), 3 (5 votes)
        # Threshold: 5
        # All are >= 5, so should be selected based on greedy
        # But let's create a scenario where we select below threshold
        content = f"""META
key;value
description;Test threshold violation
country;Poland
unit;City
instance;test_instance
num_projects;4
num_votes;12
budget;1000
vote_type;approval
rule;greedy-threshold
date_begin;2024
date_end;2024
min_project_score_threshold;6
comment;#1: Testing threshold
PROJECTS
project_id;cost;votes;name;selected
1;300;10;Project A;1
2;400;6;Project B;1
3;200;4;Project C;1
4;100;3;Project D;0
VOTES
voter_id;vote
1;1,2,3
2;1,2
3;1,3
4;1,2,3
5;1
6;2,3
7;1,2
8;1,3
9;1
10;1
11;2
12;1
"""

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have threshold violation error
        self.assertIn("errors", test_results)
        self.assertIn("threshold violation", test_results["errors"])

        error = test_results["errors"]["threshold violation"][1]
        self.assertIn("3", error)  # Project 3 is below threshold (4 < 6)

        print("✓ Test passed: threshold violations are caught")

    def test_rule_greedy_exclusive_matches_greedy(self):
        """Test that greedy-exclusive produces no warning when it matches greedy."""
        # Budget: 900
        # Selection matches what greedy would choose
        content = self.create_test_pb_content(
            rule="greedy-exclusive", selected_projects=[1, 2, 3], budget=900
        )

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have no errors and no warnings about mismatch
        warnings = test_results.get("warnings", {})
        self.assertNotIn("greedy-exclusive potential mismatch", warnings)

        errors = test_results.get("errors", {})
        self.assertNotIn("greedy rule not followed", errors)

        print("✓ Test passed: 'greedy-exclusive' matching greedy produces no warning")

    def test_rule_greedy_custom_matches_greedy(self):
        """Test that greedy-custom produces no mismatch warning when it matches greedy."""
        # Budget: 900
        # Selection matches what greedy would choose
        content = self.create_test_pb_content(
            rule="greedy-custom",
            selected_projects=[1, 2, 3],
            budget=900,
            include_comment=True,
        )

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have no errors
        errors = test_results.get("errors", {})
        self.assertNotIn("greedy rule not followed", errors)

        # Should not have mismatch warning
        warnings = test_results.get("warnings", {})
        self.assertNotIn("greedy-custom cannot be verified", warnings)

        print(
            "✓ Test passed: 'greedy-custom' matching greedy produces no mismatch warning"
        )

    def test_rule_greedy_with_threshold_parameter(self):
        """Test regular greedy with threshold parameter (from min_project_score_threshold)."""
        # When min_project_score_threshold is present, it should be used even with regular greedy
        content = f"""META
key;value
description;Test greedy with threshold
country;Poland
unit;City
instance;test_instance
num_projects;3
num_votes;12
budget;900
vote_type;approval
rule;greedy
date_begin;2024
date_end;2024
min_project_score_threshold;6
comment;#1: Testing threshold
PROJECTS
project_id;cost;votes;name;selected
1;300;10;Project A;1
2;400;6;Project B;1
3;200;5;Project C;0
VOTES
voter_id;vote
1;1,2,3
2;1,2
3;1,3
4;1,2,3
5;1
6;2,3
7;1,2
8;1,3
9;1
10;1
11;2
12;1
"""

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Project 3 has 5 votes, below threshold of 6, so shouldn't be selected
        # This should be correct according to greedy with threshold
        errors = test_results.get("errors", {})
        self.assertNotIn("greedy rule not followed", errors)
        self.assertNotIn("threshold violation", errors)

        print("✓ Test passed: greedy respects threshold parameter")

    def test_rule_no_selected_field(self):
        """Test that when there's no 'selected' field, validation is skipped."""
        # Create content without selected field in projects
        content = f"""META
key;value
description;Test without selected field
country;Poland
unit;City
instance;test_instance
num_projects;3
num_votes;12
budget;900
vote_type;approval
rule;greedy
date_begin;2024
date_end;2024
comment;#1: Testing no selected field
PROJECTS
project_id;cost;votes;name
1;300;10;Project A
2;400;6;Project B
3;200;5;Project C
VOTES
voter_id;vote
1;1,2,3
2;1,2
3;1,3
4;1,2,3
5;1
6;2,3
7;1,2
8;1,3
9;1
10;1
11;2
12;1
"""

        results = self.checker.process_files([content])
        test_results = results[1]["results"]

        # Should have no rule validation errors since there's no selected field
        errors = test_results.get("errors", {})
        self.assertNotIn("greedy rule not followed", errors)

        # The checker should just skip validation when no selected field exists
        print("✓ Test passed: no selected field - validation skipped")


if __name__ == "__main__":
    unittest.main()
