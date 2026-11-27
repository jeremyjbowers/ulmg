# ABOUTME: Tests home and away progress, and the in-season bar that offers the next road game.
# ABOUTME: Percents come from the scheduled games. A finished away schedule leaves the button. Staff get the club on the schedule.

import re
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings

from tests.usage_fixtures import ULMG_SEASON, create_series, create_teams
from ulmg import models, schedule, sim_game, utils
from ulmg.templatetags.ulmg_tags import play_bar_for


class SideProgressTest(TestCase):
    def setUp(self):
        self.home, self.road = create_teams()
        self.games = create_series(self.home, self.road, length=3)

    def test_a_played_road_game_counts_for_each_club(self):
        self.games[0].home_score = 3
        self.games[0].road_score = 5
        self.games[0].save()
        away = schedule.side_progress(self.road, ULMG_SEASON)
        self.assertEqual(away["away"]["played"], 1)
        self.assertEqual(away["away"]["scheduled"], 3)
        self.assertEqual(away["away"]["percent"], 33)
        self.assertEqual(away["away"]["record"], "1-0")
        self.assertEqual(away["away"]["runs_scored"], 5)
        self.assertEqual(away["away"]["runs_allowed"], 3)
        self.assertEqual(away["home"]["scheduled"], 0)
        self.assertEqual(away["home"]["percent"], 0)
        home = schedule.side_progress(self.home, ULMG_SEASON)
        self.assertEqual(home["home"]["record"], "0-1")
        self.assertEqual(home["home"]["runs_scored"], 3)
        self.assertEqual(home["home"]["runs_allowed"], 5)
        self.assertEqual(home["home"]["percent"], 33)

    def test_a_tie_is_named_and_a_closed_half_is_left_out(self):
        self.games[0].home_score = 4
        self.games[0].road_score = 4
        self.games[0].save()
        self.assertEqual(schedule.side_progress(self.road, ULMG_SEASON)["away"]["record"], "0-0-1")
        later = create_series(self.road, self.home, length=2, slot_number=2, first_day=10)
        later[0].series.slot.half = 2
        later[0].series.slot.save()
        later[0].home_score = 1
        later[0].road_score = 8
        later[0].save()
        first = schedule.side_progress(self.home, ULMG_SEASON, halves=(1,))
        self.assertEqual(first["away"]["scheduled"], 0)
        both = schedule.side_progress(self.home, ULMG_SEASON, halves=(1, 2))
        self.assertEqual(both["away"]["scheduled"], 2)
        self.assertEqual(both["away"]["record"], "1-0")
        self.assertEqual(both["away"]["runs_scored"], 8)
        self.assertEqual(both["away"]["runs_allowed"], 1)


