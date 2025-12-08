"""
Test cases for empty line removal functionality in the checker.
"""

import os
import sys
import tempfile
from io import StringIO
from unittest import TestCase

# Add project root to path for local imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

from pabulib.checker import Checker


class TestEmptyLineRemoval(TestCase):
    """Test empty line removal functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.checker = Checker()

    def test_empty_line_removal_count(self):
        """Test that empty lines are properly removed and counted."""
        # Create test content with known empty lines
        test_content = """META
key;value
description;Test file with empty lines
country;Test Country

num_projects;2
num_votes;2


budget;1000
vote_type;approval

PROJECTS
project_id;cost;name
1;100;Project One
2;200;Project Two

VOTES
voter_id;vote
1;1
2;2

"""
        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pb", delete=False) as f:
            f.write(test_content)
            temp_file_path = f.name

        try:
            # Process the file
            results = self.checker.process_files([temp_file_path])

            # Check that empty lines were removed and counted
            # Should be in warnings, not errors
            self.assertEqual(results["metadata"]["processed"], 1)
            file_key = next(
                (k for k in results.keys() if k not in ["metadata", "summary"]), None
            )
            self.assertIsNotNone(file_key)

            file_results = results[file_key]["results"]
            if isinstance(file_results, dict) and "warnings" in file_results:
                warnings = file_results["warnings"]
                self.assertIn("empty lines removed", warnings)
                self.assertIn(
                    "Removed 6 empty lines from the file.",
                    warnings["empty lines removed"][1],
                )

        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def test_no_empty_lines_to_remove(self):
        """Test behavior when there are no empty lines to remove."""
        # Create test content without empty lines
        test_content = """META
key;value
description;Test file without empty lines
country;Test Country
num_projects;1
num_votes;1
budget;1000
vote_type;approval
PROJECTS
project_id;cost;name
1;100;Project One
VOTES
voter_id;vote
1;1"""

        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pb", delete=False) as f:
            f.write(test_content)
            temp_file_path = f.name

        try:
            # Capture stdout to check the removal message
            old_stdout = sys.stdout
            sys.stdout = captured_output = StringIO()

            # Process the file
            self.checker.process_files([temp_file_path])

            # Restore stdout
            sys.stdout = old_stdout
            output = captured_output.getvalue()

            # Check that no empty line removal message appears
            self.assertNotIn("Removed", output)
            self.assertNotIn("empty lines", output)

        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def test_empty_line_removal_with_real_file(self):
        """Test empty line removal with the actual test file."""
        test_file_path = os.path.join(
            os.path.dirname(__file__), "..", "test_empty_lines.pb"
        )

        # Check if the test file exists
        if not os.path.exists(test_file_path):
            self.skipTest(f"Test file {test_file_path} not found")

        # Process the file
        results = self.checker.process_files([test_file_path])

        # Check that empty lines were removed and counted
        # Should be in warnings, not errors
        self.assertEqual(results["metadata"]["processed"], 1)
        file_key = next(
            (k for k in results.keys() if k not in ["metadata", "summary"]), None
        )
        self.assertIsNotNone(file_key)

        file_results = results[file_key]["results"]
        if isinstance(file_results, dict) and "warnings" in file_results:
            warnings = file_results["warnings"]
            self.assertIn("empty lines removed", warnings)
            self.assertIn(
                "Removed 6 empty lines from the file.",
                warnings["empty lines removed"][1],
            )

    def test_empty_line_removal_modifies_lines_in_place(self):
        """Test that empty line removal modifies the lines list in place."""
        # Create lines with empty lines
        lines = [
            "META",
            "key;value",
            "description;Test",
            "",  # empty line
            "country;Test",
            "",  # empty line
            "PROJECTS",
            "project_id;cost",
            "1;100",
            "",  # empty line
        ]

        original_length = len(lines)
        empty_count = sum(1 for line in lines if line.strip() == "")

        # Initialize file_results before calling the method
        from copy import deepcopy

        self.checker.file_results = deepcopy(self.checker.error_levels)

        # Call the method directly
        self.checker.check_empty_lines(lines)

        # Check that empty lines were removed
        self.assertEqual(len(lines), original_length - empty_count)
        self.assertNotIn("", lines)

        # Verify all remaining lines have content
        for line in lines:
            self.assertTrue(line.strip(), "All lines should have non-empty content")
