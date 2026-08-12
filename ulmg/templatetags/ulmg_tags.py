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


@register.filter(name="ops_plus")
def ops_plus(hit_stats):
    """Return OPS+ from FanGraphs hit_stats, or derive it from OBP+ and SLG+."""
    if not hit_stats:
        return None

    if isinstance(hit_stats, dict):
        if hit_stats.get("ops_plus") not in (None, ""):
            return hit_stats["ops_plus"]

        obp_plus = hit_stats.get("obp_plus")
        slg_plus = hit_stats.get("slg_plus")
        if obp_plus not in (None, "") and slg_plus not in (None, ""):
            return float(obp_plus) + float(slg_plus) - 100

    return None


@register.filter(name="commafy")
def commafy(n):
    r = []
    for i, c in enumerate(reversed(str(n))):
        if i and (not (i % 3)):
            r.insert(0, ",")
        r.insert(0, c)
    return "".join(r)
