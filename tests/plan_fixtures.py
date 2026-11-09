# ABOUTME: Shared test data for half plan tests: a generated season schedule and real 30-man rosters.
# ABOUTME: Builds Team, Player, PlayerStatSeason and Card rows, and files plans through ulmg.plans.

from io import StringIO

from django.core.management import call_command

from ulmg import models, plans
from tests.schedule_fixtures import create_league_teams

SEASON = 2027
CARD_SEASON = SEASON - 1

STARTER_STATS = {"g": 32, "gs": 32, "ip": "190.0", "start_minusip": "190.0"}
RELIEVER_STATS = {"g": 60, "gs": 0, "ip": "65.0", "relief_minusip": "65.0"}
SWINGMAN_STATS = {"g": 40, "gs": 8, "ip": "90.0", "start_minusip": "45.0", "relief_minusip": "45.0"}
HITTER_STATS = {"pa": 600, "ab": 540, "bb": 50, "hbp": 5, "sf": 5}

HITTER_RATES = {
    "k": 0.2, "bb": 0.08, "hbp": 0.01, "single": 0.14, "double": 0.045,
    "triple": 0.004, "hr": 0.03,
}

FIELD_POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]


def create_season():
    """The sixteen league teams and a real generated schedule for SEASON."""
    create_league_teams()
    call_command("generate_schedule", "--season", str(SEASON), "--seed", "21", stdout=StringIO())


def create_pitcher(team, name, throws="R", stats=STARTER_STATS, roster=True, card=True):
    player = models.Player.objects.create(
        name=name, position="P", level="V", team=team, throws=throws, is_ulmg_mlb_roster=roster
    )
    models.PlayerStatSeason.objects.create(
        player=player, season=CARD_SEASON, classification="1-mlb", pitch_stats=dict(stats)
    )
    if card:
        models.Card.objects.create(
            player=player,
            season=CARD_SEASON,
            batters_faced=700,
            pitcher_rates={"k": 0.25, "bb": 0.07, "hbp": 0.01, "h": 0.2, "hr": 0.03},
        )
    return player


def create_hitter(team, name, position="OF", defense=None, roster=True, card=True):
    player = models.Player.objects.create(
        name=name, position=position, level="V", team=team, bats="R", throws="R",
        is_ulmg_mlb_roster=roster,
    )
    models.PlayerStatSeason.objects.create(
        player=player, season=CARD_SEASON, classification="1-mlb", hit_stats=dict(HITTER_STATS)
    )
    if card:
        models.Card.objects.create(
            player=player,
            season=CARD_SEASON,
            plate_appearances=600,
            hitter_rates=dict(HITTER_RATES),
            defense=defense or {},
        )
    return player


class Roster:
    """A team's 30-man: five starters, two relievers, a swingman and ten hitters."""

    def __init__(self, team, throws=("R", "R", "R", "R", "R")):
        abbr = team.abbreviation
        self.team = team
        self.starters = [
            create_pitcher(team, f"{abbr} Starter {i + 1}", throws=hand)
            for i, hand in enumerate(throws)
        ]
        self.relievers = [
            create_pitcher(team, f"{abbr} Reliever {i + 1}", stats=RELIEVER_STATS) for i in range(2)
        ]
        self.swingman = create_pitcher(team, f"{abbr} Swingman", stats=SWINGMAN_STATS)
        self.catcher = create_hitter(team, f"{abbr} Catcher", position="C", defense={"C": 4.0})
        self.fielders = [
            create_hitter(team, f"{abbr} Fielder {position}", defense={position: 1.5})
            for position in FIELD_POSITIONS[1:]
        ]
        self.hitters = [self.catcher] + self.fielders + [create_hitter(team, f"{abbr} Hitter DH")]
        self.bench = [create_hitter(team, f"{abbr} Bench {i + 1}", position="IF") for i in range(2)]

    def lineup(self, hitters=None):
        """Lineup entries in batting order: catcher, the seven fielders, then the DH."""
        hitters = hitters or self.hitters
        positions = FIELD_POSITIONS + ["DH"]
        return [
            {"order": i + 1, "player": player, "position": position}
            for i, (player, position) in enumerate(zip(hitters, positions))
        ]

    def file(self, half=1, rotation=None, lineup_vs_lhp=None, lineup_vs_rhp=None, **kwargs):
        plan = plans.plan_for(self.team, SEASON, half)
        fields = {
            "rotation": rotation if rotation is not None else self.starters,
            "closer": self.relievers[0],
            "setup_l": [],
            "setup_r": [self.relievers[1]],
            "sirp": [],
            "mirp": [self.swingman],
            "bench": self.bench,
            "lineup_vs_lhp": lineup_vs_lhp or self.lineup(),
            "lineup_vs_rhp": lineup_vs_rhp or self.lineup(),
        }
        fields.update(kwargs)
        plans.save_plan(plan, **fields)
        return plan
