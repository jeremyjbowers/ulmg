# ABOUTME: End-to-end tests for the half plan pages: the public plan, the plan editor and the day editor.
# ABOUTME: Posts real forms over the test client as the owner, another owner, the commissioner and logged out.

import re

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from ulmg import models, plans, usage
from tests.plan_fixtures import SEASON, Roster, create_hitter, create_season


def form_data(roster, rotation=None, vs_lhp=None, vs_rhp=None):
    data = {
        "rotation": [p.id for p in (rotation or roster.starters)],
        "closer": roster.relievers[0].id,
        "setup_l": [],
        "setup_r": [roster.relievers[1].id],
        "sirp": [],
        "mirp": [roster.swingman.id],
        "bench": [p.id for p in roster.bench],
    }
    for prefix, lineup in (("vs_lhp", vs_lhp), ("vs_rhp", vs_rhp)):
        for i, entry in enumerate(lineup or roster.lineup(), start=1):
            data[f"{prefix}_order_{i}"] = entry["order"]
            data[f"{prefix}_player_{i}"] = entry["player"].id
            data[f"{prefix}_position_{i}"] = entry["position"]
    return data


def day_data(starter=None, lineup=None):
    data = {"starter": starter.id if starter else ""}
    if lineup:
        data["override_lineup"] = "1"
        for i, entry in enumerate(lineup, start=1):
            data[f"day_order_{i}"] = entry["order"]
            data[f"day_player_{i}"] = entry["player"].id
            data[f"day_position_{i}"] = entry["position"]
    return data


def create_owner(username, team):
    user = User.objects.create_user(username, f"{username}@example.com", "password")
    owner = models.Owner.objects.create(user=user, name=f"{username} owner", email=user.email)
    team.owner_obj = owner
    team.save()
    return user


PLAN_URL = f"/teams/atl/plan/1/?season={SEASON}"
EDIT_URL = f"/teams/atl/plan/1/edit/?season={SEASON}"


def day_url(day, half=1):
    return f"/teams/atl/plan/{half}/day/{day}/?season={SEASON}"


@override_settings(CURRENT_SEASON=SEASON, TEAM_SEASON_HALF="1h")
class PlanViewsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_season()
        cls.atl = models.Team.objects.get(abbreviation="ATL")
        cls.car = models.Team.objects.get(abbreviation="CAR")
        cls.roster = Roster(cls.atl)
        cls.owner = create_owner("atl", cls.atl)
        cls.other_owner = create_owner("car", cls.car)
        cls.commissioner = User.objects.create_superuser("commish", "commish@example.com", "password")

    def setUp(self):
        self.client = Client()

    def as_user(self, user):
        self.client.force_login(user)
        return self.client

    def saved_plan(self):
        return models.HalfPlan.objects.filter(team=self.atl, season=SEASON, half=1).first()


class PublicPlanTestCase(PlanViewsTestCase):
    def test_plan_is_public(self):
        self.roster.file()
        response = self.client.get(PLAN_URL)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertEqual(body.count('class="plan-day '), 81)
        self.assertEqual([int(d) for d in re.findall(r'data-day="(\d+)"', body)], list(range(1, 82)))
        self.assertEqual(body.count('class="plan-rotation"'), 5)
        self.assertIn("ATL Starter 1", body)
        self.assertIn('class="plan-closer"', body)
        self.assertIn("ATL Bench 1", body)
        self.assertNotIn("Edit the plan", body)
        self.assertNotIn("Edit day", body)

    def test_plan_shows_cards_and_usage(self):
        self.roster.file()
        body = self.client.get(PLAN_URL).content.decode()
        self.assertIn("34 starts left", body)
        self.assertIn("C +4.0", body)
        self.assertIn("unlimited PA", body)

    def test_plan_page_without_a_plan(self):
        response = self.client.get(PLAN_URL)
        self.assertEqual(response.status_code, 200)
        self.assertIn("ATL has not filed a plan for this half", response.content.decode())

    def test_logged_out_editor_redirects_to_login(self):
        response = self.client.get(EDIT_URL)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_another_owner_can_read_but_not_edit(self):
        self.roster.file()
        client = self.as_user(self.other_owner)
        self.assertEqual(client.get(PLAN_URL).status_code, 200)
        self.assertNotIn("Edit the plan", client.get(PLAN_URL).content.decode())
        self.assertEqual(client.get(EDIT_URL).status_code, 403)

        reversed_rotation = list(reversed(self.roster.starters))
        response = client.post(EDIT_URL, form_data(self.roster, rotation=reversed_rotation))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.saved_plan().rotation, [p.id for p in self.roster.starters])

        response = client.post(day_url(20), day_data(starter=self.roster.swingman))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.saved_plan().days.filter(manual_starter__isnull=False).exists())

    def test_capped_batter_is_flagged(self):
        self.roster.file()
        counter = usage.counter_for(self.roster.hitters[-1], SEASON)
        counter.plate_appearances_cap = 10
        counter.plate_appearances = 10
        counter.save()
        body = self.client.get(PLAN_URL).content.decode()
        self.assertIn("past his PA cap", body)


