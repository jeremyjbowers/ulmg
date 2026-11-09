# ABOUTME: End-to-end tests for roster moves on the team page: the move form, the move log, moves left and active stays.
# ABOUTME: Posts real forms over the test client as the owner, another owner, the commissioner and logged out.

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from ulmg import models, roster_moves, schedule
from tests.plan_fixtures import SEASON, Roster, create_pitcher, create_season

TEAM_URL = "/teams/atl/"
GAME_URL = "/teams/atl/game/"
MOVE_URL = "/teams/atl/moves/"


def create_owner(username, team):
    user = User.objects.create_user(username, f"{username}@example.com", "password")
    owner = models.Owner.objects.create(user=user, name=f"{username} owner", email=user.email)
    team.owner_obj = owner
    team.save()
    return user


@override_settings(CURRENT_SEASON=SEASON, TEAM_SEASON_HALF="1h", TEAM_ROSTER_TAB=True)
class RosterMoveViewsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_season()
        cls.atl = models.Team.objects.get(abbreviation="ATL")
        cls.car = models.Team.objects.get(abbreviation="CAR")
        cls.roster = Roster(cls.atl)
        cls.up = create_pitcher(cls.atl, "ATL Call-up", roster=False)
        cls.owner = create_owner("atl", cls.atl)
        cls.other = create_owner("car", cls.car)
        cls.commish = User.objects.create_superuser("commish", "c@example.com", "password")

    def setUp(self):
        self.clients = {}

    def client_for(self, user):
        # One client per user, so a message set by a post shows on the next page.
        if user not in self.clients:
            client = Client()
            if user is not None:
                client.force_login(user)
            self.clients[user] = client
        return self.clients[user]

    def post_move(self, user, up=None, down=None):
        up = up or self.up
        down = down or self.roster.relievers[1]
        return self.client_for(user).post(MOVE_URL, {"player_up": up.id, "player_down": down.id})

    def test_the_owner_makes_a_move_and_sees_it_on_the_team_page(self):
        response = self.post_move(self.owner)
        self.assertRedirects(response, GAME_URL + "#roster-moves", fetch_redirect_response=False)
        move = models.RosterMove.objects.get()
        self.assertEqual(move.made_by, self.owner)
        self.up.refresh_from_db()
        self.assertTrue(self.up.is_ulmg_mlb_roster)

        page = self.client_for(self.owner).get(GAME_URL)
        self.assertContains(page, "Called up ATL Call-up and sent down ATL Reliever 2.")
        self.assertContains(page, '<span id="moves-left">9</span> of 10', html=False)
        self.assertContains(page, 'class="roster-stay"', count=1)
        self.assertContains(page, "15 road games left")
        self.assertContains(page, 'class="roster-move-row ', count=1)
        self.assertContains(page, 'name="player_up"')

    def test_a_rejected_move_shows_why_and_changes_nothing(self):
        self.post_move(self.owner)
        response = self.post_move(self.owner, up=self.roster.relievers[0], down=self.up)
        self.assertRedirects(response, GAME_URL + "#roster-moves", fetch_redirect_response=False)
        page = self.client_for(self.owner).get(GAME_URL)
        self.assertContains(page, "already on ATL&#x27;s 30-man")
        self.assertEqual(models.RosterMove.objects.count(), 1)

    def test_a_cut_short_stay_is_refused_over_the_form(self):
        self.post_move(self.owner)
        replacement = create_pitcher(self.atl, "ATL Second Call-up", roster=False)
        self.post_move(self.owner, up=replacement, down=self.up)
        page = self.client_for(self.owner).get(GAME_URL)
        self.assertContains(page, "stays on the 30-man for 15 road games")
        self.assertEqual(models.RosterMove.objects.count(), 1)

    def test_the_commissioner_can_make_a_move(self):
        self.post_move(self.commish)
        self.assertEqual(models.RosterMove.objects.get().made_by, self.commish)

    def test_another_owner_is_refused(self):
        with self.assertLogs("django.request", "WARNING") as logs:
            response = self.post_move(self.other)
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden: /teams/atl/moves/", logs.output[0])
        self.assertFalse(models.RosterMove.objects.exists())
        page = self.client_for(self.other).get(GAME_URL)
        self.assertContains(page, "half-not-started")
        self.assertNotContains(page, 'name="player_up"')

    def test_a_logged_out_post_goes_to_login(self):
        response = self.post_move(None)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])
        self.assertFalse(models.RosterMove.objects.exists())

    def test_get_is_not_allowed(self):
        with self.assertLogs("django.request", "WARNING") as logs:
            response = self.client_for(self.owner).get(MOVE_URL)
        self.assertEqual(response.status_code, 405)
        self.assertIn("Method Not Allowed (GET): /teams/atl/moves/", logs.output[0])

    def test_moves_left_reaches_zero(self):
        for i in range(roster_moves.MOVES_PER_HALF):
            models.RosterMove.objects.create(
                season=SEASON, half=1, team=self.atl, player_up=self.up,
                player_down=self.roster.relievers[1], stay_games=0,
            )
        page = self.client_for(self.owner).get(GAME_URL)
        self.assertContains(page, '<span id="moves-left">0</span> of 10', html=False)
        self.assertContains(page, 'class="roster-move-row ', count=10)


@override_settings(CURRENT_SEASON=SEASON, TEAM_SEASON_HALF="1h")
class PlanPagesAfterAMoveTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_season()
        cls.atl = models.Team.objects.get(abbreviation="ATL")
        cls.roster = Roster(cls.atl)
        cls.up = create_pitcher(cls.atl, "ATL Call-up", roster=False)
        cls.owner = create_owner("atl", cls.atl)
        cls.roster.file()
        cls.sent = cls.roster.hitters[3]
        roster_moves.make_move(cls.atl, cls.up, cls.sent, season=SEASON, half=1)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.owner)

    def option(self, player):
        return f'<option value="{player.id}"'

    def test_the_plan_editor_offers_call_ups_and_sent_down_players(self):
        page = self.client.get(f"/teams/atl/plan/1/edit/?season={SEASON}")
        self.assertContains(page, self.option(self.up))
        self.assertContains(page, self.option(self.sent))

    def test_the_day_editor_offers_that_games_roster(self):
        games = [g for g in schedule.team_games(self.atl, SEASON) if g.series.slot.half == 1]
        home = next(g for g in games if g.series.home_team_id == self.atl.id)
        road = next(g for g in games if g.series.road_team_id == self.atl.id)
        home_page = self.client.get(f"/teams/atl/plan/1/day/{home.day}/?season={SEASON}")
        self.assertNotContains(home_page, self.option(self.up))
        self.assertContains(home_page, self.option(self.sent))
        road_page = self.client.get(f"/teams/atl/plan/1/day/{road.day}/?season={SEASON}")
        self.assertContains(road_page, self.option(self.up))
        self.assertNotContains(road_page, self.option(self.sent))

    def test_the_plan_page_flags_a_sent_down_batter_on_road_days(self):
        page = self.client.get(f"/teams/atl/plan/1/?season={SEASON}")
        road_days = sum(
            1 for g in schedule.team_games(self.atl, SEASON)
            if g.series.slot.half == 1 and g.series.road_team_id == self.atl.id
        )
        self.assertContains(page, "plan-unavailable", count=road_days)
