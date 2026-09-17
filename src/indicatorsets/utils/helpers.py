"""Small, dependency-free helpers used across the indicatorsets utils package."""

import random
from collections import defaultdict
from datetime import datetime as dtime

from epiweeks import Week


def list_to_dict(lst):
    result = {}
    for item in lst:
        key, value = item.split(":")
        if key in result:
            if isinstance(result[key], list):
                result[key].append(value)
            else:
                result[key] = [result[key], value]
        else:
            result[key] = [value]
    return result


def generate_random_color():
    """
    Generate a random color in hexadecimal format.
    """
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))


def get_epiweek(start_date, end_date):
    start_date = dtime.strptime(start_date, "%Y-%m-%d")
    start_date = Week.fromdate(start_date)
    start_date = f"{start_date.year}{start_date.week if start_date.week >= 10 else '0' + str(start_date.week)}"
    end_date = dtime.strptime(end_date, "%Y-%m-%d")
    end_date = Week.fromdate(end_date)
    end_date = f"{end_date.year}{end_date.week if end_date.week >= 10 else '0' + str(end_date.week)}"
    return [start_date, end_date]


def group_by_property(list_of_dicts, property):
    """Groups a list of dictionaries by a specified property.

    Args:
        list_of_dicts: A list of dictionaries.
        property: The property to group by.

    Returns:
        A dictionary where keys are the unique values of the property,
        and values are lists of dictionaries with that property value.
    """
    grouped_dict = defaultdict(list)
    for item in list_of_dicts:
        grouped_dict[item[property]].append(item)
    return dict(grouped_dict)
