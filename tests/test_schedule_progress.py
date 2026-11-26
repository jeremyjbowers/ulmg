# ABOUTME: Tests home and away progress, and the in-season bar that offers the next road game.
# ABOUTME: Percents, the record and the runs come from the scheduled games. A tester reads the club on the page.

from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings

from tests.usage_fixtures import ULMG_SEASON, create_series, create_teams
from ulmg import models, schedule, utils
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
