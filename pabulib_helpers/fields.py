"""
IMPORTANT: If a new custom field is added, it MUST be included in the relevant *_FIELDS_ORDER dictionary.
Otherwise, an error will be raised when processing — especially when saving the `meta` dictionary.

Example usage in Pabulib:
    def sort_meta_fields(self):
        unknown_keys = [key for key in self.meta if key not in flds.META_FIELDS_ORDER]
        if unknown_keys:
            raise ValueError(f"Unknown meta field(s): {unknown_keys}. "
                             f"Did you forget to add them to META_FIELDS_ORDER?")
        self.meta = {
            key: self.meta[key] for key in flds.META_FIELDS_ORDER if key in self.meta
        }

This field configuration is used in the Pabulib data pipeline to:
- Define the order and presence of metadata, project, and vote fields
- Enforce type constraints and custom validations
- Prevent unregistered fields from being silently included

Each field entry may define:
  - `datatype`: expected Python type
  - `obligatory`: whether the field is required
  - `nullable`: whether None is allowed
  - `checker`: custom validation function

Validation logic is imported from `pabulib_helpers.fields_validations`.

Keep this schema updated to avoid data loss or errors during processing.
"""

import pabulib_helpers.fields_validations as validate

META_FIELDS_ORDER = {
    "description": {"datatype": str, "obligatory": True},
    "country": {
        "datatype": str,
        "checker": validate.country_name,
        "obligatory": True,
    },
    "unit": {"datatype": str, "obligatory": True},
    "district": {"datatype": str},
    "subunit": {"datatype": str},
    "instance": {"datatype": str, "obligatory": True},
    "num_projects": {"datatype": int, "obligatory": True},
    "num_votes": {"datatype": int, "obligatory": True},
    "budget": {"datatype": float, "obligatory": True},
    "vote_type": {
        "datatype": str,
        "checker": lambda x: (
            True
            if x in validate.VOTE_TYPES
            else f"invalid vote_type '{x}'. Valid options are: {', '.join(validate.VOTE_TYPES)}"
        ),
        "obligatory": True,
    },
    "rule": {
        "datatype": str,
        "checker": lambda x: (
            True
            if x in validate.RULES
            else f"invalid rule '{x}'. Valid options are: {', '.join(validate.RULES)}"
        ),
        "obligatory": True,
    },
    # change on the webpage that dates are obligatory
    "date_begin": {
        "datatype": str,
        "checker": validate.date_format,
        "obligatory": True,
    },
    "date_end": {"datatype": str, "checker": validate.date_format, "obligatory": True},
    "min_length": {"datatype": int},
    "max_length": {"datatype": int},
    "min_sum_cost": {"datatype": float},
    "max_sum_cost": {"datatype": float},
    "min_points": {"datatype": int},
    "max_points": {"datatype": int},
    "min_sum_points": {"datatype": int},
    "max_sum_points": {"datatype": int},
    "min_project_cost": {"datatype": int},
    "max_project_cost": {"datatype": int},
    "min_project_score_threshold": {"datatype": int},
    "neighborhoods": {"datatype": str},
    "subdistricts": {"datatype": str},
    "categories": {"datatype": str},
    "edition": {"datatype": str},
    "language": {
        "datatype": str,
        "checker": validate.language_code,
    },
    "currency": {
        "datatype": str,
        "checker": validate.currency_code,
    },
    "fully_funded": {
        "datatype": int,
        "checker": lambda x: (
            True
            if x in [1]
            else f"invalid fully_funded value '{x}'. Valid options are: 1"
        ),
    },
    "experimental": {
        "datatype": int,
        "checker": lambda x: (
            True
            if x in [1]
            else f"invalid experimental value '{x}'. Valid options are: 1"
        ),
    },
    "comment": {
        "datatype": str,
        "checker": lambda x: (
            True if x.startswith("#1: ") else "comment should follow the '#1: ' format"
        ),
    },
    "acknowledgments": {"datatype": str},
    # Amsterdam specific fields
    "leftover_budget": {"datatype": str},
    "budget_per_category": {"datatype": list, "checker": validate.if_list},
    "budget_per_neighborhood": {"datatype": list, "checker": validate.if_list},
    "min_length_per_category": {"datatype": int},
    "max_length_per_category": {"datatype": int},
    "min_sum_cost_per_category": {"datatype": list, "checker": validate.if_list},
    "max_sum_cost_per_category": {"datatype": list, "checker": validate.if_list},
}

PROJECTS_FIELDS_ORDER = {
    "project_id": {"datatype": str, "obligatory": True},
    "cost": {"datatype": int, "obligatory": True},
    "votes": {"datatype": int},
    "score": {"datatype": int},
    "name": {"datatype": str},
    "category": {"datatype": list, "checker": validate.if_list, "nullable": True},
    "target": {"datatype": list, "checker": validate.if_list, "nullable": True},
    "selected": {
        "datatype": int,
        "checker": lambda x: (
            True
            if x in [0, 1, 2, 3]
            else f"invalid selected value '{x}'. Valid options are: 0, 1, 2, 3"
        ),
    },
    "neighborhood": {"datatype": str},
    "subunit": {"datatype": str},
    "district": {"datatype": str},
    "description": {"datatype": str},
    "proposer": {"datatype": str},
    "public_id": {"datatype": str},
    "latitude": {"datatype": float, "nullable": True},
    "longitude": {"datatype": float, "nullable": True},
}


VOTES_FIELDS_ORDER = {
    "voter_id": {"datatype": str, "obligatory": True},
    "vote": {"datatype": list, "checker": validate.if_list, "obligatory": True},
    "points": {"datatype": list, "checker": validate.if_list},
    "age": {"datatype": int, "nullable": True},
    "sex": {
        "datatype": str,
        "checker": lambda x: (
            True
            if x in ["M", "F", "O"]
            else f"invalid sex value '{x}'. Valid options are: M, F, O"
        ),
        "nullable": True,
    },
    "voting_method": {
        "datatype": str,
        "checker": lambda x: (
            True
            if x in ["internet", "paper"]
            else f"invalid voting_method '{x}'. Valid options are: internet, paper"
        ),
    },
    "district": {"datatype": str, "nullable": True},
    "neighborhood": {"datatype": str, "nullable": True},
    "education": {"datatype": str, "nullable": True},
    # Zurich specific fields
    "topic_preference_transport": {"datatype": int},
    "topic_preference_culture": {"datatype": int},
    "topic_preference_nature": {"datatype": int},
    "district_preference": {"datatype": str},
    "time_taken_seconds": {"datatype": int},
    "format_easiness": {"datatype": str},
    "format_expressiveness": {"datatype": str},
    "format_rank": {"datatype": str},
}
