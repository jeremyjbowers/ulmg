# ABOUTME: End-to-end tests for the public league and team schedule pages.
# ABOUTME: Fetches pages over the test client, logged out and as a manager, after generating a real schedule.

import re
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from ulmg import models, schedule
from tests.schedule_fixtures import create_league_teams


class ScheduleViewsTestCase(TestCase):
    def setUp(self):
        self.teams = create_league_teams()
        call_command("generate_schedule", "--season", "2027", "--seed", "21", stdout=StringIO())
        self.client = Client()
        self.team = models.Team.objects.get(abbreviation="ATL")

    def test_league_schedule_is_public(self):
        response = self.client.get("/schedule/?season=2027")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("2027 schedule", body)
        self.assertIn("Days 1-4", body)
        last = models.ScheduleSlot.objects.get(season=2027, number=44)
        self.assertEqual(last.last_day, 162)
        self.assertIn(f"Days {last.first_day}-162", body)
        self.assertEqual(body.count('class="schedule-slot"'), 44)
        self.assertEqual(body.count('class="schedule-series"'), 352)

    def test_league_schedule_lists_every_series_in_a_slot(self):
        body = self.client.get("/schedule/?season=2027").content.decode()
        slot = models.ScheduleSlot.objects.get(season=2027, number=1)
        for series in slot.series.all():
            self.assertIn(
                f"{series.road_team.abbreviation}</a> at <a href=\"/teams/{series.home_team.abbreviation.lower()}/schedule/?season=2027\"",
                body,
            )

    @override_settings(CURRENT_SEASON=2027, CURRENT_SEASON_TYPE="midseason")
    def test_league_schedule_defaults_to_the_current_season(self):
        body = self.client.get("/schedule/").content.decode()
        self.assertIn("2027 schedule", body)

    def test_league_schedule_without_a_schedule(self):
        response = self.client.get("/schedule/?season=2031")
        self.assertEqual(response.status_code, 200)
        self.assertIn("No schedule has been generated for 2031", response.content.decode())

    def test_team_schedule_is_public_and_lists_162_games(self):
        response = self.client.get("/teams/atl/schedule/?season=2027")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertEqual(body.count('class="schedule-game"'), 162)
        self.assertEqual(body.count("unplayed"), 162)
        self.assertNotIn("You play", body)
        days = [int(d) for d in re.findall(r'data-day="(\d+)"', body)]
        self.assertEqual(days, list(range(1, 163)))

    def test_team_schedule_shows_opponent_and_park(self):
        body = self.client.get("/teams/atl/schedule/?season=2027").content.decode()
        for game in schedule.team_games(self.team, 2027)[:10]:
            if game.series.home_team_id == self.team.id:
                text = f"vs <a[^>]*>{game.series.road_team.abbreviation}</a>"
            else:
                text = f"at <a[^>]*>{game.series.home_team.abbreviation}</a>"
            self.assertRegex(body, rf'data-day="{game.day}"[^>]*>\s*<td[^>]*>{game.day}</td>\s*<td[^>]*>{text}')

    def test_team_schedule_shows_results(self):
        game = schedule.team_games(self.team, 2027)[0]
        game.home_score = 7
        game.road_score = 3
        game.save()
        body = self.client.get("/teams/atl/schedule/?season=2027").content.decode()
        self.assertEqual(body.count("unplayed"), 161)
        if game.series.home_team_id == self.team.id:
            self.assertIn("W 7-3", body)
        else:
            self.assertIn("L 3-7", body)

    def test_manager_sees_his_road_games_marked(self):
        user = User.objects.create_user(username="atl", email="atl@example.com")
        owner = models.Owner.objects.create(user=user, name="ATL Owner", email="atl@example.com")
        self.team.owner_obj = owner
        self.team.save()
        self.client.force_login(user)
        body = self.client.get("/teams/atl/schedule/?season=2027").content.decode()
        self.assertEqual(body.count("You play"), 81)
        other = self.client.get("/teams/pit/schedule/?season=2027").content.decode()
        self.assertNotIn("You play", other)

    def test_team_pages_link_to_the_schedule(self):
        self.client.force_login(User.objects.create_user(username="reader"))
        roster = self.client.get("/teams/atl/").content.decode()
        self.assertIn('href="/teams/atl/schedule/"', roster)
        other = self.client.get("/teams/atl/other/").content.decode()
        self.assertIn('href="/teams/atl/schedule/"', other)

    def test_navigation_links_to_the_league_schedule(self):
        self.client.force_login(User.objects.create_user(username="reader"))
        body = self.client.get("/trades/").content.decode()
        self.assertIn('href="/schedule/"', body)

    def test_the_rest_of_the_site_still_requires_login(self):
        response = self.client.get("/teams/atl/")
        self.assertEqual(response.status_code, 302)
