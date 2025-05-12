import math
import os
import re
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from typing import List, Union

from pabulib_helpers import fields as flds
from pabulib_helpers import parse_pb_lines
from pabulib_helpers import utilities as utils


@dataclass
class Checker:
    """
    A class to validate and check data files for correctness and compliance.

    Attributes:
        results (dict): Stores metadata and results of checks.
        error_counters (defaultdict): Tracks the number of errors by type.
        counted_votes (defaultdict): Tracks vote counts for each project.
        counted_scores (defaultdict): Tracks score counts for each project.
    """

    def __post_init__(self):
        """
        Initialize results and error tracking structures.
        """
        self.results = {
            "metadata": {"processed": 0, "valid": 0, "invalid": 0},
            "summary": defaultdict(lambda: 0),
        }
        self.error_levels = {"errors": {}, "warnings": {}}
        self.error_counters = defaultdict(lambda: 1)
        self.counted_votes = defaultdict(int)
        self.counted_scores = defaultdict(int)

    def add_error(self, error_type: str, details: str, level: str = "errors") -> None:
        """
        Record an error of the given error_type with details.

        Args:
            error_type (str): The type/category of the error.
            details (str): Description of the error.
        """
        if level not in self.error_levels.keys():
            raise RuntimeError(f"Wrong level type!: {level}")
        current_count = self.error_counters[error_type]
        try:
            self.file_results[level][error_type][current_count] = details
        except KeyError:
            self.file_results[level][error_type] = {current_count: details}

        self.error_counters[error_type] += 1
        self.results["summary"][error_type] += 1

    def check_empty_lines(self, lines: List[str]) -> None:
        """
        Check for and report empty lines in the file.

        Args:
            lines (List[str]): List of file lines.
        """
        if lines and lines[-1].strip() == "":
            lines.pop()
        empty_lines = [i for i, line in enumerate(lines, start=1) if line.strip() == ""]
        if empty_lines:
            self.add_error("empty lines", f"contains empty lines at: {empty_lines}")

    def check_if_commas_in_floats(self) -> None:
        """
        Check if there are commas in float values and correct them if found.
        """
        error_type = "comma in float!"
        if "," in self.meta["budget"]:
            self.add_error(error_type, "in budget")
            # replace it to continue with other checks
            self.meta["budget"] = self.meta["budget"].replace(",", ".")

        if self.meta.get("max_sum_cost"):
            if "," in self.meta["max_sum_cost"]:
                self.add_error(error_type, "in max_sum_cost")
                # replace it to continue with other checks
                self.meta["max_sum_cost"] = self.meta["max_sum_cost"].replace(",", ".")

        for project_id, project_data in self.projects.items():
            cost = project_data["cost"]
            if not isinstance(cost, int) and "," in cost:
                self.add_error(
                    error_type, f"in project: `{project_id}`, cost: `{cost}`"
                )
                # replace it to continue with other checks
                self.projects[project_id]["cost"] = str(cost).split(",")[0]

    def check_budgets(self) -> None:
        """
        Validate if budgets and project costs are within limits and consistent.
        """
        budget_spent = 0
        all_projects_cost = 0
        budget_available = math.floor(float(self.meta["budget"].replace(",", ".")))
        all_projects = []

        for project_id, project_data in self.projects.items():
            selected_field = project_data.get("selected")
            project_cost = int(project_data["cost"])
            all_projects_cost += project_cost

            if selected_field and int(selected_field) == 1:
                all_projects.append([project_id, project_cost, project_data["name"]])
                budget_spent += project_cost

            if project_cost == 0:
                self.add_error(
                    "project with no cost", f"project: `{project_id}` has no cost!"
                )
            elif project_cost > budget_available:
                self.add_error(
                    "single project exceeded whole budget",
                    f"project `{project_id}` has exceeded the whole budget! cost: `{project_cost}` vs budget: `{budget_available}`",
                )

        if budget_spent > budget_available:
            self.add_error(
                "budget exceeded",
                f"Budget: `{budget_available}`, cost of selected projects: {budget_spent}",
            )
            # for project in all_projects:
            #     print(project)
        if self.meta.get("fully_funded"):
            if int(self.meta["fully_funded"]) == 1:
                if budget_available < all_projects_cost:
                    self.add_error(
                        "wrong fully_funded flag",
                        f"budget: {utils.get_str_with_sep_from(budget_available)}, lower than cost of all projects: {utils.get_str_with_sep_from(all_projects_cost)}",
                    )
                return
            else:
                self.add_error(
                    "fully_funded flag different than 1!",
                    f"value: {self.meta['fully_funded']}",
                )
                return
        # IF NOT FULLY FUNDED FLAG, THEN CHECK IF budget not exceeded:
        if budget_available >= all_projects_cost:
            self.add_error(
                "all projects funded",
                f"budget: {utils.get_str_with_sep_from(budget_available)}, cost of all projects: {utils.get_str_with_sep_from(all_projects_cost)}",
            )
        # check if unused budget
        budget_remaining = budget_available - budget_spent
        for project_id, project_data in self.projects.items():
            selected_field = project_data.get("selected")
            if selected_field and int(selected_field) == 0:
                project_cost = int(project_data["cost"])
                # Skip "unused budget" error if project is below threshold
                if self.threshold > 0:
                    project_score = float(project_data.get(self.results_field, 0))
                    if project_score <= self.threshold:
                        continue  # Not eligible → skip

                if project_cost <= budget_remaining:
                    self.add_error(
                        "unused budget",
                        f"project: {project_id} can be funded but it's not selected",
                    )

    def check_number_of_votes(self) -> None:
        """
        Compare the number of votes from META and VOTES sections, log discrepancies.
        """
        meta_votes = self.meta["num_votes"]
        if int(meta_votes) != len(self.votes):
            self.add_error(
                "different number of votes",
                f"votes number in META: `{meta_votes}` vs counted from file: `{len(self.votes)}`",
            )

    def check_number_of_projects(self) -> None:
        """
        Compare the number of projects from META and PROJECTS sections, log discrepancies.
        """
        meta_projects = self.meta["num_projects"]
        if int(meta_projects) != len(self.projects):
            self.add_error(
                "different number of projects",
                f"projects number in meta: `{meta_projects}` vs counted from file: `{len(self.projects)}`",
            )

    def check_duplicated_votes(self) -> None:
        """
        Check for duplicated votes within each voter's submission.

        Iterates through the votes for each voter and identifies if any voter has
        submitted duplicate project IDs in their vote list.
        """
        for voter, vote_data in self.votes.items():
            votes = vote_data["vote"].split(",")
            if len(votes) > len(set(votes)):
                error_type = "vote with duplicated projects"
                details = f"duplicated projects in a vote: Voter ID: `{voter}`, vote: `{votes}`."
                self.add_error(error_type, details)

    def check_vote_length(self) -> None:
        """
        Validate the number of votes cast by each voter against allowed limits.

        Checks if the number of votes by a voter exceeds the maximum allowed
        or falls below the minimum required. Reports discrepancies.

        Uses meta fields to determine the applicable minimum and maximum limits.
        """
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
                        error_type = "vote length exceeded"
                        details = f"Voter ID: `{voter}`, max vote length: `{max_length}`, number of voter votes: `{voter_votes}`"
                        self.add_error(error_type, details)
                if min_length:
                    if voter_votes < int(min_length):
                        error_type = "vote length too short"
                        details = f"Voter ID: `{voter}`, min vote length: `{min_length}`, number of voter votes: `{voter_votes}`"
                        self.add_error(error_type, details)

    def check_if_correct_votes_number(self) -> None:
        """
        Check if number of votes in PROJECTS is the same as counted.

        Count the number of votes from the VOTES section (given as a dictionary)
        and check if it matches the number of votes listed in the PROJECTS section.

        Log discrepancies such as differing counts, votes for unlisted projects,
        or projects without any votes.
        """
        self.counted_votes = utils.count_votes_per_project(self.votes)
        for project_id, project_info in self.projects.items():
            votes = project_info.get("votes", 0) or 0
            if int(votes) == 0:
                error_type = "project with no votes"
                details = f"It's possible, that this project was not approved for voting! Project: {project_id}"
                self.add_error(error_type, details)
            counted_votes = self.counted_votes[project_id]
            if not int(project_info.get("votes", 0) or 0) == int(counted_votes or 0):
                error_type = f"different values in votes"
                file_votes = project_info.get("votes", 0)
                details = f"project: `{project_id}` file votes (in PROJECTS section): `{file_votes}` vs counted: {counted_votes}"
                self.add_error(error_type, details)

        for project_id, project_votes in self.counted_votes.items():
            if (
                not self.projects.get(project_id)
                or "votes" not in self.projects[project_id]
            ):
                error_type = f"different values in votes"
                details = f"project: `{project_id}` file votes (in PROJECTS section): `0` vs counted: {project_votes}"
                self.add_error(error_type, details)

    def check_if_correct_scores_number(self) -> None:
        """
        Check if score numbers given in PROJECTS match the counted scores.

        Count scores for each project and compare with the scores listed
        in the PROJECTS section. Log discrepancies for inconsistent data.
        """
        self.counted_scores = utils.count_points_per_project(self.votes)
        for project_id, project_info in self.projects.items():
            counted_votes = self.counted_scores[project_id]

            if not int(project_info.get("score", 0) or 0) == int(counted_votes or 0):
                error_type = f"different values in scores"
                file_score = project_info.get("score", 0)
                details = f"project: `{project_id}` file scores (in PROJECTS section): `{file_score}` vs counted: {counted_votes}"
                self.add_error(error_type, details)

        for project_id, project_votes in self.counted_scores.items():
            if not self.projects.get(project_id):
                error_type = f"different values in scores"
                details = f"project: `{project_id}` file scores (in PROJECTS section): `0` vs counted: {project_votes}"

    def check_votes_and_scores(self) -> None:
        """
        Validate the presence and correctness of votes and scores in the PROJECTS section.

        Ensure that at least one of votes or scores is present. If votes or scores
        are present, validate their consistency with the respective counts.
        """
        if not any([self.votes_in_projects, self.scores_in_projects]):
            error_type = "No votes or score counted in PROJECTS section"
            details = "There should be at least one field"
            self.add_error(error_type, details)
        if self.votes_in_projects:
            self.check_if_correct_votes_number()
        if self.scores_in_projects:
            self.check_if_correct_scores_number()

    def verify_poznan_selected(self, budget, projects, results) -> None:
        """
        Validate project selection according to Poznań rules.

        Ensures that selected projects adhere to the available budget and
        that projects costing up to 80% of the remaining budget are considered.

        Args:
            budget (float): Available budget for funding projects.
            projects (dict): Dictionary of projects with details such as cost and selection status.
            results (str): Field to use for result comparison (e.g., votes or scores).

        Logs discrepancies where:
        - Projects that should be selected are not.
        - Projects that should not be selected are selected.
        """
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
            error_type = "poznan rule not followed"
            details = f"Projects not selected but should be: {should_be_selected}"
            self.add_error(error_type, details, level="warnings")

        shouldnt_be_selected = file_selected_set.difference(rule_selected_set)
        if shouldnt_be_selected:
            error_type = "poznan rule not followed"
            details = f"Projects selected but should not: {shouldnt_be_selected}"
            self.add_error(error_type, details)

    def verify_greedy_selected(self, budget, projects, results, threshold=0) -> None:
        """
        Validate project selection according to greedy rules, with optional minimum score threshold.

        Ensures that projects are selected in descending order of priority (e.g., votes or scores),
        above a specified threshold, until the budget is exhausted.

        Args:
            budget (float): Available budget for funding projects.
            projects (dict): Dictionary of projects with details such as cost and selection status.
            results (str): Field to use for result comparison (e.g., votes or score).
            threshold (int): Minimum votes/score a project must have to be considered (default is 0).

        Logs discrepancies where:
        - Projects that should be selected are not.
        - Projects that should not be selected are selected.
        - Projects below the threshold are selected.
        """
        selected_projects = dict()
        greedy_winners = dict()
        selected_below_threshold = set()

        for project_id, project_dict in projects.items():
            project_score = float(project_dict[results])
            project_cost = float(project_dict["cost"])

            cost_printable = utils.make_cost_printable(project_cost)
            row = [project_id, project_dict[results], cost_printable]

            if int(project_dict["selected"]) == 1:
                selected_projects[project_id] = row
                if project_score < threshold:
                    selected_below_threshold.add(project_id)

            # Only consider projects above threshold for greedy selection
            if project_score >= threshold and budget >= project_cost:
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
            error_type = "greedy rule not followed"
            details = f"Projects not selected but should be: {should_be_selected or ''}, and selected but shouldn't: {shouldnt_be_selected or ''}"
            self.add_error(error_type, details)

        if selected_below_threshold:
            error_type = "threshold violation"
            details = f"Projects selected below threshold ({threshold}): {selected_below_threshold}"
            self.add_error(error_type, details)

    def verify_selected(self) -> None:
        """
        Verify project selection based on the specified rules.

        Determines the selection rule (e.g., Poznań, greedy) and validates the
        selected projects against the available budget and rule-specific criteria.

        Args:
            None

        Logs discrepancies where:
        - Projects that should be selected are not.
        - Projects that should not be selected are selected.
        - No `selected` field is present in project data.
        """
        selected_field = next(iter(self.projects.values())).get("selected")
        if selected_field:
            projects = utils.sort_projects_by_results(self.projects)
            budget = float(self.meta["budget"].replace(",", "."))
            rule = self.meta["rule"]
            if self.meta["unit"] == "Poznań":
                self.verify_poznan_selected(budget, projects, self.results_field)
            elif rule == "greedy":
                self.verify_greedy_selected(
                    budget, projects, self.results_field, self.threshold
                )
            else:
                # TODO add checker for other rules!
                print(
                    f"Rule different than `greedy`. Checker for `{rule}` not implemented yet."
                )
        else:
            print("There is no selected field!")

    def check_fields(self) -> None:
        """
        Validate the structure and values of metadata, project, and vote fields.

        This method ensures the following:
        - Required fields are present and not null.
        - Unknown fields are identified and reported.
        - Field values adhere to expected types and constraints.
        - Fields appear in the correct order as specified.

        Logs errors for any discrepancies found in metadata, project, or vote fields.
        """

        def validate_fields_and_order(data, fields_order, field_name):
            """
            Validate field presence, order, and unknown fields for a given data structure.

            Args:
                data (dict): The data structure to validate (e.g., meta, project, vote).
                fields_order (dict): The expected order and rules for the fields.
                field_name (str): A label for the data structure being validated.

            Logs:
                Errors for missing required fields, unknown fields, and incorrect field order.
            """
            # Check for missing obligatory fields
            missing_fields = [
                field
                for field, props in fields_order.items()
                if props.get("obligatory") and field not in data
            ]
            if missing_fields:
                error_type = f"missing {field_name} obligatory field"
                details = f"missing fields: {missing_fields}"
                self.add_error(error_type, details)

            # Check for not known fields
            not_known_fields = [item for item in data if item not in fields_order]
            if not_known_fields:
                error_type = f"not known {field_name} fields"
                details = f"{field_name} contains not known fields: {not_known_fields}."
                self.add_error(error_type, details)

            # Check if fields in correct order

            # Extract the correct order of fields from fields_order
            fields_order_keys = list(fields_order.keys())

            # Get the current order of keys from the data dictionary
            data_keys = list(data.keys())

            # Generate the correct order based on fields_order_keys
            correct_data_order = sorted(
                data_keys,
                key=lambda field: (
                    fields_order_keys.index(field)
                    if field in fields_order_keys
                    else float("inf")
                ),
            )

            # Check if the order is correct
            if data_keys != correct_data_order:
                # Report a warning with the correct order
                error_type = f"wrong {field_name} fields order"
                details = f"correct order should be: {correct_data_order}"
                self.add_error(error_type, details, level="warnings")

        def validate_fields_values(data, fields_order, field_name, identifier=""):
            """
            Validate field values for adherence to type and custom rules.

            Args:
                data (dict): The data structure to validate.
                fields_order (dict): The expected types and constraints for the fields.
                field_name (str): A label for the data structure being validated.
                identifier (str): Additional context for error messages (e.g., project ID).

            Logs:
                Errors for missing, incorrect, or invalid field values.
            """

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
                        error_type = f"invalid {field_name} field value"
                        details = (
                            f"{identifier}{field_name} field '{field}' cannot be None."
                        )
                        self.add_error(error_type, details)
                    continue

                # Attempt to cast to expected type
                try:
                    value = expected_type(value)
                except (ValueError, TypeError):
                    error_type = f"incorrect {field_name} field datatype"
                    details = (
                        f"{identifier}{field_name} field '{field}' has incorrect datatype. "
                        f"Expected {expected_type.__name__}, found {type(value).__name__}."
                    )
                    self.add_error(error_type, details)
                    continue

                # Apply custom checker if defined
                if checker:
                    check_result = checker(value) if callable(checker) else True
                    if check_result is not True:  # Validation failed
                        details = (
                            check_result  # Use checker-provided message if available
                            if isinstance(check_result, str)
                            else f"{identifier}{field_name} field '{field}' failed validation with value: {value}."
                        )
                        error_type = f"invalid {field_name} field value"
                        self.add_error(error_type, details)

        # Check meta fields
        validate_fields_and_order(self.meta, flds.META_FIELDS_ORDER, "meta")
        validate_fields_values(self.meta, flds.META_FIELDS_ORDER, "meta")

        self.validate_date_range(self.meta)

        # Check projects fields
        # Check field order and missing fields for the first project only
        first_project = next(iter(self.projects.values()), {})
        validate_fields_and_order(first_project, flds.PROJECTS_FIELDS_ORDER, "projects")

        # Validate all project entries
        for project_id, project_data in self.projects.items():
            identifier = f"Project ID `{project_id}`: "
            validate_fields_values(
                project_data, flds.PROJECTS_FIELDS_ORDER, "projects", identifier
            )

        # Check votes fields
        first_vote = next(iter(self.votes.values()), {})
        # TODO voter_id filed is checked during loading pb file. But maybe would be nice
        # to load name of column and later on check if correct one
        first_vote = {"voter_id": "placeholder", **first_vote}
        validate_fields_and_order(first_vote, flds.VOTES_FIELDS_ORDER, "votes")

        # Validate all vote entries
        for vote_id, vote_data in self.votes.items():
            identifier = f"Voter ID `{vote_id}`: "
            validate_fields_values(
                vote_data, flds.VOTES_FIELDS_ORDER, "votes", identifier
            )

    def validate_date_range(self, meta) -> None:
        """
        Validate the date range in metadata.

        Ensures the start date is earlier than or equal to the end date.

        Args:
            meta (dict): Metadata containing the date range to validate.

        Logs:
            Errors for invalid date formats or a mismatched date range.
        """

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
                error_type = "date range missmatch"
                details = (
                    f"date end ({parsed_end}) earlier than start ({parsed_begin})!"
                )
                self.add_error(error_type, details)

    # Convert the defaultdict (nested) to regular dictionaries
    def convert_to_dict(self, obj):
        """
        Recursively convert a nested defaultdict structure into regular dictionaries.

        Args:
            obj: The object to convert, which can be a defaultdict, dict, or any other type.

        Returns:
            A regular dictionary representation of the input object.

        Example:
            If the input is a nested defaultdict, the output will be the same structure
            but with all defaultdicts replaced by regular dicts.
        """
        if isinstance(obj, defaultdict):
            return {k: self.convert_to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, dict):
            return {k: self.convert_to_dict(v) for k, v in obj.items()}
        else:
            return obj

    def run_checks(self):
        """
        Execute all validation and integrity checks sequentially.

        This method runs a series of validation checks to ensure the consistency
        and correctness of the data being processed. The checks performed include:
        - Validating and correcting float values with commas.
        - Ensuring budgets and project costs align with constraints.
        - Comparing the number of votes and projects against metadata.
        - Checking the length of votes for compliance with min/max rules.
        - Validating votes and scores across sections.
        - Verifying project selection based on defined rules.
        - Checking the structure and values of fields in metadata, projects, and votes.

        Logs errors for any inconsistencies or violations detected during the checks.
        """
        self.check_if_commas_in_floats()
        self.check_budgets()
        self.check_number_of_votes()
        self.check_number_of_projects()
        self.check_vote_length()
        # TODO check min/max points
        self.check_votes_and_scores()
        self.verify_selected()
        self.check_fields()

    def create_webpage_name(self) -> str:
        """
        Generate a webpage name based on metadata fields.

        Combines the country, unit, and instance fields from the metadata to create a unique identifier
        for the webpage. If a subunit field is present, it is appended to the name.

        Returns:
            str: The generated webpage name.

        Example:
            For metadata with country="US", unit="California", instance="2024", and subunit="BayArea",
            the output will be "US_California_2024_BayArea".
        """
        country = self.meta["country"]
        unit = self.meta["unit"]
        instance = self.meta["instance"]
        webpage_name = f"{country}_{unit}_{instance}"
        if self.meta.get("subunit"):
            webpage_name += f"_{self.meta['subunit']}"
        return webpage_name

    def process_files(self, files: List[Union[str, bytes]]) -> dict:
        """
        Process a list of file paths or raw content.

        This method iterates over the provided files, parsing their content and performing
        validations and checks. Each file is either read as raw content or from a file path,
        and its results are stored in the `results` attribute.

        Args:
            files (List[Union[str, bytes]]): A list of file paths or raw content to process.

        Returns:
            dict: A dictionary containing the cleaned and processed results, with metadata.

        Workflow:
        1. Parse file content into sections (meta, projects, votes, etc.).
        2. Validate the structure and content of the parsed data.
        3. Record errors and metadata for each processed file.
        4. Convert results into a standardized dictionary format.

        Example Usage:
            files = ["path/to/file1", "raw content of file2"]
            results = self.process_files(files)
        """
        for identifier, file_or_content in enumerate(files, start=1):
            self.file_results = deepcopy(self.error_levels)
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

            # Minimum number of votes / score for project to be eligible for implementation
            self.threshold = int(self.meta.get("min_project_score_threshold", 0))

            self.results[identifier] = dict()
            self.results[identifier]["webpage_name"] = self.create_webpage_name()

            # do file checks
            self.check_empty_lines(lines)

            # results field, votes or score (points)
            self.results_field = "score" if self.scores_in_projects else "votes"

            # do section checks
            self.run_checks()

            if not any(
                [self.file_results.get("errors"), self.file_results.get("warnings")]
            ):
                self.results[identifier]["results"] = "File looks correct!"
                self.results["metadata"]["valid"] += 1

            else:
                self.results[identifier]["results"] = self.file_results
                self.results["metadata"]["invalid"] += 1

            self.results["metadata"]["processed"] += 1

        results_cleaned = self.convert_to_dict(self.results)
        return results_cleaned
