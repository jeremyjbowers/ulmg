# ABOUTME: League-season URLs put the year in the path. A leftover ?season= query redirects there.
# ABOUTME: Pages that omit the year use the league season, which opens on November 1.

from django.shortcuts import redirect

from ulmg import utils


def season_url(*parts, season, tail=()):
    """A path with the year after the resource and before any action, always with a trailing slash."""
    bits = [str(part).strip("/") for part in parts]
    tail_bits = [str(part).strip("/") for part in tail]
    return "/" + "/".join([*bits, str(season), *tail_bits]) + "/"


def resolve_year(request, season):
    """The year in the path, else ?season=, else the league season of today."""
    if season is not None:
        return int(season)
    raw = request.GET.get("season")
    if raw not in (None, ""):
        try:
            return int(raw)
        except ValueError:
            pass
    return utils.league_season()


def bounce(request, *parts, season=None, tail=()):
    """
    Redirect to the canonical path when the year is missing or still a query.
    Returns None when the request is already that path.
    """
    year = resolve_year(request, season)
    target = season_url(*parts, season=year, tail=tail)
    if request.path != target or "season" in request.GET:
        return redirect(target)
    return None