@override_settings(TEAM_SEASON_HALF="1h")
class PlayBarTest(TestCase):
    def setUp(self):
        self.home, self.road = create_teams()
        self.games = create_series(self.home, self.road, length=4)
        self.games[0].home_score = 2
        self.games[0].road_score = 1
        self.games[0].save()
        self.owner = User.objects.create_user("road-owner")
        models.Owner.objects.create(user=self.owner, name="Road")
        self.road.owner_obj = models.Owner.objects.get(user=self.owner)
        self.road.save()
        patcher = patch("ulmg.utils.league_season", return_value=ULMG_SEASON)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_bar_follows_the_owner_and_names_his_next_road_game(self):
        bar = play_bar_for(self.owner, self.road, self.home)
        self.assertEqual(bar["game"].id, self.games[1].id)
        self.assertEqual(bar["game"].day, 2)
        self.assertEqual(bar["away"]["percent"], 25)
        self.assertEqual(bar["away"]["record"], "0-1")
        self.assertIsNone(play_bar_for(User.objects.create_user("stranger"), None, self.road))

    def test_a_tester_without_a_club_reads_the_club_on_the_page(self):
        tester = User.objects.create_user("tester")
        tester.groups.add(Group.objects.create(name=utils.SIM_TESTERS_GROUP))
        bar = play_bar_for(tester, None, self.home)
        self.assertEqual(bar["team"], self.home)
        self.assertIsNone(bar["game"])
        self.assertEqual(bar["home"]["percent"], 25)
        self.assertIsNone(play_bar_for(tester, None, None))

    def test_no_schedule_means_no_bar(self):
        quiet = models.Team.objects.create(abbreviation="QUI", city="Quiet", nickname="Zeros", division="Rickey")
        user = User.objects.create_user("quiet")
        models.Owner.objects.create(user=user, name="Quiet")
        quiet.owner_obj = models.Owner.objects.get(user=user)
        quiet.save()
        self.assertIsNone(play_bar_for(user, quiet, None))

    def test_a_finished_away_schedule_keeps_the_button_with_nowhere_to_go(self):
        for game in self.games[1:]:
            game.home_score = 4
            game.road_score = 2
            game.save()
        bar = play_bar_for(self.owner, self.road, None)
        self.assertTrue(bar["away_complete"])
        self.assertIsNone(bar["game"])
        self.assertEqual(bar["away"]["percent"], 100)
        self.assertIsNone(bar["staff"])

    def test_staff_on_a_schedule_get_that_clubs_next_road_game(self):
        foe = models.Team.objects.create(abbreviation="BOS", city="Boston", nickname="Pilgrims", division="Rickey")
        visiting = create_series(foe, self.home, length=2, slot_number=2, first_day=10)
        staff = User.objects.create_user("staff", is_staff=True)
        self.assertIsNone(play_bar_for(staff, None, self.home))
        bar = play_bar_for(staff, None, self.home, schedule_team=self.home)
        self.assertIsNone(bar["team"])
        self.assertIsNone(bar["home"])
        self.assertEqual(bar["staff"]["team"], self.home)
        self.assertEqual(bar["staff"]["game"].id, visiting[0].id)
        self.assertFalse(bar["staff"]["done"])

        self.owner.is_staff = True
        self.owner.save()
        own = play_bar_for(self.owner, self.road, self.road, schedule_team=self.road)
        self.assertIsNone(own["staff"])
        self.assertEqual(own["game"].id, self.games[1].id)
        other = play_bar_for(self.owner, self.road, self.home, schedule_team=self.home)
        self.assertEqual(other["game"].id, self.games[1].id)
        self.assertEqual(other["staff"]["game"].id, visiting[0].id)
        plain = play_bar_for(User.objects.create_user("plain"), None, self.home, schedule_team=self.home)
        self.assertIsNone(plain)

        for game in visiting:
            game.home_score = 1
            game.road_score = 0
            game.save()
        finished = play_bar_for(staff, None, self.home, schedule_team=self.home)
        self.assertTrue(finished["staff"]["done"])
        self.assertIsNone(finished["staff"]["game"])
        self.assertEqual(finished["staff"]["team"], self.home)

    def test_staff_may_open_only_that_clubs_next_road_game(self):
        staff = User.objects.create_user("commish", is_staff=True)
        self.assertEqual(sim_game.open_seat_choices(staff, self.games[1]), [(sim_game.AWAY,)])
        self.assertEqual(sim_game.open_seat_choices(staff, self.games[2]), [])
        self.assertEqual(sim_game.open_seat_choices(staff, self.games[0]), [])
        self.assertTrue(sim_game.can_play(staff, self.games[1]))
        self.assertFalse(sim_game.can_play(staff, self.games[2]))
        stranger = User.objects.create_user("stranger-2")
        self.assertEqual(sim_game.open_seat_choices(stranger, self.games[1]), [])


def _bar(html):
    return html.split('id="play-bar"', 1)[1].split("</div>", 1)[0]


