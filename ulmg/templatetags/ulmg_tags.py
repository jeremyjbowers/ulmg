from django import template
from decimal import Decimal

register = template.Library()

@register.filter(name='kill_leading_zero')
def kill_leading_zero(value):
    if isinstance(value, Decimal):
        return str(value).replace("0.", ".")
    return value