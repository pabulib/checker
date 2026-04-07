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
    votes_in_projects = False
    scores_in_projects = False
    parse_errors = []
    parse_warnings = []
    section_sequence = []
    seen_sections = set()

    # Use StringIO to simulate file-like behavior for csv.reader
    rows = list(csv.reader(StringIO("\n".join(lines)), delimiter=";"))
    row_index = 0

    while row_index < len(rows):
        row = rows[row_index]
        row_index += 1

        if not row:
            continue

        first_cell = str(row[0]).strip()
        normalized_first_cell = first_cell.lower()

        if normalized_first_cell in ["meta", "projects", "votes"]:
            section = normalized_first_cell
            section_sequence.append(section)

            if section in seen_sections:
                parse_errors.append(f"Duplicated section '{first_cell}'.")
            else:
                seen_sections.add(section)

            if section == "meta":
                if row_index >= len(rows):
                    parse_errors.append("META section is missing the required header 'key;value'.")
                    continue

                next_row = rows[row_index]
                normalized_header = [cell.strip().lower() for cell in next_row]
                if len(normalized_header) >= 2 and normalized_header[0] == "key" and normalized_header[1] == "value":
                    row_index += 1
                else:
                    parse_errors.append("META section must start with the header 'key;value'.")
                continue

            if row_index >= len(rows):
                parse_errors.append(
                    f"{section.upper()} section is missing its column header row."
                )
                header = []
                continue

            raw_header = rows[row_index]
            row_index += 1
            header = [cell.strip() for cell in raw_header]
            normalized_header = [cell.lower() for cell in header]

            if len(normalized_header) != len(set(normalized_header)):
                parse_errors.append(
                    f"{section.upper()} section contains duplicated column names: {header}."
                )

            if section == "projects":
                if not normalized_header or normalized_header[0] != "project_id":
                    parse_errors.append(
                        f"PROJECTS section must start with 'project_id', found: {header[0] if header else ''}."
                    )
                votes_in_projects = "votes" in normalized_header
                scores_in_projects = "score" in normalized_header
            if section == "votes" and (
                not normalized_header or normalized_header[0] != "voter_id"
            ):
                parse_errors.append(
                    f"VOTES section must start with 'voter_id', found: {header[0] if header else ''}."
                )
            continue

        if not section:
            parse_errors.append(
                f"Found data row before any section header: {row}."
            )
            continue

        if section == "meta":
            key = first_cell
            if not key:
                parse_errors.append("META contains an empty key.")
                continue
            if key in meta:
                parse_errors.append(f"Duplicated META key '{key}'.")
            original_value = row[1].strip() if len(row) > 1 else ""
            value = original_value if original_value else ""
            meta[key] = value
            original_meta[key] = original_value
            if len(row) > 2:
                parse_warnings.append(
                    f"META row for key '{key}' has extra columns; only the first value is used."
                )
            continue

        if not header:
            parse_errors.append(
                f"{section.upper()} section contains data rows before a valid header."
            )
            continue

        if len(row) > len(header):
            parse_warnings.append(
                f"{section.upper()} row '{first_cell}' has extra columns; trailing values are ignored."
            )

        if section == "projects":
            project_id = first_cell
            if not project_id:
                parse_errors.append("PROJECTS contains an empty project_id.")
                continue
            if project_id in projects:
                parse_errors.append(f"Duplicated project_id '{project_id}'.")
                continue
            projects[project_id] = {"project_id": project_id}
            original_projects[project_id] = {"project_id": project_id}
            for it, key in enumerate(header[1:]):
                original_value = row[it + 1].strip() if len(row) > it + 1 else ""
                value = original_value if original_value else ""
                projects[project_id][key.strip()] = value
                original_projects[project_id][key.strip()] = original_value
            continue

        if section == "votes":
            voter_id = first_cell
            if not voter_id:
                parse_errors.append("VOTES contains an empty voter_id.")
                continue
            if votes.get(voter_id):
                parse_errors.append(f"Duplicated voter_id '{voter_id}'.")
                continue
            votes[voter_id] = {"voter_id": voter_id}
            original_votes[voter_id] = {"voter_id": voter_id}
            for it, key in enumerate(header[1:]):
                original_value = row[it + 1].strip() if len(row) > it + 1 else ""
                value = original_value if original_value else ""
                votes[voter_id][key.strip()] = value
                original_votes[voter_id][key.strip()] = original_value

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

    expected_sections = ["meta", "projects", "votes"]
    missing_sections = [
        expected_section
        for expected_section in expected_sections
        if expected_section not in seen_sections
    ]
    if missing_sections:
        parse_errors.append(
            f"Missing required sections: {', '.join(section.upper() for section in missing_sections)}."
        )
    unique_sequence = []
    for section_name in section_sequence:
        if section_name not in unique_sequence:
            unique_sequence.append(section_name)
    if unique_sequence and unique_sequence != [section for section in expected_sections if section in unique_sequence]:
        parse_errors.append(
            "Sections must appear in the order META, PROJECTS, VOTES."
        )

    if parse_errors:
        meta["__parse_errors__"] = parse_errors
    if parse_warnings:
        meta["__parse_warnings__"] = parse_warnings

    return meta, projects, votes, votes_in_projects, scores_in_projects
