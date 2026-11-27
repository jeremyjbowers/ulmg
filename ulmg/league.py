# ABOUTME: Reads the one LeagueSettings row: season, half, and which roster windows are open.
# ABOUTME: A Django setting of the old name still overrides that row, which is how the tests pin a season.
from django.conf import settings

_MISSING = object()

# Names these used to have in the settings file. Defined there, or passed to
# override_settings, they win over the row so a deploy or a test can still pin them.
_SETTINGS_NAMES = {
    "current_season": "CURRENT_SEASON",
    "current_season_type": "CURRENT_SEASON_TYPE",
    "draft_prep_season_type": "DRAFT_PREP_SEASON_TYPE",
    "season_half": "TEAM_SEASON_HALF",
    "stats_display_season_cap": "STATS_DISPLAY_SEASON_CAP",
    "protect_tab": "TEAM_PROTECT_TAB",
    "roster_tab": "TEAM_ROSTER_TAB",
    "roster_staff_only": "TEAM_ROSTER_STAFF_ONLY",
    "live_tab": "TEAM_LIVE_TAB",
    "wishlist_tab": "TEAM_WISHLIST_TAB",
    "mlb_roster_size": "MLB_ROSTER_SIZE",
    "protect_roster_size": "PROTECT_ROSTER_SIZE",
}


def load():
    """The league settings row, created from the field defaults if it is missing."""
    from ulmg.models import LeagueSettings

    return LeagueSettings.load()


def _value(field):
    override = getattr(settings, _SETTINGS_NAMES[field], _MISSING)
    if override is not _MISSING:
        return override
    return getattr(load(), field)


def current_season():
    """The ULMG year. Stat pages step back one year while the season type is offseason."""
    return _value("current_season")


def current_season_type():
    """offseason or midseason."""
    return _value("current_season_type")


def draft_prep_season_type():
    """Open and AA draft prep. Blank follows the current season type."""
    return _value("draft_prep_season_type")


def season_half():
    """1h until the second half of the schedule is open, then 2h."""
    return _value("season_half")


def stats_display_season_cap():
    """Latest calendar year shown on stat pages, or None for no extra cap."""
    return _value("stats_display_season_cap")


def protect_tab():
    """Owners set 40-man protections from their team page."""
    return _value("protect_tab")


def roster_tab():
    """Owners set MLB and AAA rosters from the buttons on their team page."""
    return _value("roster_tab")


def roster_staff_only():
    """While this is on, those roster controls are shown to staff only."""
    return _value("roster_staff_only")


def live_tab():
    return _value("live_tab")


def wishlist_tab():
    return _value("wishlist_tab")


def mlb_roster_size():
    return _value("mlb_roster_size")


def protect_roster_size():
    return _value("protect_roster_size")
