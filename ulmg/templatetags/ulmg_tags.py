from django import template
from decimal import Decimal

register = template.Library()

@register.filter(name="percents_to_hundreds")
def percents_to_hundreds(value):
    value = float(value)
    return value * 100.0


@register.filter(name="kill_leading_zero")
def kill_leading_zero(value):
    if isinstance(value, Decimal):
        return str(value).replace("0.", ".")

    if isinstance(value, float):
        return str(value).replace("0.", ".")

    if isinstance(value, str):
        return value.replace("0.", ".")

    return value


@register.filter(name="commafy")
def commafy(n):
    r = []
    for i, c in enumerate(reversed(str(n))):
        if i and (not (i % 3)):
            r.insert(0, ",")
        r.insert(0, c)
    return "".join(r)
