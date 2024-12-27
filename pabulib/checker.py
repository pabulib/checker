import json
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Union

from pabulib_helpers import fields as flds
from pabulib_helpers import parse_pb_lines
from pabulib_helpers import utilities as utils


@dataclass
class Checker:

    def __post_init__(self):
        self.results = dict()  # results of all data
        self.results["metadata"] = dict()  # metadata, how many files was processed
        self.results["metadata"]["processed"] = 0
        self.results["metadata"]["valid"] = 0
        self.results["metadata"]["invalid"] = 0
        self.results["summary"] = defaultdict(
            lambda: 0
        )  # sum of errors across all files
        self.error_counters = defaultdict(lambda: 1)
        self.counted_votes = defaultdict(int)
        self.counted_scores = defaultdict(int)

    def add_error(self, type, details):
        current_count = self.error_counters[type]
        try:
            self.file_results[type][current_count] = details
        except KeyError:
            self.file_results[type] = {current_count: details}

        self.error_counters[type] += 1
        self.results["summary"][type] += 1

    def check_empty_lines(self, lines):
        if lines and lines[-1].strip() == "":
            lines.pop()
        empty_lines = [i for i, line in enumerate(lines, start=1) if line.strip() == ""]
        if empty_lines:
            type = "empty lines"
            details = f"contains empty lines at: {empty_lines}"
            self.add_error(type, details)

    def check_if_commas_in_floats(self):
        """Check if there is a comma in float values."""

        type = "comma in float!"
        if "," in self.meta["budget"]:
            self.add_error(type, "in budget")
            # replace it to continue with other checks
            self.meta["budget"] = self.meta["budget"].replace(",", ".")
        if self.meta.get("max_sum_cost"):
            if "," in self.meta["max_sum_cost"]:
                self.add_error(type, "in max_sum_cost")
                # replace it to continue with other checks
                self.meta["max_sum_cost"] = self.meta["max_sum_cost"].replace(",", ".")
        for project_id, project_data in self.projects.items():
            cost = project_data["cost"]
            if not isinstance(cost, int):
                if "," in cost:
                    self.add_error(type, f"in project: `{project_id}`, cost: `{cost}`")
                    # replace it to continue with other checks
                    self.projects[project_id]["cost"] = str(cost).split(",")[0]

    def check_budgets(self) -> None:
        """Check if budget exceeded or if too expensive project."""

        budget_spent = 0
        all_projects_cost = 0
        budget_available = math.floor(float(self.meta["budget"].replace(",", ".")))
        all_projects = list()
        for project_id, project_data in self.projects.items():
            selected_field = project_data.get("selected")
            project_cost = int(project_data["cost"])
            all_projects_cost += project_cost
            if selected_field:
                if int(selected_field) == 1:
                    all_projects.append(
                        [project_id, project_cost, project_data["name"]]
                    )
                    budget_spent += project_cost
            if project_cost == 0:
                type = "project with no cost"
                details = f"project: `{project_id}` has not cost!"
                self.add_error(type, details)
            elif project_cost > budget_available:
                type = "single project exceeded whole budget"
                details = f"project `{project_id}` has exceeded the whole budget! cost: `{project_cost}` vs budget: `{budget_available}`"
                self.add_error(type, details)
        if budget_spent > budget_available:
            type = "budget exceeded"
            details = f"Budget: `{budget_available}`, cost of selected projects: {budget_spent}"
            self.add_error(type, details)
            # for project in all_projects:
            #     print(project)
        if self.meta.get("fully_funded") and int(self.meta["fully_funded"]) == 1:
            return
        # IF NOT FULLY FUNDED FLAG, THEN CHECK IF budget not exceeded:
        if budget_available > all_projects_cost:
            type = "all projects funded"
            details = f"budget: {utils.get_str_with_sep_from(budget_available)}, cost of all projects: {utils.get_str_with_sep_from(all_projects_cost)}"
            self.add_error(type, details)
        # check if unused budget
        budget_remaining = budget_available - budget_spent
        for project_id, project_data in self.projects.items():
            selected_field = project_data.get("selected")
            if selected_field:
                if int(selected_field) == 0:
                    project_cost = int(project_data["cost"])
                    if project_cost < budget_remaining:
                        type = "unused budget"
                        details = (
                            f"project: {project_id} can be funded but it's not selected"
                        )
                        self.add_error(type, details)

    def check_number_of_votes(self) -> None:
        """Compare number of votes from META and votes and log if not equal."""

        meta_votes = self.meta["num_votes"]
        if int(meta_votes) != len(self.votes):
            type = "different number of votes"
            details = f"votes number in META: `{meta_votes}` vs counted from file (number of rows in VOTES section): `{str(len(self.votes))}`"
            self.add_error(type, details)

    def check_number_of_projects(self) -> None:
        """Check if number of projects is the same as in META, log if not."""

        meta_projects = self.meta["num_projects"]
        if int(meta_projects) != len(self.projects):
            type = "different number of projects"
            details = f"projects number in meta: `{meta_projects}` vs counted from file (number of rows in PROJECTS section): `{str(len(self.projects))}`"
            self.add_error(type, details)

    def check_duplicated_votes(self):
        for voter, vote_data in self.votes.items():
            votes = vote_data["vote"].split(",")
            if len(votes) > len(set(votes)):
                type = "vote with duplicated projects"
                details = f"duplicated projects in a vote: Voter ID: `{voter}`, vote: `{votes}`."
                self.add_error(type, details)

    def check_vote_length(self) -> None:
        """Check if voter has more or less votes than allowed."""

        max_length = (
            self.meta.get("max_length")
            or self.meta.get("max_length_unit")
            or self.meta.get("max_length_district")
        )

        min_length = (
            self.meta.get("min_length")
            or self.meta.get("min_length_unit")
            or self.meta.get("min_length_district")
        )

        if max_length or min_length:
            for voter, vote_data in self.votes.items():
                votes = vote_data["vote"].split(",")
                voter_votes = len(votes)
                if max_length:
                    if voter_votes > int(max_length):
                        type = "vote length exceeded"
                        details = f"Voter ID: `{voter}`, max vote length: `{max_length}`, number of voter votes: `{voter_votes}`"
                        self.add_error(type, details)
                if min_length:
                    if voter_votes < int(min_length):
                        type = "vote length too short"
                        details = f"Voter ID: `{voter}`, min vote length: `{min_length}`, number of voter votes: `{voter_votes}`"

    def check_if_correct_votes_number(self) -> None:
        """Check if number of votes in PROJECTS is the same as counted.

        Count number of votes from VOTES section (given as dict) and check
        if it's the same as given in PROJECTS.

        Log if there is different number, if there is vote for project which
        is not listed or if project has no votes.
        """

        self.counted_votes = utils.count_votes_per_project(self.votes)
        for project_id, project_info in self.projects.items():
            votes = project_info.get("votes", 0) or 0
            if int(votes) == 0:
                type = "project with no votes"
                details = f"It's possible, that this project was not approved for voting! Project: {project_id}"
                self.add_error(type, details)
            counted_votes = self.counted_votes[project_id]
            if not int(project_info.get("votes", 0) or 0) == int(counted_votes or 0):
                type = f"different values in votes"
                file_votes = project_info.get("votes", 0)
                details = f"project: `{project_id}` file votes (in PROJECTS section): `{file_votes}` vs counted: {counted_votes}"
                self.add_error(type, details)

        for project_id, project_votes in self.counted_votes.items():
            if (
                not self.projects.get(project_id)
                or "votes" not in self.projects[project_id]
            ):
                type = f"different values in votes"
                details = f"project: `{project_id}` file votes (in PROJECTS section): `0` vs counted: {project_votes}"
                self.add_error(type, details)

    def check_if_correct_scores_number(self) -> None:
        """Check if score number given in PROJECTS is the same as counted.

        Count scores per projects and check if it's equal to given number.
        If not, log every project with inconsistent data.
        """

        self.counted_scores = utils.count_points_per_project(self.votes)
        for project_id, project_info in self.projects.items():
            counted_votes = self.counted_scores[project_id]

            if not int(project_info.get("score", 0) or 0) == int(counted_votes or 0):
                type = f"different values in scores"
                file_score = (project_info.get("score", 0),)
                details = f"project: `{project_id}` file scores (in PROJECTS section): `{file_score}` vs counted: {counted_votes}"
                self.add_error(type, details)

        for project_id, project_votes in self.counted_scores.items():
            if not self.projects.get(project_id):
                type = f"different values in scores"
                details = f"project: `{project_id}` file scores (in PROJECTS section): `0` vs counted: {project_votes}"

    def check_votes_and_scores(self):
        if not any([self.votes_in_projects, self.scores_in_projects]):
            type = "No votes or score counted in PROJECTS section"
            details = "There should be at least one field"
            self.add_error(type, details)
        if self.votes_in_projects:
            self.check_if_correct_votes_number()
        if self.scores_in_projects:
            self.check_if_correct_scores_number()

    def verify_poznan_selected(self, budget, projects, results):
        file_selected = dict()
        rule_selected = dict()
        get_rule_projects = True
        for project_id, project_dict in projects.items():
            project_cost = float(project_dict["cost"])
            cost_printable = utils.make_cost_printable(project_cost)
            row = [project_id, project_dict[results], cost_printable]
            if int(project_dict["selected"]) in (1, 2):
                # 2 for projects from 80% rule
                file_selected[project_id] = row
            if get_rule_projects:
                if budget >= project_cost:
                    rule_selected[project_id] = row
                    budget -= project_cost
                else:
                    if budget >= project_cost * 0.8:
                        # if there is no more budget but project costs
                        # 80% of left budget it would be funded
                        rule_selected[project_id] = row
                    get_rule_projects = False
        rule_selected_set = set(rule_selected.keys())
        file_selected_set = set(file_selected.keys())
        should_be_selected = rule_selected_set.difference(file_selected_set)
        if should_be_selected:
            type = "poznan rule not followed"
            details = f"Projects not selected but should be: {should_be_selected}"
            self.add_error(type, details)

        shouldnt_be_selected = file_selected_set.difference(rule_selected_set)
        if shouldnt_be_selected:
            type = "poznan rule not followed"
            details = f"Projects selected but should not: {shouldnt_be_selected}"
            self.add_error(type, details)

    def verify_greedy_selected(self, budget, projects, results):
        selected_projects = dict()
        greedy_winners = dict()
        for project_id, project_dict in projects.items():
            project_cost = float(project_dict["cost"])
            cost_printable = utils.make_cost_printable(project_cost)
            row = [project_id, project_dict[results], cost_printable]
            if int(project_dict["selected"]) == 1:
                selected_projects[project_id] = row
            if budget >= project_cost:
                greedy_winners[project_id] = row
                budget -= project_cost
        gw_set = set(greedy_winners.keys())
        selected_set = set(selected_projects.keys())
        should_be_selected = gw_set.difference(selected_set)
        # if should_be_selected:
        #     print(f"Projects not selected but should be: {should_be_selected}")

        shouldnt_be_selected = selected_set.difference(gw_set)
        # if shouldnt_be_selected:
        #    print(f"Projects selected but should not: {shouldnt_be_selected}")

        if should_be_selected or should_be_selected:
            type = "greedy rule not followed"
            details = f"Projects not selected but should be: {should_be_selected or ''}, and selected but shouldn't: {shouldnt_be_selected or ''}"
            self.add_error(type, details)

    def verify_selected(self):
        selected_field = next(iter(self.projects.values())).get("selected")
        if selected_field:
            projects = utils.sort_projects_by_results(self.projects)
            results = "votes"
            if self.scores_in_projects:
                results = "score"
            budget = float(self.meta["budget"].replace(",", "."))
            rule = self.meta["rule"]
            if self.meta["unit"] == "Poznań":
                self.verify_poznan_selected(budget, projects, results)
            elif rule == "greedy":
                self.verify_greedy_selected(budget, projects, results)
            else:
                # TODO add checker for other rules!
                print(
                    f"Rule different than `greedy`. Checker for `{rule}` not implemented yet."
                )
        else:
            print("There is no selected field!")

    def check_fields(self):
        def validate_fields(data, fields_order, field_name):
            # Check for missing obligatory fields
            missing_fields = [
                field
                for field, props in fields_order.items()
                if props.get("obligatory") and field not in data
            ]
            if missing_fields:
                type = f"missing {field_name} obligatory field"
                details = f"missing fields: {missing_fields}"
                self.add_error(type, details)

            # Check for not known fields
            not_known_fields = [item for item in data if item not in fields_order]
            if not_known_fields:
                type = f"not known {field_name} fields"
                details = f"{field_name} contains not known fields: {not_known_fields}."
                self.add_error(type, details)

            # Check if fields in correct order
            fields_order_keys = list(
                fields_order.keys()
            )  # Get the ordered list of keys
            data_order = [
                item for item in data if item in fields_order_keys
            ]  # Filter data keys

            # Check if the relative order in data matches the expected order
            expected_order_index = 0
            for field in data_order:
                # Find the index of the current field in the expected order
                while (
                    expected_order_index < len(fields_order_keys)
                    and fields_order_keys[expected_order_index] != field
                ):
                    expected_order_index += 1

                # If the field is not found in the expected order, report an error
                if expected_order_index >= len(fields_order_keys):
                    # longterm we want to keep all files in the same order, but
                    # ATM its not crucial
                    type = f"wrong {field_name} fields order"
                    details = f"{field_name} wrong fields order: {data_order}."
                    self.add_error(type, details)
                    break

            # Validate each field
            for field, value in data.items():
                if field not in fields_order:
                    continue  # Skip fields not in the order list

                field_rules = fields_order[field]
                expected_type = field_rules["datatype"]
                checker = field_rules.get("checker")
                nullable = field_rules.get("nullable")

                # Handle nullable fields
                if not value:
                    if not nullable:
                        type = f"invalid {field_name} field value"
                        details = f"{field_name} field '{field}' cannot be None."
                        self.add_error(type, details)
                    continue

                # Attempt to cast to expected type
                try:
                    value = expected_type(value)
                except (ValueError, TypeError):
                    type = f"incorrect {field_name} field datatype"
                    details = (
                        f"{field_name} field '{field}' has incorrect datatype. "
                        f"Expected {expected_type.__name__}, found {type(value).__name__}."
                    )
                    self.add_error(type, details)
                    continue

                # Apply custom checker if defined
                if checker:
                    check_result = checker(value) if callable(checker) else True
                    if check_result is not True:  # Validation failed
                        details = (
                            check_result  # Use checker-provided message if available
                            if isinstance(check_result, str)
                            else f"{field_name} field '{field}' failed validation with value: {value}."
                        )
                        type = f"invalid {field_name} field value"
                        self.add_error(type, details)

        # Check meta fields
        validate_fields(self.meta, flds.META_FIELDS_ORDER, "meta")

        self.validate_date_range(self.meta)

        # Check projects fields
        first_project = next(iter(self.projects.values()), {})
        validate_fields(
            first_project,
            flds.PROJECTS_FIELDS_ORDER,
            "projects",
        )

        # Check votes fields
        first_vote = next(iter(self.votes.values()), {})
        # voter_id filed is checked during loading pb file. But maybe would be nice
        # to load name of column and later on check if correct one
        first_vote = {"voter_id": "placeholder", **first_vote}
        validate_fields(first_vote, flds.VOTES_FIELDS_ORDER, "votes")

    def validate_date_range(self, meta):

        def parse_date(date_str):
            # Convert date string to a comparable format.
            # - YYYY -> "YYYY-01-01"
            # - DD.MM.YYYY -> "YYYY-MM-DD"

            if re.match(r"^\d{4}$", date_str):  # Year-only format
                return f"{date_str}-01-01"
            if re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_str):  # Full date format
                day, month, year = map(int, date_str.split("."))
                return f"{year:04d}-{month:02d}-{day:02d}"

        parsed_begin = parse_date(meta["date_begin"])
        parsed_end = parse_date(meta["date_end"])

        if parsed_begin and parsed_end:
            if parsed_begin > parsed_end:
                type = f"date range missmatch"
                details = (
                    f"date end ({parsed_end}) earlier than start ({parsed_begin})!"
                )
                self.add_error(type, details)

    def run_checks(self):
        self.check_if_commas_in_floats()
        self.check_budgets()
        self.check_number_of_votes()
        self.check_number_of_projects()
        self.check_vote_length()
        # TODO check min/max points
        self.check_votes_and_scores()
        self.verify_selected()
        self.check_fields()

    def process_files(self, files: List[Union[str, bytes]]):
        """
        Process a list of file paths or raw content.
        """
        for identifier, file_or_content in enumerate(files, start=1):
            self.file_results = {}
            if os.path.isfile(file_or_content):
                # Input is a file path
                identifier = os.path.splitext(os.path.basename(file_or_content))[0]
                print(f"Processing file: `{identifier}`...")
                with open(file_or_content, "r", encoding="utf-8") as file:
                    file_or_content = file.read()
            lines = file_or_content.split("\n")

            (
                self.meta,
                self.projects,
                self.votes,
                self.votes_in_projects,
                self.scores_in_projects,
            ) = parse_pb_lines(lines)

            # do file checks
            self.check_empty_lines(lines)

            # do section checks
            self.run_checks()

            if not self.file_results:
                self.results[identifier] = "File looks correct!"
                self.results["metadata"]["valid"] += 1

            else:
                self.results[identifier] = self.file_results
                self.results["metadata"]["invalid"] += 1

            self.results["metadata"]["processed"] += 1

        return self.results
