from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter
def cat_color_idx(name, color_map):
    """Return the CSS class index for a category name."""
    if not color_map or not name:
        return 0
    return color_map.get(name, 0)


@register.simple_tag(takes_context=True)
def url_replace(context, key, value):
    """Return query string with one parameter replaced, preserving others."""
    params = context["request"].GET.copy()
    params[key] = value
    return params.urlencode()


@register.filter
def inr(value, decimal_places=2):
    """Format a number as Indian Rupees with ₹ symbol and Indian number grouping.
    e.g. 1234567.50 → ₹12,34,567.50
    """
    try:
        value = Decimal(str(value))
    except (InvalidOperation, TypeError):
        return value

    # Round to desired decimal places
    quantize_str = "0." + "0" * decimal_places if decimal_places > 0 else "0"
    value = value.quantize(Decimal(quantize_str))

    # Split into integer and decimal parts
    str_value = f"{value:.{decimal_places}f}"
    if decimal_places > 0:
        integer_part, decimal_part = str_value.split(".")
    else:
        integer_part, decimal_part = str_value, ""

    # Indian grouping: last 3 digits, then groups of 2
    negative = integer_part.startswith("-")
    if negative:
        integer_part = integer_part[1:]

    if len(integer_part) > 3:
        last3 = integer_part[-3:]
        rest = integer_part[:-3]
        groups = []
        while len(rest) > 2:
            groups.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.append(rest)
        groups.reverse()
        integer_part = ",".join(groups) + "," + last3
    
    formatted = f"₹{'-' if negative else ''}{integer_part}"
    if decimal_places > 0:
        formatted += f".{decimal_part}"
    return formatted