@override_settings(TEAM_SEASON_HALF="1h")
class PlayBarPageTest(TestCase):
    def setUp(self):
        self.home, self.road = create_teams()
        self.games = create_series(self.home, self.road, length=4)
        self.games[0].home_score = 2
        self.games[0].road_score = 1
        self.games[0].save()
        foe = models.Team.objects.create(abbreviation="BOS", city="Boston", nickname="Pilgrims", division="Rickey")
        self.visiting = create_series(foe, self.home, length=2, slot_number=2, first_day=10)
        self.owner = User.objects.create_user("road-owner")
        models.Owner.objects.create(user=self.owner, name="Road")
        self.road.owner_obj = models.Owner.objects.get(user=self.owner)
        self.road.save()
        self.client.force_login(self.owner)
        patcher = patch("ulmg.utils.league_season", return_value=ULMG_SEASON)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_button_stays_disabled_once_his_away_games_are_all_played(self):
        for game in self.games[1:]:
            game.home_score = 4
            game.road_score = 2
            game.save()
        schedule_page = self.client.get(f"/teams/{self.road.abbreviation.lower()}/schedule/{ULMG_SEASON}/")
        bar = _bar(schedule_page.content.decode())
        self.assertIn("Away 100% complete", bar)
        self.assertRegex(bar, r'<button type="button" class="play-next" disabled[^>]*>Play next game</button>')
        self.assertNotIn("href=", bar)
        self.assertNotIn("Play next: Game", bar)
        followed = _bar(self.client.get("/trades/").content.decode())
        self.assertRegex(followed, r'<button type="button" class="play-next" disabled[^>]*>Play next game</button>')
        self.assertNotIn("href=", followed)

    def test_staff_on_a_team_schedule_get_a_second_play_next_button(self):
        self.owner.is_staff = True
        self.owner.save()
        page = self.client.get(f"/teams/{self.home.abbreviation.lower()}/schedule/{ULMG_SEASON}/")
        bar = _bar(page.content.decode())
        self.assertLess(bar.index("Play next: Game"), bar.index(f"Play next {self.home.abbreviation} game"))
        self.assertIn(
            f'href="/games/{self.games[1].id}/" class="play-next',
            bar,
        )
        self.assertIn(f"Play next: Game {self.games[1].day} at {self.home.abbreviation}", bar)
        self.assertIn(f'href="/games/{self.visiting[0].id}/" class="play-next', bar)
        self.assertIn(f">Play next {self.home.abbreviation} game</a>", bar)
        self.assertEqual(bar.count("play-next"), 2)

        own = _bar(
            self.client.get(f"/teams/{self.road.abbreviation.lower()}/schedule/{ULMG_SEASON}/").content.decode()
        )
        self.assertEqual(own.count("play-next"), 1)
        self.assertNotIn(f"Play next {self.road.abbreviation} game", own)

        elsewhere = self.client.get(f"/teams/{self.home.abbreviation.lower()}/game/").content.decode()
        self.assertNotIn(f"Play next {self.home.abbreviation} game", elsewhere)
        trades = self.client.get("/trades/").content.decode()
        self.assertNotIn(f"Play next {self.home.abbreviation} game", trades)

        self.owner.is_staff = False
        self.owner.save()
        plain = _bar(
            self.client.get(f"/teams/{self.home.abbreviation.lower()}/schedule/{ULMG_SEASON}/").content.decode()
        )
        self.assertNotIn(f"Play next {self.home.abbreviation} game", plain)
        self.assertEqual(plain.count("play-next"), 1)

    def test_the_staff_button_is_dead_when_that_clubs_away_schedule_is_complete(self):
        self.owner.is_staff = True
        self.owner.save()
        for game in self.visiting:
            game.home_score = 1
            game.road_score = 0
            game.save()
        bar = _bar(
            self.client.get(f"/teams/{self.home.abbreviation.lower()}/schedule/{ULMG_SEASON}/").content.decode()
        )
        self.assertIn(f'href="/games/{self.games[1].id}/" class="play-next', bar)
        self.assertRegex(
            bar,
            rf'<button type="button" class="play-next" disabled[^>]*>Play next {self.home.abbreviation} game</button>',
        )
        self.assertNotIn(f'href="/games/{self.visiting[0].id}/"', bar)
        self.assertIsNone(re.search(rf'href="[^"]*">Play next {self.home.abbreviation} game', bar))

    def test_staff_without_a_club_can_open_the_schedule_teams_next_road_game(self):
        staff = User.objects.create_user("commish", is_staff=True)
        self.client.force_login(staff)
        page = self.client.get(f"/teams/{self.road.abbreviation.lower()}/schedule/{ULMG_SEASON}/")
        bar = _bar(page.content.decode())
        self.assertEqual(bar.count("play-next"), 1)
        self.assertIn(f'href="/games/{self.games[1].id}/" class="play-next', bar)
        self.assertIn(f">Play next {self.road.abbreviation} game</a>", bar)
        self.assertNotIn("% complete", bar)
        opened = self.client.get(f"/games/{self.games[1].id}/")
        self.assertContains(opened, "Proceed with this lineup")
        self.assertContains(opened, f'action="/games/{self.games[1].id}/open/"')
        later = self.client.get(f"/games/{self.games[2].id}/")
        self.assertContains(later, "You can't open this game")
        self.assertNotContains(later, "Proceed with this lineup")
