import csv
from io import StringIO
from typing import Dict, List, Tuple

from . import fields as flds


def assign_default_values_for_missing_fields(
    data: Dict, fields_order: Dict, original_data: Dict = None
) -> Dict:
    """
    Assign default values to missing required fields to allow checker to continue processing.

    Args:
        data (Dict): The data dictionary to check and update
        fields_order (Dict): The field definitions with datatype and obligatory flags
        original_data (Dict): The original data before processing to track what was actually missing

    Returns:
        Dict: Updated data dictionary with default values for missing required fields
    """
    default_values = {
        str: "",
        int: 0,
        float: 0.0,
        list: [],
    }

    # Mark fields that were originally missing
    if original_data is None:
        original_data = {}

    for field, props in fields_order.items():
        if props.get("obligatory") and field not in original_data:
            # Assign default value based on datatype
            default_value = default_values.get(props["datatype"], "")
            data[field] = default_value
            # Mark this field as originally missing for validation
            data[f"__{field}_was_missing__"] = True

    return data


def parse_pb_lines(lines: List[str]) -> Tuple[Dict, Dict, Dict, bool, bool]:
    meta, projects, votes = {}, {}, {}
    original_meta, original_projects, original_votes = {}, {}, {}
    section = ""
    header = []

    # Use StringIO to simulate file-like behavior for csv.reader
    reader = csv.reader(StringIO("\n".join(lines)), delimiter=";")

    for row in reader:
        if row:
            if str(row[0]).strip().lower() in ["meta", "projects", "votes"]:
                section = str(row[0]).strip().lower()

                # Only projects and votes sections have headers, meta doesn't
                if section in ["projects", "votes"]:
                    header = next(reader)
                    check_header = header[0].strip().lower()
                    # Validate header for each section
                    if section == "projects" and check_header != "project_id":
                        raise ValueError(
                            f"First value in PROJECTS section is not 'project_id': {check_header}"
                        )
                    if section == "votes" and check_header != "voter_id":
                        raise ValueError(
                            f"First value in VOTES section is not 'voter_id': {check_header}"
                        )
            elif section == "meta":
                original_value = row[1].strip() if len(row) > 1 else ""
                value = original_value if original_value else ""
                meta[row[0]] = value
                original_meta[row[0]] = original_value
            elif section == "projects":
                votes_in_projects = True if "votes" in header else False
                scores_in_projects = True if "score" in header else False
                projects[row[0]] = {"project_id": row[0]}
                original_projects[row[0]] = {"project_id": row[0]}
                for it, key in enumerate(header[1:]):
                    original_value = row[it + 1].strip() if len(row) > it + 1 else ""
                    value = original_value if original_value else ""
                    projects[row[0]][key.strip()] = value
                    original_projects[row[0]][key.strip()] = original_value
            elif section == "votes":
                if votes.get(row[0]):
                    raise RuntimeError(f"Duplicated Voter ID!! {row[0]}")
                votes[row[0]] = {"voter_id": row[0]}  # Add voter_id as a field
                original_votes[row[0]] = {
                    "voter_id": row[0]
                }  # Add to original data too
                for it, key in enumerate(header[1:]):
                    original_value = row[it + 1].strip() if len(row) > it + 1 else ""
                    value = original_value if original_value else ""
                    votes[row[0]][key.strip()] = value
                    original_votes[row[0]][key.strip()] = original_value

    # Assign default values for missing required fields to allow checker to continue
    meta = assign_default_values_for_missing_fields(
        meta, flds.META_FIELDS_ORDER, original_meta
    )

    # For projects, we need to handle each project individually
    if projects:
        # Get the first project to check for missing fields
        first_project_id = next(iter(projects))
        projects[first_project_id] = assign_default_values_for_missing_fields(
            projects[first_project_id],
            flds.PROJECTS_FIELDS_ORDER,
            original_projects[first_project_id],
        )

        # Apply the same structure to all other projects
        for project_id in list(projects.keys())[1:]:
            projects[project_id] = assign_default_values_for_missing_fields(
                projects[project_id],
                flds.PROJECTS_FIELDS_ORDER,
                original_projects[project_id],
            )

    # For votes, handle each vote individually
    for voter_id in votes:
        votes[voter_id] = assign_default_values_for_missing_fields(
            votes[voter_id], flds.VOTES_FIELDS_ORDER, original_votes[voter_id]
        )

    return meta, projects, votes, votes_in_projects, scores_in_projects
