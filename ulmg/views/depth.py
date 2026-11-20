# ABOUTME: Playing time on the lineup, rotation and bullpen pages: the season's split of plate appearances by position, starts and bullpen innings.
# ABOUTME: Anyone can read it. Only the team's owner and the commissioner can save a spot. The depth-chart address opens the lineups.

from django.shortcuts import get_object_or_404, redirect

from ulmg import depth, models, plans
from ulmg.season_paths import bounce, season_url

# The form field that marks a playing-time post on the lineup, rotation and bullpen pages.
SPOT_ACTION = "spot"


def is_spot_post(request):
    return request.method == "POST" and request.POST.get("action") == SPOT_ACTION


def _amount(post, name, unlimited):
    """A posted number. None when blank, "bad" when it is not a whole number."""
    if unlimited:
        return 0
    raw = (post.get(name) or "").strip()
    if raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return "bad"


def _checked(post, name):
    return post.get(name) in ("on", "true", "1")


def _int(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def posted_edits(post):
    """The rows of one posted spot as depth.SpotEdit, the filed rows first, then the player being added."""
    edits = []
    for raw in post.getlist("assignment"):
        row_id = _int(raw)
        if row_id is None:
            continue
        unlimited = _checked(post, f"unlimited_{row_id}")
        edits.append(
            depth.SpotEdit(
                assignment=row_id,
                player=None,
                amount=_amount(post, f"amount_{row_id}", unlimited),
                unlimited=unlimited,
                remove=_checked(post, f"remove_{row_id}"),
            )
        )
    player_id = _int(post.get("player"))
    if player_id is not None:
        unlimited = _checked(post, "unlimited")
        edits.append(
            depth.SpotEdit(
                assignment=None,
                player=models.Player.objects.filter(pk=player_id).first(),
                amount=_amount(post, "amount", unlimited),
                unlimited=unlimited,
            )
        )
    return edits


def save_spot(team, season, post):
    """Save one posted spot. Returns the errors, empty when it saved."""
    edits = posted_edits(post)
    if any(edit.assignment is None and edit.player is None for edit in edits):
        return ["That player is not on the roster."]
    try:
        depth.save_spot(depth.ensure(team, season), post.get("bucket") or "", edits)
    except depth.DepthError as exc:
        return exc.errors
    return []


def team_depth(request, abbreviation, season=None):
    """The depth chart is filed on the lineup, rotation and bullpen pages. Its address opens the lineups."""
    team = get_object_or_404(models.Team, abbreviation__iexact=abbreviation)
    bounced = bounce(request, "teams", team.abbreviation.lower(), "depth", season=season)
    if bounced:
        return bounced
    return redirect(season_url("teams", team.abbreviation.lower(), "plan", plans.current_half(), season=int(season)))
