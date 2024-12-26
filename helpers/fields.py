"""NOTE: IF NEW CUSTOM FIELD, IT HAS TO BE ADDED HERE.
Otherwise they will be skipped when saving."""

import helpers.fields_validations as validate

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
        "checker": lambda x: x in validate.VOTE_TYPES,
        "obligatory": True,
    },
    "rule": {
        "datatype": str,
        "checker": lambda x: x in validate.RULES,
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
    "fully_funded": {"datatype": int, "checker": lambda x: x in [1]},
    "experimental": {"datatype": int, "checker": lambda x: x in [1]},
    "comment": {"datatype": str, "checker": lambda x: x.startswith("#1: ")},
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
    "selected": {"datatype": int, "checker": lambda x: x in [0, 1, 2]},
    "neighborhood": {"datatype": str},
    "subunit": {"datatype": str},
    "district": {"datatype": str},
    "description": {"datatype": str},
    "proposer": {"datatype": str},
    "public_id": {"datatype": str},
    "longitude": {"datatype": float, "nullable": True},
    "latitude": {"datatype": float, "nullable": True},
}


VOTES_FIELDS_ORDER = {
    "voter_id": {"datatype": str, "obligatory": True},
    "vote": {"datatype": list, "checker": validate.if_list, "obligatory": True},
    "points": {"datatype": list, "checker": validate.if_list},
    "age": {"datatype": int, "nullable": True},
    "sex": {
        "datatype": str,
        "checker": lambda x: x in ["M", "F"],
    },
    "voting_method": {
        "datatype": str,
        "checker": lambda x: x in ["internet", "paper"],
    },
    "district": {"datatype": str, "nullable": True},
    "neighborhood": {"datatype": str},
    "education": {"datatype": str},
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
