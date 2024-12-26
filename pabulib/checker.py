from dataclasses import dataclass, field
from helpers import parse_pb_lines
from helpers import Utils
from collections import defaultdict
import math
import os
from typing import List, Union, Dict
import json


@dataclass
class Checker:

    def __post_init__(self):
        self.results = dict() # results of all data
        self.results["metadata"] = dict() # metadata, how many files was processed
        self.results["metadata"]["processed"] = 0
        self.results["metadata"]["valid"] = 0
        self.results["metadata"]["invalid"] = 0
        self.results["summary"] = defaultdict(lambda: 0) # sum of errors across all files
        self.error_counters = defaultdict(lambda: 1)
        self.utils = Utils()

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
            details = f"budget: {self.utils.get_str_with_sep_from(budget_available)}, cost of all projects: {self.utils.get_str_with_sep_from(all_projects_cost)}"
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
                        details = f"project: {project_id} can be funded but it's not selected"
                        self.add_error(type, details)

    def run_checks(self):
        self.check_if_commas_in_floats()
        self.check_budgets()

    def process_files(self, files: List[Union[str, bytes]]):
        """
        Process a list of file paths or raw content.
        """
        for identifier, file_or_content in enumerate(files, start=1):
            self.file_results = {}
            if os.path.isfile(file_or_content):
                # Input is a file path
                identifier = os.path.splitext(os.path.basename(file_or_content))[0]
                with open(file_or_content, "r", encoding="utf-8") as file:
                    file_or_content = file.read()
            lines = file_or_content.split("\n")

            self.meta, self.projects, self.votes, self.votes_in_projects, self.scores_in_projects = parse_pb_lines(lines)

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

            results = json.dumps(self.results, indent=4)
            print(results)



