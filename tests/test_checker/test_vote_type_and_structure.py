import unittest

from pabulib.checker import Checker


class TestVoteTypeAndStructure(unittest.TestCase):
    def setUp(self):
        self.checker = Checker()

    def test_meta_requires_key_value_header(self):
        content = """META
description;Missing meta header
country;Poland
unit;Town
instance;2024
num_projects;1
num_votes;1
budget;100
vote_type;approval
rule;greedy
date_begin;2024
date_end;2024
PROJECTS
project_id;cost;votes
1;100;1
VOTES
voter_id;vote
v1;1
"""
        results = self.checker.process_files([content])
        errors = results[1]["results"]["errors"]
        self.assertIn("file structure error", errors)
        self.assertIn("META section must start with the header 'key;value'.", errors["file structure error"][1])

    def test_duplicate_project_id_is_reported(self):
        content = """META
key;value
description;Duplicate project
country;Poland
unit;Town
instance;2024
num_projects;2
num_votes;1
budget;100
vote_type;approval
rule;greedy
date_begin;2024
date_end;2024
PROJECTS
project_id;cost;votes
1;50;1
1;60;0
VOTES
voter_id;vote
v1;1
"""
        results = self.checker.process_files([content])
        errors = results[1]["results"]["errors"]
        self.assertIn("file structure error", errors)
        self.assertTrue(
            any("Duplicated project_id '1'." in message for message in errors["file structure error"].values())
        )

    def test_scoring_vote_type_is_supported(self):
        content = """META
key;value
description;Scoring ballot
country;Poland
unit;Town
instance;2024
num_projects;2
num_votes;1
budget;100
vote_type;scoring
rule;unknown
date_begin;2024
date_end;2024
default_score;0
PROJECTS
project_id;cost;score;selected
1;40;5;0
2;60;3;0
VOTES
voter_id;vote;points
v1;1,2;5,3
"""
        results = self.checker.process_files([content])
        file_results = results[1]["results"]
        errors = file_results.get("errors", {})
        invalid_meta_errors = errors.get("invalid meta field value", {})
        self.assertFalse(
            any("vote_type" in message for message in invalid_meta_errors.values()),
            f"Unexpected vote_type validation error: {invalid_meta_errors}",
        )

    def test_cumulative_requires_points_for_each_vote(self):
        content = """META
key;value
description;Cumulative ballot
country;Poland
unit;Town
instance;2024
num_projects;2
num_votes;1
budget;100
vote_type;cumulative
rule;unknown
date_begin;2024
date_end;2024
max_sum_points;10
PROJECTS
project_id;cost;score
1;40;5
2;60;3
VOTES
voter_id;vote
v1;1,2
"""
        results = self.checker.process_files([content])
        errors = results[1]["results"]["errors"]
        self.assertIn("missing points for vote_type", errors)

    def test_points_length_must_match_vote_length(self):
        content = """META
key;value
description;Scoring mismatch
country;Poland
unit;Town
instance;2024
num_projects;2
num_votes;1
budget;100
vote_type;scoring
rule;unknown
date_begin;2024
date_end;2024
PROJECTS
project_id;cost;score
1;40;5
2;60;3
VOTES
voter_id;vote;points
v1;1,2;5
"""
        results = self.checker.process_files([content])
        errors = results[1]["results"]["errors"]
        self.assertIn("vote/points length mismatch", errors)

    def test_choose_one_requires_exactly_one_project(self):
        content = """META
key;value
description;Choose one ballot
country;Poland
unit;Town
instance;2024
num_projects;2
num_votes;1
budget;100
vote_type;choose-1
rule;unknown
date_begin;2024
date_end;2024
PROJECTS
project_id;cost;votes
1;40;1
2;60;1
VOTES
voter_id;vote
v1;1,2
"""
        results = self.checker.process_files([content])
        errors = results[1]["results"]["errors"]
        self.assertIn("invalid choose-1 vote length", errors)

    def test_approval_respects_max_sum_cost(self):
        content = """META
key;value
description;Approval cost limit
country;Poland
unit;Town
instance;2024
num_projects;2
num_votes;1
budget;100
vote_type;approval
rule;unknown
date_begin;2024
date_end;2024
max_sum_cost;50
PROJECTS
project_id;cost;votes
1;40;1
2;30;1
VOTES
voter_id;vote
v1;1,2
"""
        results = self.checker.process_files([content])
        warnings = results[1]["results"]["warnings"]
        self.assertIn("approval vote cost above maximum", warnings)

    def test_invalid_calendar_date_is_reported(self):
        content = """META
key;value
description;Invalid date
country;Poland
unit;Town
instance;2024
num_projects;1
num_votes;1
budget;100
vote_type;approval
rule;unknown
date_begin;31.02.2024
date_end;2024
PROJECTS
project_id;cost;votes
1;100;1
VOTES
voter_id;vote
v1;1
"""
        results = self.checker.process_files([content])
        errors = results[1]["results"]["errors"]
        self.assertIn("invalid meta field value", errors)
        self.assertTrue(
            any("Invalid date_begin value '31.02.2024'" in message for message in errors["invalid meta field value"].values())
        )

    def test_non_increasing_points_order_warning(self):
        content = """META
key;value
description;Scoring order
country;Poland
unit;Town
instance;2024
num_projects;3
num_votes;1
budget;100
vote_type;scoring
rule;unknown
date_begin;2024
date_end;2024
PROJECTS
project_id;cost;score
1;20;5
2;30;4
3;40;3
VOTES
voter_id;vote;points
v1;1,2,3;3,5,1
"""
        results = self.checker.process_files([content])
        warnings = results[1]["results"]["warnings"]
        self.assertIn("vote order not sorted by points", warnings)

    def test_max_length_cannot_exceed_num_projects(self):
        content = """META
key;value
description;Invalid max length
country;Poland
unit;Town
instance;2024
num_projects;2
num_votes;1
budget;100
vote_type;approval
rule;unknown
date_begin;2024
date_end;2024
max_length;3
PROJECTS
project_id;cost;votes
1;40;1
2;60;1
VOTES
voter_id;vote
v1;1,2
"""
        results = self.checker.process_files([content])
        errors = results[1]["results"]["errors"]
        self.assertIn("invalid meta field value", errors)
        self.assertTrue(
            any(
                "max_length `3` cannot be higher than num_projects `2`" in message
                for message in errors["invalid meta field value"].values()
            )
        )

    def test_near_duplicate_categories_raise_warning(self):
        content = """META
key;value
description;Category normalization
country;Poland
unit;Town
instance;2024
num_projects;2
num_votes;1
budget;100
vote_type;approval
rule;unknown
categories;sport,Sport
date_begin;2024
date_end;2024
PROJECTS
project_id;cost;votes;category
1;40;1;sport
2;60;0;Sport
VOTES
voter_id;vote
v1;1
"""
        results = self.checker.process_files([content])
        warnings = results[1]["results"]["warnings"]
        self.assertIn("inconsistent label normalization", warnings)


if __name__ == "__main__":
    unittest.main()
