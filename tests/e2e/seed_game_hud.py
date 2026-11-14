# ABOUTME: Seeds a local dev database with one opened sim game for the HUD end-to-end check, using the test fixtures' real rows.
# ABOUTME: Run through `django-admin shell` with the engine up; prints the game id and a session key for the sim tester.
import random
import types

from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.core.management import call_command

from tests import game_fixtures as gf
from ulmg import models, sim_game

FIRST = ["Ava", "Ben", "Cal", "Dev", "Eli", "Finn", "Gus", "Hal", "Ike", "Jay", "Kai", "Leo", "Max", "Ned", "Oz", "Pat", "Quin", "Rio"]
LAST = [
    "Okafor", "Reyes", "Mills", "Tanaka", "Brandt", "Mireles", "Kowalczyk", "Adeyemi", "Whitlock", "Sandoval",
    "Pruitt", "Nakagawa", "Delacroix", "Halvorsen", "Castillo", "Oyelaran", "Lindqvist", "Ferreira", "Voss",
    "Marchetti", "Ibekwe", "Rasmussen", "Zielinski", "Yamamoto", "Albright", "Ruiz", "Vance", "Moreau", "Quist",
    "Sorensen", "Takeda", "Umeh", "Varga", "Wexler", "Xiong", "Yilmaz", "Zapata", "Abara", "Bianchi", "Coyle",
    "Dorsey", "Ekström", "Fontaine", "Grieve", "Huxley", "Ibarra", "Jessup", "Kerrigan", "Lusk", "Mbeki",
]

t = types.SimpleNamespace()
gf.create_game_season(t)
t.tester.set_password("tester")
t.tester.save()

# Made-up names, speeds and steal rates so the screenshots read like a game.
rng = random.Random(7)
names = iter(LAST)
for roster in (t.road, t.home):
    for player in roster.starters + roster.relievers + [roster.swingman] + roster.hitters + roster.bench:
        last = next(names)
        player.first_name = rng.choice(FIRST)
        player.last_name = last
        player.name = f"{player.first_name[0]}. {last}"
        player.save()
    for hitter in roster.hitters + roster.bench:
        models.Card.objects.filter(player=hitter).update(spd=round(rng.uniform(2.0, 8.0), 1), steal_success=round(rng.uniform(0.5, 0.9), 2))
models.Card.objects.filter(player=t.home.fielders[2]).update(defense={"3B": -2.0})
models.Card.objects.filter(player=t.road.bench[1]).update(defense={"2B": 3.0, "SS": 1.5})

venue = models.Venue.objects.create(name="Fenway Park", mlb_team="Red Sox", mlb_venue_id="3", mlb_venue_url="https://example.test/3", pf_hr=97, pf_2b=122)
call_command("load_park_dimensions")
t.home.team.home_field = venue
t.home.team.save()

log = sim_game.open_game(t.game, t.tester, (sim_game.AWAY, sim_game.HOME))
seed = gf.seeds()
for _ in range(9):
    log = gf.refresh(log)
    play = sim_game.Play(log)
    need = play.need()
    if need is not None:
        break
    sim_game.step(log, t.tester, play.sequence, seeds=seed)

session = SessionStore()
session[SESSION_KEY] = str(t.tester.pk)
session[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
session[HASH_SESSION_KEY] = t.tester.get_session_auth_hash()
session.create()
print("GAME", t.game.id)
print("SESSION", session.session_key)
