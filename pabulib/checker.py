import math
import os
import re
import unicodedata
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
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

    # Valid rule values for project selection algorithms
    VALID_RULES = {
        "greedy",
        "greedy-no-skip",
        "greedy-threshold",
        "greedy-exclusive",
        "greedy-custom",
        "equalshares",
        "equalshares-comparison",
        "equalshares/add1",
        "equalshares/add1-comparison",
        "unknown",
    }
    SENTINEL_PROJECT_COST = 999999999
    EQUALSHARES_COMPARISON_MODE = "satisfaction"

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

    def _get_default_value_for_type(self, datatype):
        """
        Get the default value for a given datatype.

        Args:
            datatype: The Python type (str, int, float, list)

        Returns:
            The default value for that type
        """
        default_values = {
            str: "",
            int: 0,
            float: 0.0,
            list: [],
        }
        return default_values.get(datatype, "")

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

    def _split_list_field(self, value) -> List[str]:
        """Return a comma-separated field as a stripped list without empty items."""
        if value in (None, ""):
            return []
        return [item.strip() for item in str(value).split(",") if item.strip()]

    def _parse_numeric(self, value):
        """Parse numeric values stored as strings, including comma decimals."""
        if value in (None, ""):
            raise ValueError("empty numeric value")
        return float(str(value).replace(",", ".").strip())

    def _normalize_text_key(self, value: str) -> str:
        """Normalize labels to detect case/whitespace/diacritic-only differences."""
        ascii_value = (
            unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        )
        return re.sub(r"\s+", " ", ascii_value.strip().lower())

    def _normalize_filename_key(self, value: str) -> str:
        """Normalize file labels before comparing filename conventions."""
        normalized = self._normalize_text_key(value).replace(" ", "_")
        return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")

    def _parse_date_value(self, date_str):
        """Parse a supported date string to a datetime.date instance."""
        try:
            if re.match(r"^\d{4}$", date_str):
                return datetime.strptime(date_str, "%Y").date()
            if re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_str):
                return datetime.strptime(date_str, "%d.%m.%Y").date()
        except ValueError:
            return None
        return None

    def _build_approval_approvers(self):
        """Map each project to the voters that approve it."""
        approvers = {project_id: [] for project_id in self.projects}
        for voter_id, vote_data in self.votes.items():
            for project_id in self._split_list_field(vote_data.get("vote", "")):
                if project_id in approvers:
                    approvers[project_id].append(voter_id)
        return approvers

    def _break_equalshares_ties(self, choices, cost, approvers):
        """Break MES ties by lower cost and then higher approval count."""
        remaining = list(choices)
        best_cost = min(cost[project_id] for project_id in remaining)
        remaining = [
            project_id for project_id in remaining if cost[project_id] == best_cost
        ]
        best_approval_count = max(len(approvers[project_id]) for project_id in remaining)
        return [
            project_id
            for project_id in remaining
            if len(approvers[project_id]) == best_approval_count
        ]

    def _equal_shares_fixed_budget(self, projects, cost, approvers, total_budget):
        """Compute approval-based MES winners for a fixed artificial budget."""
        voters = list(self.votes.keys())
        if not voters:
            return []

        voter_budget = {
            voter_id: Fraction(total_budget, len(voters)) for voter_id in voters
        }
        remaining = {
            project_id: len(approvers[project_id])
            for project_id in projects
            if cost[project_id] > 0 and approvers[project_id]
        }
        winners = []

        while True:
            best = []
            best_eff_vote_count = Fraction(0, 1)
            remaining_sorted = sorted(
                remaining, key=lambda project_id: remaining[project_id], reverse=True
            )
            for project_id in remaining_sorted:
                previous_eff_vote_count = remaining[project_id]
                if previous_eff_vote_count < best_eff_vote_count:
                    break

                money_behind_now = sum(
                    voter_budget[voter_id] for voter_id in approvers[project_id]
                )
                if money_behind_now < cost[project_id]:
                    del remaining[project_id]
                    continue

                sorted_approvers = sorted(
                    approvers[project_id], key=lambda voter_id: voter_budget[voter_id]
                )
                paid_so_far = Fraction(0, 1)
                denominator = len(sorted_approvers)

                for voter_id in sorted_approvers:
                    max_payment = Fraction(cost[project_id] - paid_so_far, denominator)
                    eff_vote_count = Fraction(cost[project_id], 1) / max_payment
                    if max_payment > voter_budget[voter_id]:
                        paid_so_far += voter_budget[voter_id]
                        denominator -= 1
                    else:
                        remaining[project_id] = eff_vote_count
                        if eff_vote_count > best_eff_vote_count:
                            best_eff_vote_count = eff_vote_count
                            best = [project_id]
                        elif eff_vote_count == best_eff_vote_count:
                            best.append(project_id)
                        break

            if not best:
                break

            best = self._break_equalshares_ties(best, cost, approvers)
            if len(best) > 1:
                raise ValueError(
                    f"Equal Shares tie-breaking failed for projects {best}."
                )

            winner = best[0]
            winners.append(winner)
            del remaining[winner]

            max_payment = Fraction(cost[winner], 1) / best_eff_vote_count
            for voter_id in approvers[winner]:
                if voter_budget[voter_id] > max_payment:
                    voter_budget[voter_id] -= max_payment
                else:
                    voter_budget[voter_id] = Fraction(0, 1)

        return winners

    def _compute_equalshares_winners(self, add1=False):
        """Compute winners for equalshares and equalshares/add1."""
        voters = list(self.votes.keys())
        if not voters:
            return []

        projects = list(self.projects.keys())
        cost = {
            project_id: int(math.floor(self._parse_numeric(project_data["cost"])))
            for project_id, project_data in self.projects.items()
        }
        approvers = self._build_approval_approvers()
        total_budget = int(math.floor(self._parse_numeric(self.meta["budget"])))

        winners = self._equal_shares_fixed_budget(
            projects, cost, approvers, total_budget
        )
        if not add1:
            return winners

        artificial_budget = (total_budget // len(voters)) * len(voters)
        current_cost = sum(cost[project_id] for project_id in winners)

        while True:
            next_budget = artificial_budget + len(voters)
            next_winners = self._equal_shares_fixed_budget(
                projects, cost, approvers, next_budget
            )
            next_cost = sum(cost[project_id] for project_id in next_winners)
            if next_cost <= total_budget:
                artificial_budget = next_budget
                winners = next_winners
                current_cost = next_cost
            else:
                break

        return winners

    def _compute_utilitarian_completion_winners(self, cost, approvers, already_winners=None):
        """Greedy/utilitarian completion used by the Equal Shares comparison step."""
        winners = list(already_winners or [])
        winner_set = set(winners)
        current_cost = sum(cost[project_id] for project_id in winners)
        total_budget = int(math.floor(self._parse_numeric(self.meta["budget"])))

        sorted_projects = sorted(
            self.projects.keys(),
            key=lambda project_id: len(approvers[project_id]),
            reverse=True,
        )
        for project_id in sorted_projects:
            if project_id in winner_set:
                continue
            if current_cost + cost[project_id] > total_budget:
                continue
            winners.append(project_id)
            winner_set.add(project_id)
            current_cost += cost[project_id]

        return winners

    def _apply_equalshares_comparison_step(
        self, winners, cost, approvers, comparison_mode=None
    ):
        """Apply the comparison step between Equal Shares and greedy completion."""
        comparison_mode = comparison_mode or self.EQUALSHARES_COMPARISON_MODE
        voters = list(self.votes.keys())
        greedy = self._compute_utilitarian_completion_winners(
            cost, approvers, already_winners=[]
        )

        prefers_mes = 0
        prefers_greedy = 0

        if comparison_mode == "satisfaction":
            mes_satisfaction = defaultdict(int)
            greedy_satisfaction = defaultdict(int)
            for candidate in winners:
                for voter_id in approvers[candidate]:
                    mes_satisfaction[voter_id] += 1
            for candidate in greedy:
                for voter_id in approvers[candidate]:
                    greedy_satisfaction[voter_id] += 1

            for voter_id in voters:
                if mes_satisfaction[voter_id] > greedy_satisfaction[voter_id]:
                    prefers_mes += 1
                elif greedy_satisfaction[voter_id] > mes_satisfaction[voter_id]:
                    prefers_greedy += 1
        elif comparison_mode == "exclusionRatio":
            mes_covered = set()
            greedy_covered = set()
            for candidate in winners:
                mes_covered.update(approvers[candidate])
            for candidate in greedy:
                greedy_covered.update(approvers[candidate])

            for voter_id in voters:
                if voter_id in mes_covered and voter_id not in greedy_covered:
                    prefers_mes += 1
                elif voter_id in greedy_covered and voter_id not in mes_covered:
                    prefers_greedy += 1
        else:
            raise ValueError(
                f"Unsupported Equal Shares comparison mode: {comparison_mode}"
            )

        if prefers_greedy > prefers_mes:
            return greedy
        return winners

    def verify_equalshares_selected(self, add1=False, comparison_step=False) -> None:
        """Validate project selection according to the Method of Equal Shares."""
        if self.meta.get("vote_type") != "approval":
            self.add_error(
                "equalshares unsupported vote_type",
                f"Rule '{self.meta.get('rule')}' currently supports only approval ballots in the checker.",
                level="warnings",
            )
            return

        cost = {
            project_id: int(math.floor(self._parse_numeric(project_data["cost"])))
            for project_id, project_data in self.projects.items()
        }
        approvers = self._build_approval_approvers()
        computed_winners = self._compute_equalshares_winners(add1=add1)
        if comparison_step:
            computed_winners = self._apply_equalshares_comparison_step(
                computed_winners, cost, approvers
            )
        computed_winners = set(computed_winners)
        selected_winners = {
            project_id
            for project_id, project_data in self.projects.items()
            if int(project_data.get("selected", 0) or 0) == 1
        }

        should_be_selected = computed_winners.difference(selected_winners)
        shouldnt_be_selected = selected_winners.difference(computed_winners)
        if should_be_selected or shouldnt_be_selected:
            error_type = f"{self.meta.get('rule')} rule not followed"
            parts = []
            if should_be_selected:
                parts.append(
                    f"Projects not selected but should be: {', '.join(sorted(should_be_selected))}"
                )
            if shouldnt_be_selected:
                parts.append(
                    f"Projects selected but shouldn't be: {', '.join(sorted(shouldnt_be_selected))}"
                )
            details = ". ".join(parts)
            self.add_error(error_type, details)

    def check_parsing_markers(self) -> None:
        """Promote parser-level structural diagnostics into checker results."""
        for message in self.meta.get("__parse_errors__", []):
            self.add_error("file structure error", message)
        for message in self.meta.get("__parse_warnings__", []):
            self.add_error("file structure warning", message, level="warnings")

    def check_empty_lines(self, lines: List[str]) -> None:
        """
        Remove empty lines from the file and count how many were removed.

        Args:
            lines (List[str]): List of file lines.
        """
        # Check for trailing empty line (allowed) and remove it first
        if lines and lines[-1].strip() == "":
            lines.pop()

        # Count empty lines after removing the trailing one (these are not allowed)
        empty_count = sum(1 for line in lines if line.strip() == "")

        # Remove all empty lines in place
        lines[:] = [line for line in lines if line.strip() != ""]

        # Add to error report if empty lines were removed
        if empty_count > 0:
            self.add_error(
                "empty lines removed",
                f"Removed {empty_count} empty lines from the file.",
                level="warnings",
            )

    def check_if_commas_in_floats(self) -> None:
        """
        Check if there are commas in float values and correct them if found.
        """
        error_type = "comma in float!"

        # Handle budget field - ensure it's a string before checking for commas
        budget_value = str(self.meta["budget"])
        if "," in budget_value:
            self.add_error(error_type, "in budget")
            # replace it to continue with other checks
            self.meta["budget"] = budget_value.replace(",", ".")

        if self.meta.get("max_sum_cost"):
            max_sum_cost_value = str(self.meta["max_sum_cost"])
            if "," in max_sum_cost_value:
                self.add_error(error_type, "in max_sum_cost")
                # replace it to continue with other checks
                self.meta["max_sum_cost"] = max_sum_cost_value.replace(",", ".")

        for project_id, project_data in self.projects.items():
            cost = project_data["cost"]
            if not isinstance(cost, int) and "," in str(cost):
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
        # Handle budget field - convert to string first, then to float for calculations
        budget_str = str(self.meta["budget"]).replace(",", ".")

        # Handle empty budget values
        try:
            budget_available = math.floor(float(budget_str)) if budget_str else 0
        except (ValueError, TypeError):
            budget_available = 0

        all_projects = []

        for project_id, project_data in self.projects.items():
            selected_field = project_data.get("selected")
            project_cost = int(math.floor(self._parse_numeric(project_data["cost"])))
            all_projects_cost += project_cost

            if selected_field and int(selected_field) == 1:
                if project_cost == self.SENTINEL_PROJECT_COST:
                    self.add_error(
                        "selected sentinel-cost project",
                        f"project `{project_id}` is marked as selected even though its sentinel cost `{project_cost}` indicates it should be excluded from implementation.",
                    )
                all_projects.append([project_id, project_cost, project_data["name"]])
                budget_spent += project_cost

            if project_cost == 0:
                self.add_error(
                    "project with no cost", f"project: `{project_id}` has no cost!"
                )
            elif project_cost > budget_available:
                # A cost of 999999999 is a sentinel value used to artificially exclude
                # a project from greedy selection (e.g. when a project was withdrawn
                # after voting). Treat it as a warning rather than an error.
                if project_cost == self.SENTINEL_PROJECT_COST:
                    self.add_error(
                        "single project exceeded whole budget",
                        f"project `{project_id}` exceeds the whole budget (cost: `{project_cost}` vs budget: `{budget_available}`), but this sentinel value is intentional and is reported as a warning",
                        level="warnings",
                    )
                else:
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

        # Get the rule to determine how to handle unused budget
        rule = self.meta.get("rule", "")

        # This check simulates a greedy fill of the remaining budget based on
        # vote totals. That is meaningful only for greedy-style rules.
        # For Equal Shares variants, leftover budget does not imply that an
        # unselected project "should" be funded, so the warning would be
        # misleading.
        if rule not in (
            "greedy",
            "greedy-threshold",
            "greedy-exclusive",
            "greedy-custom",
            "greedy-no-skip",
        ):
            return

        # Skip unused budget check for greedy-no-skip - unused budget is expected
        if rule == "greedy-no-skip":
            return

        # Get unselected projects that are above threshold
        unselected_projects = []
        for project_id, project_data in self.projects.items():
            selected_field = project_data.get("selected")
            if selected_field and int(selected_field) == 0:
                project_cost = int(math.floor(self._parse_numeric(project_data["cost"])))
                # Skip if project is below threshold
                if self.threshold > 0:
                    project_score = float(project_data.get(self.results_field, 0))
                    if project_score <= self.threshold:
                        continue  # Not eligible → skip

                unselected_projects.append(
                    (
                        project_id,
                        project_cost,
                        float(project_data.get(self.results_field, 0)),
                    )
                )

        # Sort by votes/score (descending) to prioritize best projects
        unselected_projects.sort(key=lambda x: x[2], reverse=True)

        # Try to fund projects in order of priority, checking remaining budget
        current_remaining = budget_remaining
        fundable_projects = []
        for project_id, project_cost, project_score in unselected_projects:
            if project_cost <= current_remaining:
                fundable_projects.append(project_id)
                # Subtract cost from remaining budget for next iteration
                current_remaining -= project_cost

        # Add message for fundable projects based on rule type
        if fundable_projects:
            projects_str = ", ".join(map(str, fundable_projects))
            message = f"projects {projects_str} can be funded but are not selected"

            # Determine level and message based on rule
            if rule in ("greedy", "greedy-threshold"):
                # For standard greedy, unused budget is an error
                level = "errors"
            elif rule in ("greedy-exclusive", "greedy-custom"):
                # For other greedy variants, it's a warning with explanation
                level = "warnings"
                message += " (note: unused budget can be expected with non-standard greedy variants)"
            else:
                # For non-greedy rules, it's a warning
                level = "warnings"

            self.add_error(
                "unused budget",
                message,
                level=level,
            )

    def check_number_of_votes(self) -> None:
        """
        Compare the number of votes from META and VOTES sections, log discrepancies.
        """
        meta_votes = self.meta["num_votes"]
        actual_votes_count = len(self.votes)

        # Check if num_votes field is missing or empty
        if not meta_votes or str(meta_votes).strip() == "":
            self.add_error(
                "missing num_votes field",
                f"num_votes field is missing or empty in META section, but found {actual_votes_count} votes in file",
            )
            return

        # Handle invalid values by treating them as 0
        try:
            meta_votes_int = int(meta_votes)
        except (ValueError, TypeError):
            self.add_error(
                "invalid num_votes field",
                f"num_votes field has invalid value: `{meta_votes}`, expected integer, but found {actual_votes_count} votes in file",
            )
            return

        # Compare the numbers if both are valid
        if meta_votes_int != actual_votes_count:
            self.add_error(
                "different number of votes",
                f"votes number in META: `{meta_votes}` vs counted from file: `{actual_votes_count}`",
            )

    def check_number_of_projects(self) -> None:
        """
        Compare the number of projects from META and PROJECTS sections, log discrepancies.
        """
        meta_projects = self.meta["num_projects"]
        actual_projects_count = len(self.projects)

        # Handle empty or invalid values by treating them as 0
        try:
            meta_projects_int = int(meta_projects) if meta_projects else 0
        except (ValueError, TypeError):
            meta_projects_int = 0

        # If meta_projects is 0 (default value or empty), it likely means the field was missing or empty
        # We still want to report the discrepancy but allow processing to continue
        if meta_projects_int != actual_projects_count:
            self.add_error(
                "different number of projects",
                f"projects number in meta: `{meta_projects}` vs counted from file: `{actual_projects_count}`",
            )

    def check_duplicated_votes(self) -> None:
        """
        Check for duplicated votes within each voter's submission.

        Iterates through the votes for each voter and identifies if any voter has
        submitted duplicate project IDs in their vote list.
        """
        for voter, vote_data in self.votes.items():
            votes = self._split_list_field(vote_data["vote"])
            if len(votes) > len(set(votes)):
                error_type = "vote with duplicated projects"
                details = f"duplicated projects in a vote: Voter ID: `{voter}`, vote: `{votes}`."
                self.add_error(error_type, details)

    def check_votes_for_invalid_projects(self) -> None:
        """
        Check if votes contain project IDs that don't exist in the PROJECTS section.

        Iterates through all votes and verifies that each project ID in the vote
        corresponds to an actual project in the projects list.
        """
        valid_project_ids = set(self.projects.keys())

        for voter, vote_data in self.votes.items():
            project_ids = self._split_list_field(vote_data["vote"])
            for project_id in project_ids:
                if project_id and project_id not in valid_project_ids:
                    error_type = "vote for non-existent project"
                    details = f"Voter ID: `{voter}` voted for project `{project_id}` which is not listed in PROJECTS section."
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
            has_vote_with_max_length = False
            total_vote_length = 0
            for voter, vote_data in self.votes.items():
                votes = self._split_list_field(vote_data["vote"])
                voter_votes = len(votes)
                total_vote_length += voter_votes
                if max_length:
                    if voter_votes > int(max_length):
                        error_type = "vote length exceeded"
                        details = f"Voter ID: `{voter}`, max vote length: `{max_length}`, number of voter votes: `{voter_votes}`"
                        self.add_error(error_type, details)
                    elif voter_votes == int(max_length):
                        has_vote_with_max_length = True
                if min_length:
                    if voter_votes < int(min_length):
                        error_type = "vote length too short"
                        details = f"Voter ID: `{voter}`, min vote length: `{min_length}`, number of voter votes: `{voter_votes}`"
                        self.add_error(error_type, details)

            # Suspicious if no one used the full max length
            if max_length and not has_vote_with_max_length:
                error_type = "no_max_length_used"
                details = f"No voter used the full max vote length of `{max_length}`"
                self.add_error(error_type, details, level="warnings")

            if (
                max_length
                and self.votes
                and int(max_length) != 1
                and total_vote_length == len(self.votes)
            ):
                error_type = "average vote length equals one"
                details = (
                    f"Average observed vote length is exactly `1` while max_length is `{max_length}`. "
                    "This may indicate that max_length in META is incorrect or that the effective ballot format was more restrictive."
                )
                self.add_error(error_type, details, level="warnings")

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
                self.add_error(error_type, details, level="warnings")
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
                self.add_error(error_type, details)

    def check_votes_and_scores(self) -> None:
        """
        Validate the presence and correctness of votes and scores in the PROJECTS section.

        Ensure that at least one of votes or scores is present. If votes or scores
        are present, validate their consistency with the respective counts.
        """
        if not any([self.votes_in_projects, self.scores_in_projects]):
            error_type = "No votes or score counted in PROJECTS section"
            details = (
                "There should be at least one field (recommended for data completeness)"
            )
            self.add_error(error_type, details, level="warnings")
        if self.votes_in_projects:
            self.check_if_correct_votes_number()
        if self.scores_in_projects:
            self.check_if_correct_scores_number()

    def check_vote_type_constraints(self) -> None:
        """Validate vote-type-specific field requirements and ballot semantics."""
        vote_type = self.meta.get("vote_type")
        if not vote_type:
            return

        requires_points = vote_type in {"cumulative", "scoring"}
        forbids_points = vote_type in {"approval", "choose-1"}
        incompatible_meta_fields = {
            "approval": {"min_points", "max_points", "min_sum_points", "max_sum_points", "default_score"},
            "choose-1": {"points", "min_points", "max_points", "min_sum_points", "max_sum_points", "default_score"},
        }

        for field_name in incompatible_meta_fields.get(vote_type, set()):
            if field_name in self.meta and str(self.meta.get(field_name, "")).strip() != "":
                self.add_error(
                    "incompatible meta field for vote_type",
                    f"Field '{field_name}' should not be used with vote_type '{vote_type}'.",
                    level="warnings",
                )

        for voter_id, vote_data in self.votes.items():
            projects = self._split_list_field(vote_data.get("vote", ""))
            points_raw = vote_data.get("points", "")
            has_points = "points" in vote_data and str(points_raw).strip() != ""

            if requires_points and not has_points:
                self.add_error(
                    "missing points for vote_type",
                    f"Voter ID `{voter_id}` is missing the 'points' field required for vote_type '{vote_type}'.",
                )
                continue

            if forbids_points and has_points:
                self.add_error(
                    "unexpected points for vote_type",
                    f"Voter ID `{voter_id}` provides 'points' even though vote_type '{vote_type}' does not use them.",
                )

            if vote_type == "choose-1" and len(projects) != 1:
                self.add_error(
                    "invalid choose-1 vote length",
                    f"Voter ID `{voter_id}` selected {len(projects)} projects, but vote_type 'choose-1' requires exactly one project.",
                )

            if not has_points:
                continue

            points = self._split_list_field(points_raw)
            if len(projects) != len(points):
                self.add_error(
                    "vote/points length mismatch",
                    f"Voter ID `{voter_id}` has {len(projects)} project ids in 'vote' but {len(points)} values in 'points'.",
                )
                continue

            parsed_points = []
            numeric_failure = False
            for point in points:
                try:
                    parsed_points.append(self._parse_numeric(point))
                except ValueError:
                    numeric_failure = True
                    self.add_error(
                        "invalid points value",
                        f"Voter ID `{voter_id}` contains a non-numeric points value `{point}`.",
                    )
                    break
            if numeric_failure:
                continue

            if vote_type == "cumulative" and any(point < 0 for point in parsed_points):
                self.add_error(
                    "negative cumulative points",
                    f"Voter ID `{voter_id}` contains negative points in a cumulative ballot.",
                )

            min_points = self.meta.get("min_points")
            max_points = self.meta.get("max_points")
            if min_points not in (None, ""):
                min_points_value = self._parse_numeric(min_points)
                for point in parsed_points:
                    if point < min_points_value:
                        self.add_error(
                            "points below minimum",
                            f"Voter ID `{voter_id}` contains points below min_points `{min_points}`.",
                        )
                        break
            if max_points not in (None, ""):
                max_points_value = self._parse_numeric(max_points)
                for point in parsed_points:
                    if point > max_points_value:
                        self.add_error(
                            "points above maximum",
                            f"Voter ID `{voter_id}` contains points above max_points `{max_points}`.",
                        )
                        break

            points_sum = sum(parsed_points)
            min_sum_points = self.meta.get("min_sum_points")
            max_sum_points = self.meta.get("max_sum_points")
            if min_sum_points not in (None, "") and points_sum < self._parse_numeric(min_sum_points):
                self.add_error(
                    "points sum below minimum",
                    f"Voter ID `{voter_id}` has total points `{points_sum}` below min_sum_points `{min_sum_points}`.",
                    level="warnings",
                )
            if max_sum_points not in (None, "") and points_sum > self._parse_numeric(max_sum_points):
                self.add_error(
                    "points sum above maximum",
                    f"Voter ID `{voter_id}` has total points `{points_sum}` above max_sum_points `{max_sum_points}`.",
                    level="warnings",
                )

            if vote_type in {"cumulative", "scoring"}:
                if any(
                    parsed_points[idx] < parsed_points[idx + 1]
                    for idx in range(len(parsed_points) - 1)
                ):
                    self.add_error(
                        "vote order not sorted by points",
                        f"Voter ID `{voter_id}` lists projects in 'vote' order that is not non-increasing by points.",
                        level="warnings",
                    )

    def check_approval_cost_constraints(self) -> None:
        """Validate min/max summed project costs for approval ballots."""
        if self.meta.get("vote_type") != "approval":
            return

        min_sum_cost = self.meta.get("min_sum_cost")
        max_sum_cost = self.meta.get("max_sum_cost")
        if min_sum_cost in (None, "") and max_sum_cost in (None, ""):
            return

        for voter_id, vote_data in self.votes.items():
            vote_cost = 0.0
            missing_project = False
            for project_id in self._split_list_field(vote_data.get("vote", "")):
                project = self.projects.get(project_id)
                if not project:
                    missing_project = True
                    break
                try:
                    vote_cost += self._parse_numeric(project.get("cost", ""))
                except ValueError:
                    missing_project = True
                    break
            if missing_project:
                continue

            if min_sum_cost not in (None, "") and vote_cost < self._parse_numeric(min_sum_cost):
                self.add_error(
                    "approval vote cost below minimum",
                    f"Voter ID `{voter_id}` selected projects with total cost `{vote_cost}` below min_sum_cost `{min_sum_cost}`.",
                    level="warnings",
                )
            if max_sum_cost not in (None, "") and vote_cost > self._parse_numeric(max_sum_cost):
                self.add_error(
                    "approval vote cost above maximum",
                    f"Voter ID `{voter_id}` selected projects with total cost `{vote_cost}` above max_sum_cost `{max_sum_cost}`.",
                    level="warnings",
                )

    def check_declared_metadata_domains(self) -> None:
        """Compare declared metadata domains with values observed in the data."""
        comparisons = [
            ("categories", "category", self.projects, True),
            ("neighborhoods", "neighborhood", self.projects, False),
            ("neighborhoods", "neighborhood", self.votes, False),
            ("subdistricts", "district", self.projects, False),
            ("subdistricts", "district", self.votes, False),
        ]

        for meta_field, data_field, records, is_list in comparisons:
            declared = self.meta.get(meta_field)
            if not declared:
                continue
            declared_values = set(self._split_list_field(declared))
            observed_values = set()
            for row in records.values():
                raw_value = row.get(data_field, "")
                if is_list:
                    observed_values.update(self._split_list_field(raw_value))
                elif str(raw_value).strip():
                    observed_values.add(str(raw_value).strip())

            if not observed_values:
                continue

            missing_declared = sorted(declared_values - observed_values)
            missing_observed = sorted(observed_values - declared_values)

            if missing_declared:
                self.add_error(
                    "unused declared metadata values",
                    f"META field '{meta_field}' declares values not used in data: {missing_declared}.",
                    level="warnings",
                )
            if missing_observed:
                self.add_error(
                    "undeclared metadata values used",
                    f"Data uses values for '{data_field}' that are not listed in META field '{meta_field}': {missing_observed}.",
                    level="warnings",
                )

    def check_label_consistency(self) -> None:
        """Detect duplicate labels caused only by normalization differences."""
        inspected_fields = [
            ("projects", self.projects, "category", True),
            ("projects", self.projects, "beneficiaries", True),
            ("projects", self.projects, "district", False),
            ("projects", self.projects, "neighborhood", False),
            ("votes", self.votes, "district", False),
            ("votes", self.votes, "neighborhood", False),
        ]

        for scope_name, records, field_name, is_list in inspected_fields:
            normalized_map = defaultdict(set)
            for record_id, row in records.items():
                raw_values = (
                    self._split_list_field(row.get(field_name, ""))
                    if is_list
                    else ([str(row.get(field_name)).strip()] if str(row.get(field_name, "")).strip() else [])
                )
                if is_list and len(raw_values) != len(set(raw_values)):
                    self.add_error(
                        "duplicate values inside list field",
                        f"{scope_name.title()} record `{record_id}` contains duplicate values in '{field_name}': {raw_values}.",
                        level="warnings",
                    )
                for raw_value in raw_values:
                    normalized_map[self._normalize_text_key(raw_value)].add(raw_value)

            for raw_values in normalized_map.values():
                if len(raw_values) > 1:
                    self.add_error(
                        "inconsistent label normalization",
                        f"{scope_name.title()} field '{field_name}' contains values that differ only by case, spacing, or diacritics: {sorted(raw_values)}.",
                        level="warnings",
                    )

    def check_comment_format(self) -> None:
        """Validate numbered comments and sequential numbering in META.comment."""
        comment = self.meta.get("comment")
        if not comment:
            return
        markers = re.findall(r"#(\d+):", comment)
        if not markers:
            self.add_error(
                "invalid comment numbering",
                "META field 'comment' should use numbered comments such as '#1: ...'.",
            )
            return
        expected_markers = [str(index) for index in range(1, len(markers) + 1)]
        if markers != expected_markers:
            self.add_error(
                "non-sequential comment numbering",
                f"META field 'comment' uses non-sequential numbering: {markers}. Expected {expected_markers}.",
                level="warnings",
            )

    def check_dataset_quality_warnings(self) -> None:
        """Run soft quality checks that do not invalidate the file."""
        self.check_declared_metadata_domains()
        self.check_label_consistency()
        self.check_comment_format()

        coordinates = []
        for project in self.projects.values():
            lat_val = project.get("latitude")
            lon_val = project.get("longitude")
            if lat_val in ("", None) or lon_val in ("", None):
                continue
            parsed_lat = self._parse_coordinate(lat_val, -90.0, 90.0)
            parsed_lon = self._parse_coordinate(lon_val, -180.0, 180.0)
            if parsed_lat is not None and parsed_lon is not None:
                coordinates.append((parsed_lat, parsed_lon))
        if len(coordinates) > 1 and len(set(coordinates)) == 1:
            self.add_error(
                "identical project coordinates",
                "All projects with coordinates share the same latitude/longitude pair. Please verify whether this is intentional.",
                level="warnings",
            )

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
        extra_selected = dict()
        get_rule_projects = True
        for project_id, project_dict in projects.items():
            project_cost = float(project_dict["cost"])
            cost_printable = utils.make_cost_printable(project_cost)
            row = [project_id, project_dict[results], cost_printable]
            if int(project_dict["selected"]) in (1, 2, 3):
                # 2 for projects from the 80% rule, 3 for projects
                # funded from additional reserve funds.
                file_selected[project_id] = row
            if int(project_dict["selected"]) == 3:
                extra_selected[project_id] = row
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

        # Some Poznan files mark additional projects with "3" when reserve
        # funds are later allocated. The extra budget amount is not stored in
        # the file, so we can only verify that these projects are the
        # highest-ranked ones among the projects not already selected by the
        # base Poznan rule above.
        if extra_selected:
            remaining_projects = [
                (project_id, row)
                for project_id, row in projects.items()
                if project_id not in rule_selected
            ]
            expected_extra_ids = [
                project_id
                for project_id, _ in remaining_projects[: len(extra_selected)]
            ]
            for project_id in expected_extra_ids:
                project_cost = float(projects[project_id]["cost"])
                cost_printable = utils.make_cost_printable(project_cost)
                rule_selected[project_id] = [
                    project_id,
                    projects[project_id][results],
                    cost_printable,
                ]
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

    def validate_rule(self, rule: str) -> bool:
        """
        Validate if the rule is one of the known/supported rules.

        Args:
            rule (str): The rule specified in the metadata.

        Returns:
            bool: True if the rule is valid, False otherwise.

        Logs errors/warnings for invalid or unknown rules.
        """
        if rule not in self.VALID_RULES:
            error_type = "unknown rule value"
            details = (
                f"The rule '{rule}' is not recognized. "
                f"Valid rules are: {', '.join(sorted(self.VALID_RULES))}."
            )
            self.add_error(error_type, details)
            return False
        return True

    def verify_greedy_selected(
        self, budget, projects, results, threshold=0, rule_name="greedy"
    ) -> None:
        """
        Validate project selection according to greedy rules, with optional minimum score threshold.

        Ensures that projects are selected in descending order of priority (e.g., votes or scores),
        above a specified threshold, until the budget is exhausted.

        Args:
            budget (float): Available budget for funding projects.
            projects (dict): Dictionary of projects with details such as cost and selection status.
            results (str): Field to use for result comparison (e.g., votes or score).
            threshold (int): Minimum votes/score a project must have to be considered (default is 0).
            rule_name (str): Name of the rule being validated (e.g., "greedy", "greedy-threshold") for error messages.

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

        if should_be_selected or shouldnt_be_selected:
            error_type = f"{rule_name} rule not followed"
            parts = []
            if should_be_selected:
                parts.append(
                    f"Projects not selected but should be: {', '.join(sorted(should_be_selected))}"
                )
            if shouldnt_be_selected:
                parts.append(
                    f"Projects selected but shouldn't be: {', '.join(sorted(shouldnt_be_selected))}"
                )
            details = ". ".join(parts)
            self.add_error(error_type, details)

        if selected_below_threshold:
            error_type = "threshold violation"
            details = f"Projects selected below threshold ({threshold}): {selected_below_threshold}"
            self.add_error(error_type, details)

    def verify_greedy_no_skip_selected(
        self, budget, projects, results, threshold=0
    ) -> None:
        """
        Validate project selection according to greedy-no-skip rules.

        In the greedy-no-skip algorithm, projects are sorted by votes/score (descending),
        and the algorithm selects projects that fit within the budget. However, unlike
        standard greedy, the algorithm STOPS immediately when it encounters the first
        project that does not fit, even if subsequent projects would fit.

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
        greedy_no_skip_winners = dict()
        selected_below_threshold = set()

        # First pass: collect all selected projects
        for project_id, project_dict in projects.items():
            project_score = float(project_dict[results])
            project_cost = float(project_dict["cost"])
            cost_printable = utils.make_cost_printable(project_cost)
            row = [project_id, project_dict[results], cost_printable]

            if int(project_dict["selected"]) == 1:
                selected_projects[project_id] = row
                if project_score < threshold:
                    selected_below_threshold.add(project_id)

        # Second pass: simulate greedy-no-skip to find what should be selected
        for project_id, project_dict in projects.items():
            project_score = float(project_dict[results])
            project_cost = float(project_dict["cost"])

            cost_printable = utils.make_cost_printable(project_cost)
            row = [project_id, project_dict[results], cost_printable]

            # Only consider projects above threshold for greedy-no-skip selection
            if project_score >= threshold:
                if project_cost == self.SENTINEL_PROJECT_COST:
                    # Sentinel costs mark withdrawn/artificially excluded projects.
                    # Skip them without stopping greedy-no-skip.
                    continue
                if budget >= project_cost:
                    greedy_no_skip_winners[project_id] = row
                    budget -= project_cost
                else:
                    # Stop immediately - don't consider any more projects
                    break

        gw_set = set(greedy_no_skip_winners.keys())
        selected_set = set(selected_projects.keys())
        should_be_selected = gw_set.difference(selected_set)
        shouldnt_be_selected = selected_set.difference(gw_set)

        if should_be_selected or shouldnt_be_selected:
            error_type = "greedy-no-skip rule not followed"
            parts = []
            if should_be_selected:
                parts.append(
                    f"Projects not selected but should be: {', '.join(sorted(should_be_selected))}"
                )
            if shouldnt_be_selected:
                parts.append(
                    f"Projects selected but shouldn't be: {', '.join(sorted(shouldnt_be_selected))}"
                )
            details = ". ".join(parts)
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
            budget_str = str(self.meta["budget"]).replace(",", ".")

            # Handle empty budget values
            try:
                budget = float(budget_str) if budget_str else 0.0
            except (ValueError, TypeError):
                budget = 0.0

            rule = self.meta.get("rule", "")

            # Validate the rule value
            if not self.validate_rule(rule):
                return

            # Handle rule-based validation
            if rule == "unknown":
                error_type = "rule validation skipped"
                details = "Rule is 'unknown', so rule compliance cannot be verified."
                self.add_error(error_type, details, level="warnings")
                return

            if rule == "equalshares":
                self.verify_equalshares_selected(add1=False)
                return

            if rule == "equalshares-comparison":
                self.verify_equalshares_selected(add1=False, comparison_step=True)
                return

            if rule == "equalshares/add1":
                self.verify_equalshares_selected(add1=True)
                return

            if rule == "equalshares/add1-comparison":
                self.verify_equalshares_selected(add1=True, comparison_step=True)
                return

            if rule == "greedy":
                # Check if min_project_score_threshold exists - if so, should use greedy-threshold
                if "min_project_score_threshold" in self.meta:
                    error_type = "incorrect rule with threshold"
                    details = (
                        "Rule is 'greedy' but 'min_project_score_threshold' field exists. "
                        "Should use 'greedy-threshold' instead."
                    )
                    self.add_error(error_type, details)
                    return

                self.verify_greedy_selected(
                    budget, projects, self.results_field, self.threshold, "greedy"
                )
                return

            if rule == "greedy-no-skip":
                self.verify_greedy_no_skip_selected(
                    budget, projects, self.results_field, self.threshold
                )
                return

            if rule == "greedy-threshold":
                # Check if min_project_score_threshold field exists
                if "min_project_score_threshold" not in self.meta:
                    error_type = "missing threshold field"
                    details = (
                        "Rule is 'greedy-threshold' but 'min_project_score_threshold' "
                        "field is missing in META section."
                    )
                    self.add_error(error_type, details)
                    return

                # Verify using greedy algorithm with threshold
                self.verify_greedy_selected(
                    budget,
                    projects,
                    self.results_field,
                    self.threshold,
                    "greedy-threshold",
                )
                return

            if rule == "greedy-exclusive":
                # Check using standard greedy, but report as warning if mismatch
                temp_errors = self.error_counters.copy()
                temp_file_results = deepcopy(self.file_results)

                self.verify_greedy_selected(
                    budget, projects, self.results_field, self.threshold, "greedy"
                )

                # Check if greedy validation found errors
                if self.file_results.get("errors", {}).get("greedy rule not followed"):
                    # Capture the error details before deleting
                    greedy_error_details = self.file_results["errors"][
                        "greedy rule not followed"
                    ][1]

                    # Remove the greedy error and replace with warning
                    del self.file_results["errors"]["greedy rule not followed"]

                    error_type = "greedy-exclusive potential mismatch"
                    details = (
                        f"Standard greedy algorithm would select different projects: {greedy_error_details} "
                        "This may be correct for 'greedy-exclusive' if conflicting "
                        "projects are handled by hierarchy rules."
                    )
                    self.add_error(error_type, details, level="warnings")
                return

            if rule == "greedy-custom":
                # Check if comment field exists
                if "comment" not in self.meta or not self.meta["comment"]:
                    error_type = "missing comment for greedy-custom"
                    details = (
                        "Rule is 'greedy-custom' but no 'comment' field found in META section. "
                        "Custom rules should be documented in the comment field."
                    )
                    self.add_error(error_type, details, level="warnings")

                # Special case: Poznań uses greedy-custom
                if self.meta.get("unit") == "Poznań":
                    self.verify_poznan_selected(budget, projects, self.results_field)
                    return

                # For other greedy-custom cases, check using standard greedy
                # but report as warning if mismatch
                temp_errors = self.error_counters.copy()
                temp_file_results = deepcopy(self.file_results)

                self.verify_greedy_selected(
                    budget, projects, self.results_field, self.threshold, "greedy"
                )

                # Check if greedy validation found errors
                if self.file_results.get("errors", {}).get("greedy rule not followed"):
                    # Capture the error details before deleting
                    greedy_error_details = self.file_results["errors"][
                        "greedy rule not followed"
                    ][1]

                    # Remove the greedy error and replace with warning
                    del self.file_results["errors"]["greedy rule not followed"]

                    error_type = "greedy-custom cannot be verified"
                    details = (
                        f"Standard greedy algorithm would select different projects: {greedy_error_details} "
                        "This may be correct for 'greedy-custom' due to special logic. "
                        "Please verify the custom rule implementation manually."
                    )
                    self.add_error(error_type, details, level="warnings")
                return

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

        def normalize_value_for_validation(field, value):
            """
            Normalize selected values before generic datatype validation.

            Project coordinates may be stored with commas as decimal separators.
            """
            if field in {"latitude", "longitude"} and value not in ("", None):
                return str(value).replace(",", ".").strip()
            return value

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
            # Filter out special marker fields for validation
            filtered_data = {
                k: v
                for k, v in data.items()
                if not k.startswith("__")
            }

            # Skip certain fields that are allowed but not part of the official schema
            # key field is automatically generated and should be ignored
            skipped_fields = {"key"}
            filtered_data = {
                k: v for k, v in filtered_data.items() if k not in skipped_fields
            }

            # Check for not known fields
            not_known_fields = [
                item for item in filtered_data if item not in fields_order
            ]
            if field_name == "projects" and "target" in not_known_fields:
                self.add_error(
                    "invalid projects field value",
                    "PROJECTS field 'target' is no longer supported. In April 2026, we renamed the unfortunately named field 'target' to 'beneficiaries'. Please update the header and the corresponding values.",
                )
                not_known_fields = [
                    item for item in not_known_fields if item != "target"
                ]
            if not_known_fields:
                error_type = f"not known {field_name} fields"
                details = f"{field_name} contains not known fields: {not_known_fields}."
                self.add_error(error_type, details)

            # Check field order using only schema-recognized fields.
            # Unknown fields are reported separately and should not create
            # confusing order warnings for fields that are no longer supported.
            fields_order_keys = list(fields_order.keys())
            known_data_keys = [
                field for field in filtered_data.keys() if field in fields_order_keys
            ]
            correct_data_order = sorted(
                known_data_keys,
                key=lambda field: fields_order_keys.index(field),
            )

            if known_data_keys != correct_data_order:
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
                # Skip special marker fields
                if field.startswith("__"):
                    continue

                if field not in fields_order:
                    continue  # Skip fields not in the order list

                field_rules = fields_order[field]
                expected_type = field_rules["datatype"]
                checker = field_rules.get("checker")
                nullable = field_rules.get("nullable")
                obligatory = field_rules.get("obligatory", False)
                value = normalize_value_for_validation(field, value)

                # Check if required field was originally missing from the file
                missing_marker = f"__{field}_was_missing__"
                if obligatory and data.get(missing_marker, False):
                    error_type = f"missing {field_name} field value"
                    details = f"{identifier}{field_name} field '{field}' is required but was missing from the file."
                    self.add_error(error_type, details)
                    continue  # Continue processing with default value

                # Handle nullable fields
                if not value:
                    if not nullable:
                        error_type = f"invalid {field_name} field value"
                        details = f"{identifier}{field_name} field '{field}' cannot be None or empty."
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

        # Conditional meta validations
        try:
            vote_type = self.meta.get("vote_type")
        except Exception:
            vote_type = None
        if vote_type == "cumulative":
            if not self.meta.get("max_sum_points") and self.meta.get(
                "max_sum_points", 0
            ) in ("", 0, None):
                self.add_error(
                    "missing meta field value",
                    "For vote_type 'cumulative', 'max_sum_points' is required.",
                )
        if vote_type == "choose-1":
            declared_min_length = self.meta.get("min_length")
            declared_max_length = self.meta.get("max_length")
            if declared_min_length not in ("", None) and int(declared_min_length) != 1:
                self.add_error(
                    "invalid choose-1 meta constraint",
                    "For vote_type 'choose-1', min_length must be 1.",
                )
            if declared_max_length not in ("", None) and int(declared_max_length) != 1:
                self.add_error(
                    "invalid choose-1 meta constraint",
                    "For vote_type 'choose-1', max_length must be 1.",
                )
        elif self.meta.get("max_length") not in ("", None):
            declared_max_length = int(self.meta.get("max_length"))
            if declared_max_length == 1:
                self.add_error(
                    "choose-1 vote_type suggested",
                    "max_length is 1 but vote_type is not 'choose-1'. This looks like a special case of approval voting and may be better represented as vote_type 'choose-1'.",
                    level="warnings",
                )
        declared_max_length = self.meta.get("max_length")
        declared_num_projects = self.meta.get("num_projects")
        if declared_max_length not in ("", None) and declared_num_projects not in ("", None):
            if int(declared_max_length) > int(declared_num_projects):
                self.add_error(
                    "invalid meta field value",
                    f"max_length `{declared_max_length}` cannot be higher than num_projects `{declared_num_projects}`.",
                )

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
        self.check_project_coordinates()

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

    def _parse_coordinate(self, value, minimum: float, maximum: float):
        """
        Parse and validate a single coordinate value.

        Returns the parsed float when valid, otherwise None.
        """
        normalized = str(value).replace(",", ".").strip()
        try:
            parsed = float(normalized)
        except (TypeError, ValueError):
            return None

        if minimum <= parsed <= maximum:
            return parsed
        return None

    def check_project_coordinates(self) -> None:
        """
        Validate project latitude/longitude presence and ranges.

        If one coordinate is present, the other must be present too.
        Valid ranges are [-90, 90] for latitude and [-180, 180] for longitude.
        """
        for project_id, project_data in self.projects.items():
            lat_val = project_data.get("latitude")
            lon_val = project_data.get("longitude")
            has_lat = lat_val not in ("", None)
            has_lon = lon_val not in ("", None)
            identifier = f"Project ID `{project_id}`: "

            if has_lat != has_lon:
                self.add_error(
                    "invalid projects field value",
                    f"{identifier}projects fields 'latitude' and 'longitude' must either both be provided or both be empty.",
                )
                continue

            if not has_lat:
                continue

            if self._parse_coordinate(lat_val, -90.0, 90.0) is None:
                self.add_error(
                    "invalid projects field value",
                    f"{identifier}projects field 'latitude' has invalid coordinate value: {lat_val}. Expected a number in range [-90, 90].",
                )

            if self._parse_coordinate(lon_val, -180.0, 180.0) is None:
                self.add_error(
                    "invalid projects field value",
                    f"{identifier}projects field 'longitude' has invalid coordinate value: {lon_val}. Expected a number in range [-180, 180].",
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
        raw_begin = meta.get("date_begin", "")
        raw_end = meta.get("date_end", "")

        parsed_begin = self._parse_date_value(raw_begin) if raw_begin else None
        parsed_end = self._parse_date_value(raw_end) if raw_end else None

        if raw_begin and parsed_begin is None:
            self.add_error(
                "invalid meta field value",
                f"Invalid date_begin value '{raw_begin}'. Expected 'YYYY' or a real calendar date in 'DD.MM.YYYY' format.",
            )
        if raw_end and parsed_end is None:
            self.add_error(
                "invalid meta field value",
                f"Invalid date_end value '{raw_end}'. Expected 'YYYY' or a real calendar date in 'DD.MM.YYYY' format.",
            )

        if parsed_begin and parsed_end:
            if parsed_begin > parsed_end:
                error_type = "date range missmatch"
                details = (
                    f"date end ({parsed_end.isoformat()}) earlier than start ({parsed_begin.isoformat()})!"
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
        self.check_parsing_markers()
        self.check_if_commas_in_floats()
        self.check_budgets()
        self.check_number_of_votes()
        self.check_number_of_projects()
        self.check_vote_length()
        self.check_vote_type_constraints()
        self.check_approval_cost_constraints()
        self.check_votes_for_invalid_projects()
        # TODO check min/max points
        self.check_votes_and_scores()
        self.verify_selected()
        self.check_fields()
        self.check_dataset_quality_warnings()

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
            self.error_counters = defaultdict(lambda: 1)
            processing_label = str(identifier)
            source_filename = None

            try:
                if isinstance(file_or_content, str) and os.path.isfile(file_or_content):
                    # Input is a file path that exists
                    identifier = os.path.splitext(os.path.basename(file_or_content))[0]
                    processing_label = identifier
                    source_filename = identifier
                    with open(file_or_content, "r", encoding="utf-8") as file:
                        file_or_content = file.read()
                elif isinstance(file_or_content, str) and (
                    file_or_content.strip().startswith("META")
                    or "\n" in file_or_content
                ):
                    # Input appears to be content (starts with META or has newlines)
                    pass  # file_or_content is already the content
                elif isinstance(file_or_content, str):
                    # Input looks like a file path but doesn't exist
                    identifier = os.path.splitext(os.path.basename(file_or_content))[0]
                    print(f"❌ ERROR: File not found: `{file_or_content}`")
                    self.results[identifier] = {
                        "results": {
                            "errors": {
                                "file not found": {
                                    1: f"File '{file_or_content}' does not exist"
                                }
                            }
                        }
                    }
                    self.results["metadata"]["invalid"] += 1
                    self.results["metadata"]["processed"] += 1
                    continue

                lines = file_or_content.split("\n")

                # Remove empty lines BEFORE parsing (they break CSV parsing)
                self.check_empty_lines(lines)

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
                webpage_name = self.create_webpage_name()
                self.results[identifier]["webpage_name"] = webpage_name
                print(
                    f"Processing file: `{webpage_name}` (source: `{processing_label}`)..."
                )

                # results field, votes or score (points)
                self.results_field = "score" if self.scores_in_projects else "votes"

                # do section checks
                self.run_checks()

                # Always include detailed results (errors and warnings)
                self.results[identifier]["results"] = self.file_results

                # Mark file as valid if there are no errors, even if warnings exist
                if not any([self.file_results.get("errors")]):
                    self.results["metadata"]["valid"] += 1
                else:
                    self.results["metadata"]["invalid"] += 1

                self.results["metadata"]["processed"] += 1

            except Exception as e:
                # Handle any other errors during processing
                print(f"❌ ERROR processing file `{processing_label}`: {e}")
                self.results[identifier] = {
                    "results": {
                        "errors": {
                            "processing error": {1: f"Failed to process file: {str(e)}"}
                        }
                    }
                }
                self.results["metadata"]["invalid"] += 1
                self.results["metadata"]["processed"] += 1

        results_cleaned = self.convert_to_dict(self.results)
        return results_cleaned
