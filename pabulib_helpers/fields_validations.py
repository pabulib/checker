import re

import pycountry

VOTE_TYPES = ["ordinal", "approval", "cumulative", "choose-1"]
RULES = [
    "greedy",
    "greedy-no-skip",
    "greedy-threshold",
    "greedy-exclusive",
    "greedy-custom",
    "equalshares",
    "equalshares/add1",
    "unknown",
]


def date_format(value):
    """
    Validate that a date string matches either 'YYYY' or 'DD.MM.YYYY' format.
    Returns True if valid, otherwise False.
    """
    if re.match(r"^\d{4}$", value) or re.match(r"^\d{2}\.\d{2}\.\d{4}$", value):
        return True
    return False


def currency_code(value, *args):
    """
    Validate that the currency code is in ISO 4217 format (three-letter code).
    Returns True if valid, otherwise an error message.
    """
    if pycountry.currencies.get(alpha_3=value) is None:
        return f"wrong currency ISO 4217 format code: {value}"
    return True


def language_code(value, *args):
    """
    Validate that the language code is in ISO 639-1 format (two-letter code).
    Returns True if valid, otherwise an error message.
    """
    if pycountry.languages.get(alpha_2=value) is None:
        return f"wrong language ISO 639-1 format code: {value}"
    return True


def if_list(value, *args):
    """
    Validate that the value is a list.
    Returns True if valid, otherwise an error message.
    """
    if not isinstance(value, list):
        return f"Expected a list, but found {type(value).__name__}."
    return True


def country_name(value, *args):
    """
    Validate that the value is a valid country name or in the allowed custom list.
    """
    custom_countries = ["Worldwide"]
    if value in custom_countries:
        return True
    try:
        if pycountry.countries.lookup(value):
            return True
    except LookupError:
        return f"Value '{value}' is not a valid country name."


def age_value(value, *args):
    """
    Validate that age is either an integer or a string representing an age bucket.

    The value comes in as a string from the file, so we need to check if it's:
    - A numeric string that can be converted to int (e.g., "27", "0", "65")
    - An age bucket string (e.g., "40-59", "18-25", "0-12")

    Returns True if valid, otherwise an error message.
    """
    # If value is already a string (from file), validate it
    if isinstance(value, str):
        # First try: is it a valid integer string?
        try:
            age_int = int(value)
            # Valid integer age
            return True
        except ValueError:
            # Not a simple integer, check if it's an age bucket
            pass

        # Second try: check for age bucket format like "40-59"
        age_bucket_pattern = r"^\d+-\d+$"
        if re.match(age_bucket_pattern, value):
            parts = value.split("-")
            if len(parts) == 2:
                try:
                    start_age = int(parts[0])
                    end_age = int(parts[1])
                    if start_age <= end_age:
                        return True
                    return f"Invalid age bucket '{value}': start age must be <= end age"
                except ValueError:
                    return f"Invalid age bucket '{value}': ages must be numeric"

        return f"Invalid age format '{value}'. Expected an integer or age bucket format like '40-59'"

    # If it's already an int (shouldn't happen from file, but handle it)
    if isinstance(value, int):
        return True

    return f"Invalid age type. Expected int or str, got {type(value).__name__}"