class EditPlanTestCase(PlanViewsTestCase):
    def test_owner_saves_a_plan(self):
        client = self.as_user(self.owner)
        page = client.get(EDIT_URL)
        self.assertEqual(page.status_code, 200)
        self.assertIn("Save the plan", page.content.decode())

        response = client.post(EDIT_URL, form_data(self.roster), follow=True)
        self.assertRedirects(response, PLAN_URL)
        self.assertIn("Saved the half 1 plan", response.content.decode())
        plan = self.saved_plan()
        self.assertEqual(plans.starters(plan)[6], self.roster.starters[0])
        self.assertEqual(plan.lineup_vs_rhp[0], {"player": self.roster.catcher.id, "position": "C"})
        self.assertTrue(usage.counter_for(self.roster.swingman, SEASON).confined_to_relief)

    def test_owner_sets_the_starter_hook(self):
        client = self.as_user(self.owner)
        page = client.get(EDIT_URL).content.decode()
        self.assertIn('<option value="normal" selected>Normal</option>', page)
        response = client.post(EDIT_URL, dict(form_data(self.roster), starter_hook="quick"), follow=True)
        self.assertRedirects(response, PLAN_URL)
        self.assertEqual(self.saved_plan().starter_hook, models.HalfPlan.QUICK_HOOK)
        self.assertIn('class="plan-starter-hook">Quick', response.content.decode())
        page = client.get(EDIT_URL).content.decode()
        self.assertIn('<option value="quick" selected>Quick</option>', page)

    def test_owner_sets_usage(self):
        client = self.as_user(self.owner)
        response = client.post(
            EDIT_URL,
            dict(
                form_data(self.roster),
                closer_usage="leverage",
                relief_usage="early",
                bench_usage="glove",
            ),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        plan = self.saved_plan()
        self.assertEqual(plan.closer_usage, models.HalfPlan.LEVERAGE)
        self.assertEqual(plan.relief_usage, models.HalfPlan.EARLY)
        self.assertEqual(plan.bench_usage, models.HalfPlan.GLOVE)
        page = response.content.decode()
        self.assertIn('class="plan-closer-usage">Leverage', page)
        self.assertIn('class="plan-relief-usage">Early', page)
        self.assertIn('class="plan-bench-usage">Glove', page)

    def test_an_unknown_usage_is_refused(self):
        self.roster.file(bench_usage=models.HalfPlan.GLOVE)
        response = self.as_user(self.owner).post(EDIT_URL, dict(form_data(self.roster), bench_usage="bunt"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("The bench usage must be stand, pinch or glove.", response.content.decode())
        self.assertEqual(self.saved_plan().bench_usage, models.HalfPlan.GLOVE)

    def test_an_unknown_starter_hook_is_refused(self):
        self.roster.file()
        response = self.as_user(self.owner).post(EDIT_URL, dict(form_data(self.roster), starter_hook="lazy"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("The starter hook must be quick, normal or slow.", response.content.decode())
        self.assertEqual(self.saved_plan().starter_hook, models.HalfPlan.NORMAL_HOOK)

    def test_editor_shows_the_saved_plan(self):
        self.roster.file()
        body = self.as_user(self.owner).get(EDIT_URL).content.decode()
        self.assertIn(f'<option value="{self.roster.starters[0].id}" selected>', body)

    def test_commissioner_can_edit_any_plan(self):
        response = self.as_user(self.commissioner).post(EDIT_URL, form_data(self.roster))
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(self.saved_plan())

    def test_rule_errors_are_shown_and_nothing_is_saved(self):
        lineup = self.roster.lineup()
        lineup[8]["player"] = self.roster.starters[0]
        response = self.as_user(self.owner).post(EDIT_URL, form_data(self.roster, vs_rhp=lineup))
        self.assertEqual(response.status_code, 400)
        body = response.content.decode()
        self.assertIn("ATL Starter 1 is a pitcher; pitchers do not hit.", body)
        # The posted selections are kept on the form.
        self.assertIn(f'<option value="{self.roster.starters[0].id}" selected>', body)
        plan = self.saved_plan()
        self.assertTrue(plan is None or not plan.days.exists())

    def test_save_rejected_listing_days_without_a_starter(self):
        response = self.as_user(self.owner).post(
            EDIT_URL, form_data(self.roster, rotation=self.roster.starters[:3])
        )
        self.assertEqual(response.status_code, 400)
        self.assertRegex(response.content.decode(), r"No legal starter for days 4, ")

    def test_second_half_locked_until_2h(self):
        url = f"/teams/atl/plan/2/edit/?season={SEASON}"
        client = self.as_user(self.owner)
        self.assertIn("opens after the trade break", client.get(url).content.decode())
        response = client.post(url, form_data(self.roster))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(models.HalfPlan.objects.filter(half=2).exists())
        public = self.client.get(f"/teams/atl/plan/2/?season={SEASON}").content.decode()
        self.assertIn("opens after the trade break", public)
        self.assertIn("ATL has not filed a plan for this half", public)

        with self.settings(TEAM_SEASON_HALF="2h"):
            response = client.post(url, form_data(self.roster))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.HalfPlanDay.objects.filter(plan__half=2).count(), 81)

    def test_unknown_half_is_not_found(self):
        self.assertEqual(self.client.get(f"/teams/atl/plan/3/?season={SEASON}").status_code, 404)


class EditDayTestCase(PlanViewsTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.plan = cls.roster.file()

    def test_owner_sets_a_spot_start_and_a_lineup(self):
        lineup = self.roster.lineup(self.roster.hitters[:-1] + [self.roster.bench[1]])
        client = self.as_user(self.owner)
        self.assertEqual(client.get(day_url(20)).status_code, 200)
        response = client.post(day_url(20), day_data(starter=self.roster.swingman, lineup=lineup), follow=True)
        self.assertRedirects(response, PLAN_URL + "#day-20", fetch_redirect_response=False)
        body = response.content.decode()
        self.assertIn("ends his relief-only designation", body)
        row = self.plan.days.get(day=20)
        self.assertEqual(row.manual_starter, self.roster.swingman)
        self.assertEqual(row.manual_lineup[-1], {"player": self.roster.bench[1].id, "position": "DH"})
        self.assertRegex(body, r'(?s)data-day="20".*?SP: ATL Swingman<span class="font-bold">\*</span>')

    def test_spot_start_breaking_rest_is_rejected(self):
        response = self.as_user(self.owner).post(day_url(3), day_data(starter=self.roster.starters[0]))
        self.assertEqual(response.status_code, 400)
        self.assertIn("has not had rest", response.content.decode())
        self.assertIsNone(self.plan.days.get(day=3).manual_starter)

    def test_clearing_a_day_returns_it_to_auto_fill(self):
        client = self.as_user(self.owner)
        client.post(day_url(20), day_data(starter=self.roster.swingman))
        client.post(day_url(20), day_data())
        self.assertIsNone(self.plan.days.get(day=20).manual_starter)

    def test_an_opened_day_cannot_be_edited(self):
        game = next(g for g in plans.half_games(self.atl, SEASON, 1).values() if g.day == 1)
        plans.open_game(game)
        client = self.as_user(self.owner)
        self.assertIn("has opened", client.get(day_url(1)).content.decode())
        response = client.post(day_url(1), day_data(starter=self.roster.swingman))
        self.assertEqual(response.status_code, 400)
        body = client.get(PLAN_URL).content.decode()
        self.assertRegex(body, r'(?s)data-day="1".*?Opened')
        self.assertEqual(body.count("Edit day"), 80)

    def test_lineup_override_rule_errors(self):
        stranger = create_hitter(self.car, "CAR Hitter")
        lineup = self.roster.lineup()
        lineup[8]["player"] = stranger
        response = self.as_user(self.owner).post(day_url(10), day_data(lineup=lineup))
        self.assertEqual(response.status_code, 400)
        self.assertIn("CAR Hitter is not on ATL&#x27;s 30-man", response.content.decode())


class SchedulePlannedStartersTestCase(PlanViewsTestCase):
    def test_team_schedule_shows_the_plans_starters(self):
        self.roster.file()
        body = self.client.get(f"/teams/atl/schedule/?season={SEASON}").content.decode()
        self.assertRegex(body, r'(?s)data-day="1">.*?class="schedule-starters[^"]*">\s*ATL Starter 1 vs -\s*</td>')
        self.assertRegex(body, r'(?s)data-day="6">.*?class="schedule-starters[^"]*">\s*ATL Starter 1 vs -\s*</td>')
        self.assertEqual(body.count("ATL Starter 1 vs"), 17)


SCHEDULE_URL = f"/teams/atl/schedule/?season={SEASON}"


class ScheduleStarterEditTestCase(PlanViewsTestCase):
    def setUp(self):
        super().setUp()
        self.plan = self.roster.file()

    def select(self, body, day):
        match = re.search(rf'aria-label="Starter, day {day}"(.*?)</select>', body, re.S)
        self.assertIsNotNone(match, msg=f"day {day} has no starter select")
        return match.group(1)

    def test_the_owner_sees_the_rotation_on_games_1_6_and_11_and_can_change_one_day(self):
        client = self.as_user(self.owner)
        body = client.get(SCHEDULE_URL).content.decode()
        ace = self.roster.starters[0].name
        for day in (1, 6, 11):
            chosen = self.select(body, day)
            self.assertIn(f"Rotation: {ace}", chosen)
            self.assertIn('value="" selected', chosen)
            self.assertRegex(chosen, r"\(\d+\)")
        self.assertIsNone(re.search(r'aria-label="Starter, day 82"', body))

        fifth = self.roster.swingman
        lineup = self.roster.lineup()
        lineup[8]["player"] = self.roster.bench[0]
        plans.save_day(self.plan, 1, lineup=lineup)
        response = client.post(SCHEDULE_URL, {"day": 1, "starter": fifth.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        chosen = self.select(response.content.decode(), 1)
        self.assertIn(f'value="{fifth.id}" selected', chosen)
        self.assertIn(f"Rotation: {ace}", self.select(response.content.decode(), 6))
        row = self.plan.days.get(day=1)
        self.assertEqual(row.manual_starter_id, fifth.id)
        self.assertEqual(row.manual_lineup[-1]["player"], self.roster.bench[0].id)

        cleared = client.post(SCHEDULE_URL, {"day": 1, "starter": ""}, follow=True)
        self.assertIn("the rotation", cleared.content.decode())
        self.plan.days.get(day=1).refresh_from_db()
        self.assertIsNone(self.plan.days.get(day=1).manual_starter_id)
        self.assertEqual(self.plan.days.get(day=1).manual_lineup[-1]["player"], self.roster.bench[0].id)

    def test_a_pitcher_at_his_start_cap_is_left_out_and_a_forged_post_is_refused(self):
        capped = self.roster.swingman
        counter = usage.counter_for(capped, SEASON)
        counter.starts_cap = 0
        counter.save()
        client = self.as_user(self.owner)
        chosen = self.select(client.get(SCHEDULE_URL).content.decode(), 2)
        self.assertNotIn(f'value="{capped.id}"', chosen)
        response = client.post(SCHEDULE_URL, {"day": 2, "starter": capped.id}, follow=True)
        self.assertIn("cap is 0 starts", response.content.decode())
        self.assertIsNone(self.plan.days.get(day=2).manual_starter_id)

    def test_another_owner_cannot_set_starters_and_a_visitor_sees_the_names(self):
        response = self.as_user(self.other_owner).post(
            SCHEDULE_URL, {"day": 1, "starter": self.roster.starters[4].id}
        )
        self.assertEqual(response.status_code, 403)
        body = Client().get(SCHEDULE_URL).content.decode()
        self.assertNotIn('aria-label="Starter, day 1"', body)
        self.assertIn("ATL Starter 1 vs", body)
