# ABOUTME: Tests the normal and advanced choice: who starts where, and that a saved choice sticks.
# ABOUTME: The game pages post the choice. Cards then show the baseball-card line, or the wash.

from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase

from tests.usage_fixtures import create_teams
from ulmg import models, stats_view, utils


class StatsViewTest(TestCase):
    def test_staff_start_advanced_and_everyone_else_starts_normal(self):
        staff = User.objects.create_user("staff", is_staff=True)
        manager = User.objects.create_user("manager")
        self.assertEqual(stats_view.resolve(staff), stats_view.ADVANCED)
        self.assertEqual(stats_view.resolve(manager), stats_view.NORMAL)
        self.assertEqual(stats_view.resolve(AnonymousUser()), stats_view.NORMAL)

    def test_a_saved_choice_beats_the_default(self):
        staff = User.objects.create_user("staff", is_staff=True)
        owner = models.Owner.objects.create(user=staff, name="Staff")
        owner.stats_view = stats_view.NORMAL
        owner.save()
        self.assertEqual(stats_view.resolve(staff), stats_view.NORMAL)
        stats_view.save(staff, {}, stats_view.ADVANCED)
        owner.refresh_from_db()
        self.assertEqual(owner.stats_view, stats_view.ADVANCED)
        self.assertEqual(stats_view.resolve(staff), stats_view.ADVANCED)

    def test_the_game_pages_save_the_choice_and_come_back(self):
        home, road = create_teams()
        user = User.objects.create_user("mgr")
        models.Owner.objects.create(user=user, name="Mgr")
        road.owner_obj = models.Owner.objects.get(user=user)
        road.save()
        self.client.force_login(user)
        url = f"/teams/{road.abbreviation.lower()}/schedule/{utils.league_season()}/"
        page = self.client.get(url)
        self.assertContains(page, 'class="stats-view')
        self.assertContains(page, 'value="normal" class="border border-gray-400 px-1 bg-gray-800 text-white"')
        self.assertNotContains(page, 'value="advanced" class="border border-gray-400 px-1 bg-gray-800')
        saved = self.client.post("/my/stats-view/", {"stats_view": "advanced", "next": url})
        self.assertRedirects(saved, url)
        road.owner_obj.refresh_from_db()
        self.assertEqual(road.owner_obj.stats_view, "advanced")
        self.assertContains(self.client.get(url), 'value="advanced" class="border border-gray-400 px-1 bg-gray-800 text-white"')

    def test_staff_start_on_advanced_and_the_game_page_offers_the_choice(self):
        from tests.usage_fixtures import create_series

        home, road = create_teams()
        games = create_series(home, road, length=1)
        user = User.objects.create_user("staff-mgr", is_staff=True)
        models.Owner.objects.create(user=user, name="Staff Mgr")
        road.owner_obj = models.Owner.objects.get(user=user)
        road.save()
        self.client.force_login(user)
        schedule_url = f"/teams/{road.abbreviation.lower()}/schedule/{utils.league_season()}/"
        schedule_page = self.client.get(schedule_url)
        self.assertContains(schedule_page, 'value="advanced" class="border border-gray-400 px-1 bg-gray-800 text-white"')
        self.assertNotContains(schedule_page, 'value="normal" class="border border-gray-400 px-1 bg-gray-800')
        game_page = self.client.get(f"/games/{games[0].id}/")
        self.assertEqual(game_page.status_code, 200)
        self.assertContains(game_page, 'class="stats-view')
        self.assertContains(game_page, 'value="advanced" class="border border-gray-400 px-1 bg-gray-800 text-white"')

    def test_someone_without_an_owner_keeps_the_choice_for_the_session(self):
        home, road = create_teams()
        user = User.objects.create_user("guest")
        self.client.force_login(user)
        url = f"/teams/{road.abbreviation.lower()}/schedule/{utils.league_season()}/"
        self.assertContains(self.client.get(url), 'value="normal" class="border border-gray-400 px-1 bg-gray-800 text-white"')
        saved = self.client.post("/my/stats-view/", {"stats_view": "advanced", "next": url})
        self.assertRedirects(saved, url)
        self.assertEqual(self.client.session[stats_view.SESSION_KEY], "advanced")
        self.assertContains(self.client.get(url), 'value="advanced" class="border border-gray-400 px-1 bg-gray-800 text-white"')

    def test_a_bad_choice_and_an_outside_return_are_refused(self):
        user = User.objects.create_user("mgr")
        models.Owner.objects.create(user=user, name="Mgr")
        self.client.force_login(user)
        bad = self.client.post("/my/stats-view/", {"stats_view": "secret", "next": "/teams/"})
        self.assertEqual(bad.status_code, 400)
        away = self.client.post("/my/stats-view/", {"stats_view": "normal", "next": "https://evil.example/phish"})
        self.assertRedirects(away, "/")
        scheme = self.client.post("/my/stats-view/", {"stats_view": "normal", "next": "//evil.example/phish"})
        self.assertRedirects(scheme, "/")
