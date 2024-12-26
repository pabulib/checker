import re

import pycountry

VOTE_TYPES = ["ordinal", "approval", "cumulative", "choose-1"]
RULES = [
    "greedy",
    "unknown",
    "equalshares",
    "equalshares/add1",
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
