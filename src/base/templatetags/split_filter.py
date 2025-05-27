from django import template

register = template.Library()


@register.filter(name="split")
def split(value, separator=","):
    """
    Custom template filter to split a string by a given separator.
    Defaults to splitting by comma if no separator is provided.
    """
    if isinstance(value, str):
        return value.split(separator)
    return []
