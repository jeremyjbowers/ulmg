# ABOUTME: Shared test data for season schedule tests: the league's sixteen teams.
# ABOUTME: Creates real Team rows in the league's four divisions, as they exist in production.

from ulmg import models

LEAGUE_TEAMS = {
    "Rickey": [
        ("ATL", "Atlanta", "Crackers"),
        ("CAR", "Carolina", "Coyotes"),
        ("DCM", "DC", "Metropolitans"),
        ("PIT", "Pittsburgh", "Pirates"),
    ],
    "Fernandez": [
        ("CLE", "Cleveland", "Clementes"),
        ("DET", "Detroit", "Voyageurs"),
        ("KCB", "Kansas City", "Beefsteaks"),
        ("LOU", "Louisville", "Sluggers"),
    ],
    "Ringen": [
        ("ABQ", "Albuquerque", "Redbirds"),
        ("ADK", "Adirondack", "Ash"),
        ("CHI", "Chicago", "Scofflaws"),
        ("HCH", "Hub City", "Hawks"),
    ],
    "Orzol": [
        ("CIN", "Cincinnati", "Reds"),
        ("LNG", "Long Island", "Ducks"),
        ("NYH", "New York", "Highlanders"),
        ("PEN", "Peninsula", "Pressmen"),
    ],
}


def create_league_teams():
    teams = []
    for division, rows in LEAGUE_TEAMS.items():
        for abbreviation, city, nickname in rows:
            teams.append(
                models.Team.objects.create(
                    abbreviation=abbreviation,
                    city=city,
                    nickname=nickname,
                    division=division,
                )
            )
    return teams
